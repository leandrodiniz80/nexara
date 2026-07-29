# Database — Elevel Prospect AI

Diretório dedicado a artefatos relacionados ao **PostgreSQL** que não fazem parte do código da aplicação (esses ficam em `backend/app/models` e `backend/alembic`).

## Finalidade

Centralizar scripts de inicialização, seeds e backups do banco de dados, mantendo-os fora do código-fonte da API.

## Estrutura

```
database/
├── init/       # Scripts executados automaticamente na primeira subida do container Postgres
├── seeds/      # Scripts de carga de dados iniciais/fixtures para desenvolvimento
└── backups/    # Dumps/backups do banco (ignorados pelo Git)
```

## Observações

- O schema do banco é versionado via **Alembic**, em [`backend/alembic`](../backend/alembic).
- Os scripts em `init/` são montados no container do PostgreSQL (ver [`docker-compose.yml`](../docker-compose.yml)) e executados apenas na criação inicial do volume de dados.
- Arquivos em `backups/` não devem ser versionados (ver [`.gitignore`](../.gitignore)).
