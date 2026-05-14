# Assistente IA - Atendimento 🚀

Este é um sistema completo de assistência para atendimento que utiliza Inteligência Artificial para automatizar processos e melhorar a eficiência. O projeto é focado em uma arquitetura robusta com conteinerização e integração com APIs de IA de ponta.

## 🛠 Tecnologias Utilizadas

* **Backend:** Python com FastAPI/SQLAlchemy.
* **Banco de Dados:** PostgreSQL para persistência de dados.
* **Cache/Mensageria:** Redis.
* **Automação:** n8n para fluxos de trabalho.
* **Infraestrutura:** Docker e Docker Compose para orquestração de serviços.
* **IA:** Integração com Anthropic API (Claude).

## 📂 Estrutura do Projeto

* `/backend`: API principal e lógica de negócio.
* `/backend/alembic`: Migrações do banco de dados para controle de versão do schema.
* `/scripts`: Scripts de inicialização, incluindo `init.sql` para o banco de dados.
* `/docs`: Documentação técnica e fluxos.

## 🚀 Como Rodar o Projeto

### Pré-requisitos

* Docker e Docker Compose instalados.
* Chave de API da Anthropic.

### Passo a Passo

1. **Clone o repositório:**
```bash
git clone https://github.com/joaolombabr/assistente-ia-atendimento.git
cd assistente-ia-atendimento

```


2. **Configure as variáveis de ambiente:**
Crie um arquivo `.env` na raiz e adicione suas credenciais:

```env
    ANTHROPIC_API_KEY=sua_chave_aqui
    POSTGRES_USER=seu_usuario
    POSTGRES_PASSWORD=sua_senha
    ```

3.  **Suba os containers:**
    ```bash
    docker-compose up --build
    ```
    Este comando irá baixar as imagens, configurar o banco de dados e iniciar a API automaticamente.

## 🧠 Funcionalidades em Implementação
*   Integração com APIs de IA (Claude/IBM Watson).
*   Automação de fluxos de atendimento via n8n.
*   Gerenciamento de tarefas e estados de atendimento.

---

**Dica:** Agora que você já fez o `git push`, você pode criar um novo arquivo chamado `README.md` no seu VS Code, colar este conteúdo, salvar e subir para o GitHub com os comandos:
1. `git add README.md`
2. `git commit -m "docs: adicionando readme do projeto"`
3. `git push origin main`

```
