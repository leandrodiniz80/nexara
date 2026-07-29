# Elevel Prospect AI

Plataforma SaaS de prospecção inteligente assistida por IA, construída sobre uma arquitetura moderna, escalável e containerizada.

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS, Shadcn UI |
| Backend | FastAPI, SQLAlchemy 2, Pydantic, Alembic |
| Banco de Dados | PostgreSQL |
| Cache | Redis |
| Filas / Jobs assíncronos | Celery |
| Proxy / Servidor Web | Nginx |
| Containers | Docker / Docker Compose |

## Estrutura do Projeto

```
elevel-prospect-ai/
├── frontend/       # Aplicação Next.js (interface web)
├── backend/        # API FastAPI, regras de negócio, workers Celery
├── database/       # Scripts de inicialização, seeds e backups do PostgreSQL
├── docker/         # Configurações de containers (Nginx, Postgres, Redis)
├── docs/           # Documentação técnica e arquitetural do projeto
├── prompts/        # Prompts de IA (sistema, templates) usados pelo produto
├── scripts/        # Scripts utilitários de automação (setup, deploy, migrations)
├── tests/          # Testes de integração e end-to-end
└── .github/        # Workflows de CI/CD e templates de issues/PRs
```

Cada pasta possui um `README.md` próprio detalhando sua finalidade.

## Pré-requisitos

- [Docker](https://www.docker.com/) e Docker Compose
- [Node.js](https://nodejs.org/) 20+ (para desenvolvimento local do frontend)
- [Python](https://www.python.org/) 3.12+ (para desenvolvimento local do backend)

## Como subir o projeto (Docker)

1. Duplique o arquivo de variáveis de ambiente:

```bash
cp .env.example .env
```

2. Suba todos os serviços (frontend, backend, banco, cache, filas e nginx):

```bash
docker compose up --build
```

3. Serviços disponíveis após a subida:

| Serviço | URL padrão |
|---|---|
| Frontend | http://localhost:3000 |
| Backend (API) | http://localhost:8000 |
| Nginx (proxy) | http://localhost:80 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## Como executar cada parte em desenvolvimento local

Consulte a documentação detalhada em [`docs/setup.md`](docs/setup.md), que cobre:

- Como iniciar o **frontend** localmente
- Como iniciar o **backend** localmente
- Como iniciar os **workers Celery**
- Como criar e aplicar **migrations** com Alembic

## Documentação

Toda a documentação técnica do projeto está centralizada em [`docs/`](docs/README.md).

## Licença

Este projeto está licenciado sob os termos definidos em [LICENSE](LICENSE).
