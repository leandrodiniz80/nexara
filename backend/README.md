# Backend — Elevel Prospect AI

API construída com **FastAPI**, responsável pelas regras de negócio, autenticação, persistência de dados e processamento assíncrono da plataforma Elevel Prospect AI.

## Finalidade

Expor a API REST consumida pelo frontend, orquestrar a lógica de prospecção assistida por IA, gerenciar persistência via PostgreSQL e delegar tarefas assíncronas/pesadas para workers Celery.

## Stack

- **FastAPI** — framework web assíncrono
- **SQLAlchemy 2** (modo assíncrono) — ORM
- **Alembic** — versionamento de schema / migrations
- **Pydantic v2** — validação e serialização de dados
- **Celery** — filas e processamento assíncrono
- **Redis** — broker/result backend do Celery e cache
- **JWT** (`python-jose` / `passlib`) — autenticação e autorização
- **Docker** — containerização

## Estrutura de pastas

```
backend/
├── app/
│   ├── main.py               # Ponto de entrada da aplicação FastAPI
│   ├── core/                  # Configurações centrais (settings, segurança/JWT)
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/     # Rotas da API, versionadas (v1)
│   ├── db/                    # Sessão e base de conexão com o banco
│   ├── models/                 # Modelos SQLAlchemy (tabelas)
│   ├── schemas/                # Schemas Pydantic (request/response)
│   ├── services/                # Regras de negócio
│   ├── repositories/            # Camada de acesso a dados
│   ├── workers/                 # Configuração do Celery e definição de tasks
│   └── utils/                    # Funções utilitárias
├── alembic/                    # Migrations do banco de dados
├── tests/                       # Testes unitários e de API do backend
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── Dockerfile
```

## Como iniciar o backend localmente

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API ficará disponível em `http://localhost:8000` e a documentação interativa (Swagger) em `http://localhost:8000/docs`.

## Como criar e aplicar migrations (Alembic)

```bash
# Gerar uma nova migration a partir das mudanças nos models
alembic revision --autogenerate -m "descrição da mudança"

# Aplicar migrations pendentes ao banco
alembic upgrade head

# Reverter a última migration
alembic downgrade -1
```

## Como iniciar os workers Celery

```bash
# Worker (processa as tasks assíncronas)
celery -A app.workers.celery_app worker --loglevel=info

# Beat (agendador de tarefas periódicas)
celery -A app.workers.celery_app beat --loglevel=info
```

Consulte também [`docs/setup.md`](../docs/setup.md) para instruções completas de ambiente.
