# Docker — Elevel Prospect AI

Configurações de infraestrutura de containers que são compartilhadas ou não pertencem a um serviço específico (os `Dockerfile` de cada aplicação ficam em [`frontend/`](../frontend/Dockerfile) e [`backend/`](../backend/Dockerfile)).

## Finalidade

Centralizar as configurações do **Nginx** (proxy reverso) e eventuais configurações auxiliares de **PostgreSQL** e **Redis** usadas pelos containers definidos em [`docker-compose.yml`](../docker-compose.yml).

## Estrutura

```
docker/
├── nginx/
│   ├── nginx.conf     # Configuração principal do Nginx
│   └── conf.d/         # Configurações de sites/proxy (frontend e backend)
├── postgres/            # Configurações auxiliares do PostgreSQL (ex: postgresql.conf customizado)
└── redis/                # Configurações auxiliares do Redis (ex: redis.conf)
```

## Como usar

O `docker-compose.yml` na raiz do projeto monta `docker/nginx/nginx.conf` e `docker/nginx/conf.d` diretamente no container `nginx`. Para adicionar uma nova rota/proxy, edite os arquivos em `nginx/conf.d/`.
