# 🤖 Assistente IA para Atendimento

> API moderna de atendimento automatizado com Inteligência Artificial, suporte a WhatsApp e Telegram, histórico de conversas e processamento assíncrono.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-orange)](https://openai.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docker.com)

---

## 📐 Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        USUÁRIOS FINAIS                          │
│            WhatsApp              Telegram                       │
└──────────────────┬───────────────────┬──────────────────────────┘
                   │ Webhook           │ Webhook
                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                          n8n                                     │
│  (Orquestração, automações, notificações, integrações futuras)  │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP POST
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI (Python)                            │
│                                                                  │
│  /webhooks ──► Normaliza payload ──► Background Task           │
│                                                                  │
│  ConversationService                                            │
│  ├── UserRepository      ──► PostgreSQL                        │
│  ├── ConversationRepository ──► PostgreSQL                     │
│  ├── MessageRepository   ──► PostgreSQL                        │
│  ├── OpenAIService       ──► OpenAI API                        │
│  └── MessagingService    ──► WhatsApp/Telegram API             │
│                                                                  │
│  Middleware: Auth, RateLimit, Logging, RequestID               │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   PostgreSQL 16          Redis 7             OpenAI API
  (Histórico)        (Cache + Filas)        (GPT-4o)
```

---

## 🗂️ Estrutura de Pastas

```
assistente-ia-atendimento/
├── backend/
│   ├── app/
│   │   ├── config/
│   │   │   └── settings.py          # Configurações via Pydantic Settings
│   │   ├── database/
│   │   │   └── connection.py        # Engine assíncrona, sessões, lifecycle
│   │   ├── models/
│   │   │   └── models.py            # SQLAlchemy models (User, Conversation, Message)
│   │   ├── schemas/
│   │   │   └── schemas.py           # Pydantic v2 schemas (req/res)
│   │   ├── repositories/
│   │   │   └── repositories.py      # Acesso ao banco (User, Conv, Msg)
│   │   ├── services/
│   │   │   └── conversation_service.py  # Orquestração do fluxo
│   │   ├── integrations/
│   │   │   ├── openai_service.py    # Integração OpenAI com retry
│   │   │   └── messaging.py         # WhatsApp + Telegram clients
│   │   ├── routers/
│   │   │   ├── webhooks.py          # POST /webhooks/whatsapp e /telegram
│   │   │   ├── conversations.py     # CRUD de conversas
│   │   │   ├── health.py            # /health, /health/live, /health/ready
│   │   │   └── admin.py             # /admin/stats
│   │   ├── middleware/
│   │   │   ├── auth.py              # Validação API Key
│   │   │   └── rate_limit.py        # Rate limiting por IP (Redis)
│   │   ├── workers/
│   │   │   └── queue.py             # Redis queue + cache helpers
│   │   ├── utils/
│   │   │   └── logger.py            # Logging estruturado (structlog)
│   │   └── main.py                  # Instância FastAPI, middlewares, routers
│   ├── alembic/
│   │   ├── versions/
│   │   │   └── 001_initial.py       # Migration inicial
│   │   └── env.py                   # Configuração Alembic assíncrono
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── n8n/
│   └── workflows/
│       └── main_workflow.json       # Workflow n8n exportado
├── scripts/
│   └── init.sql                     # SQL de inicialização do PostgreSQL
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 Executando Localmente

### Pré-requisitos

- Docker Desktop instalado
- Conta na [OpenAI](https://platform.openai.com)
- (Opcional) WhatsApp Business API ou Telegram Bot

### 1. Clone e configure o ambiente

```bash
git clone https://github.com/seu-usuario/assistente-ia-atendimento.git
cd assistente-ia-atendimento

# Copia e edita as variáveis
cp .env.example .env
# Edite o .env com suas chaves reais
```

### 2. Configure o .env (mínimo para rodar)

```env
SECRET_KEY=gere_com_python_secrets_token_hex_32
OPENAI_API_KEY=sk-sua-chave-aqui
INTERNAL_API_KEY=qualquer_chave_para_testes
JWT_SECRET_KEY=outra_chave_secreta
POSTGRES_PASSWORD=minhasenha
```

### 3. Suba os containers

```bash
# Sobe todos os serviços
docker-compose up -d

# Aguarda os serviços ficarem healthy e roda as migrations
docker-compose up migrate

# Acompanha logs da API
docker-compose logs -f api
```

### 4. Verifique se está funcionando

```bash
# Health check
curl http://localhost:8000/health

# Documentação interativa
open http://localhost:8000/docs

# n8n (automações)
open http://localhost:5678
# Login: admin / admin123
```

---

## 📡 Endpoints Principais

### Webhooks
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/webhooks/whatsapp` | Verificação do webhook Meta |
| `POST` | `/webhooks/whatsapp` | Recebe mensagens do WhatsApp |
| `POST` | `/webhooks/telegram` | Recebe updates do Telegram |

### Conversas
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/conversations` | Lista conversas (paginado) |
| `GET` | `/conversations/{id}` | Detalhes + histórico |
| `PATCH` | `/conversations/{id}/close` | Encerra conversa |

### Admin
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/admin/stats` | Estatísticas gerais |
| `GET` | `/health` | Status dos serviços |

> Todos os endpoints (exceto webhooks e health) requerem o header:
> `X-API-Key: seu_INTERNAL_API_KEY`

---

## 🔧 Configurando WhatsApp

1. Acesse [Meta for Developers](https://developers.facebook.com)
2. Crie um App do tipo "Business"
3. Adicione o produto "WhatsApp"
4. Em **Webhooks**, configure:
   - **URL do Callback**: `https://sua-api.com/webhooks/whatsapp`
   - **Token de Verificação**: valor do `WHATSAPP_VERIFY_TOKEN` no .env
   - **Campos**: marque `messages`
5. Copie o **Access Token** e **Phone Number ID** para o .env

---

## 🤖 Configurando Telegram

```bash
# 1. Abra o @BotFather no Telegram
# 2. Envie /newbot e siga as instruções
# 3. Copie o token para TELEGRAM_BOT_TOKEN no .env

# 4. Configure o webhook (substitua os valores)
curl -X POST "https://api.telegram.org/botSEU_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://sua-api.com/webhooks/telegram"}'
```

---

## 📊 Configurando n8n

1. Acesse `http://localhost:5678`
2. Faça login com as credenciais do .env
3. Importe o workflow: **Settings → Import from file → `n8n/workflows/main_workflow.json`**
4. Configure a credencial HTTP Header Auth:
   - **Name**: API Key
   - **Header Name**: X-API-Key
   - **Header Value**: seu `INTERNAL_API_KEY`
5. Ative o workflow

---

## 🛠️ Migrações do Banco

```bash
# Rodar todas as migrations pendentes
docker-compose run --rm migrate alembic upgrade head

# Criar nova migration
docker-compose run --rm migrate alembic revision --autogenerate -m "descricao"

# Ver histórico
docker-compose run --rm migrate alembic history

# Reverter última migration
docker-compose run --rm migrate alembic downgrade -1
```

---

## 🧪 Testes

```bash
# Instala dependências de dev
pip install -r requirements.txt

# Roda testes
cd backend
pytest --cov=app tests/ -v

# Roda apenas testes de integração
pytest tests/integration/ -v
```

---

## 📦 Deploy em Cloud

### Railway (mais simples)
```bash
railway login
railway new
railway add postgresql redis
railway up
```

### AWS ECS / Fargate
- Use o `Dockerfile` com ECR para push da imagem
- Configure RDS PostgreSQL e ElastiCache Redis
- Use ECS Task Definitions para a API

### Google Cloud Run
```bash
gcloud builds submit --tag gcr.io/projeto/atendimento-api
gcloud run deploy atendimento-api --image gcr.io/projeto/atendimento-api
```

### DigitalOcean App Platform
- Conecte o repositório GitHub
- Configure as variáveis de ambiente
- Adicione PostgreSQL e Redis gerenciados

---

## 🗺️ Roadmap de Evolução

### Fase 2 — Autenticação JWT + Dashboard
- [ ] Login com JWT para painel admin
- [ ] Dashboard React com métricas em tempo real
- [ ] WebSocket para conversas ao vivo

### Fase 3 — IA Avançada (RAG)
- [ ] Embeddings com pgvector para base de conhecimento
- [ ] RAG (Retrieval-Augmented Generation) com docs da empresa
- [ ] Handoff inteligente para atendente humano

### Fase 4 — Multi-empresa (SaaS)
- [ ] Tenant isolation por empresa
- [ ] Billing e planos
- [ ] White-label

### Fase 5 — Observabilidade Completa
- [ ] OpenTelemetry + Jaeger para tracing
- [ ] Métricas Prometheus + Grafana
- [ ] Alertas automáticos

### Fase 6 — IA Agêntica
- [ ] Agentes com ferramentas (consultar sistemas, criar tickets)
- [ ] Integração com CRM (HubSpot, Salesforce)
- [ ] Análise de sentimento e escalação automática

---

## 🤝 Boas Práticas Utilizadas

- **Clean Architecture**: separação clara em camadas (router → service → repository → db)
- **Dependency Injection**: via `Depends()` do FastAPI
- **Async/Await**: toda a stack é assíncrona (I/O non-blocking)
- **12-Factor App**: configuração via variáveis de ambiente
- **Observabilidade**: logs estruturados em JSON, request ID propagado
- **Segurança**: autenticação, rate limiting, validação de assinaturas
- **Tipagem forte**: Pydantic v2 + SQLAlchemy 2.0 com mapped_column

---

## 📄 Licença

MIT — use e adapte livremente para seus projetos.
