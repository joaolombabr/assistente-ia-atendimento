# Assistente IA — Atendimento

API de atendimento automatizado com IA para WhatsApp e Telegram: recebe as mensagens por
webhook (via n8n), mantém o histórico da conversa no PostgreSQL e responde com a OpenAI.

O projeto fica em [`assistente-ia-atendimento/`](assistente-ia-atendimento/) — o
[README de lá](assistente-ia-atendimento/README.md) tem a arquitetura, os endpoints e o passo a
passo para rodar.

## Stack

- **API:** Python, FastAPI, SQLAlchemy, Alembic
- **Dados:** PostgreSQL (conversas e mensagens), Redis
- **IA:** OpenAI API (`gpt-4o-mini`)
- **Canais:** WhatsApp e Telegram, com orquestração em n8n (`n8n/workflows/`)
- **Infra:** Docker Compose (API, migrations, PostgreSQL, Redis)

## Rodando

```bash
git clone https://github.com/joaolombabr/assistente-ia-atendimento.git
cd assistente-ia-atendimento/assistente-ia-atendimento
cp .env.example .env   # preencha OPENAI_API_KEY e as credenciais dos canais
docker compose up --build
```
