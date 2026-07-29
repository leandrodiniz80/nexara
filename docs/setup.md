# Guia de Setup — Elevel Prospect AI

Guia completo para subir o ambiente de desenvolvimento, seja via Docker (recomendado) ou executando cada serviço localmente.

## Pré-requisitos

- [Docker](https://www.docker.com/) e Docker Compose
- [Node.js](https://nodejs.org/) 20+ (desenvolvimento local do frontend)
- [Python](https://www.python.org/) 3.12+ (desenvolvimento local do backend)

## 1. Variáveis de ambiente

Duplique o arquivo de exemplo na raiz do projeto e ajuste os valores conforme necessário:

```bash
cp .env.example .env
```

O frontend também possui seu próprio exemplo, usado apenas em execução local fora do Docker:

```bash
cp frontend/.env.local.example frontend/.env.local
```

## 2. Como subir o projeto inteiro (Docker)

Na raiz do projeto:

```bash
docker compose up --build
```

Isso sobe todos os serviços definidos em [`docker-compose.yml`](../docker-compose.yml):

| Serviço    | Descrição                          | URL padrão              |
| ---------- | ----------------------------------- | ------------------------ |
| `frontend` | Next.js                             | http://localhost:3000    |
| `backend`  | FastAPI                             | http://localhost:8000    |
| `worker`   | Celery worker                       | —                         |
| `beat`     | Celery beat (tarefas periódicas)    | —                         |
| `database` | PostgreSQL                          | localhost:5432            |
| `redis`    | Redis                               | localhost:6379             |
| `nginx`    | Proxy reverso                       | http://localhost:80        |

Para derrubar o ambiente:

```bash
docker compose down
```

## 3. Como executar o backend localmente (sem Docker)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000
- Documentação interativa (Swagger): http://localhost:8000/docs

Requer PostgreSQL e Redis acessíveis conforme `DATABASE_URL` e `REDIS_URL` no `.env`. Os serviços `database` e `redis` do `docker-compose.yml` podem ser subidos isoladamente:

```bash
docker compose up database redis
```

## 4. Como executar o frontend localmente (sem Docker)

```bash
cd frontend
npm install
npm run dev
```

A aplicação ficará disponível em http://localhost:3000, consumindo a API definida em `NEXT_PUBLIC_API_URL`.

## 5. Como criar e aplicar migrations (Alembic)

Sempre a partir de `backend/`, com o ambiente virtual ativo:

```bash
# Gerar uma nova migration a partir das mudanças nos models
alembic revision --autogenerate -m "descricao da mudanca"

# Aplicar migrations pendentes ao banco
alembic upgrade head

# Reverter a última migration
alembic downgrade -1
```

Rodando via Docker, execute o comando dentro do container do backend:

```bash
docker compose exec backend alembic upgrade head
```

## 6. Como iniciar os workers Celery

```bash
# Worker — processa as tasks assíncronas
celery -A app.workers.celery_app worker --loglevel=info

# Beat — agendador de tarefas periódicas
celery -A app.workers.celery_app beat --loglevel=info
```

Via Docker, os serviços `worker` e `beat` já sobem automaticamente com `docker compose up`.

## 7. Qualidade de código

```bash
# Backend
cd backend && ruff check . && black --check . && mypy .

# Frontend
cd frontend && npm run lint && npm run format:check && npm run type-check
```

O frontend usa Husky + lint-staged para rodar lint/format automaticamente antes de cada commit.
