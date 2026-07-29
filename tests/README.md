# Tests — Elevel Prospect AI

Testes que atravessam múltiplos serviços do sistema (frontend + backend + infraestrutura).

## Finalidade

Cobrir cenários que não pertencem a um único módulo: testes de integração entre backend e banco/cache/filas, e testes end-to-end (E2E) simulando o uso real da aplicação pelo navegador.

Testes unitários específicos de cada aplicação ficam junto ao próprio código: [`backend/tests`](../backend/tests) para o backend, e (quando adicionados) colocados junto aos componentes no `frontend/`.

## Estrutura

```
tests/
├── integration/   # Testes de integração entre serviços (API + banco, API + filas, etc.)
└── e2e/           # Testes end-to-end simulando fluxos completos de usuário
```

## Convenções

- `integration/`: testes em Python (pytest) que sobem dependências reais (ou via `docker compose`) para validar a integração entre backend, PostgreSQL, Redis e Celery.
- `e2e/`: testes que simulam o usuário navegando pela aplicação (ex: Playwright/Cypress), rodando contra o `frontend` e `backend` de ponta a ponta.

Nenhum teste foi implementado ainda — esta pasta faz parte da fundação do projeto.
