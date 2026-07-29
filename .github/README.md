# .github — Elevel Prospect AI

Configurações do repositório específicas do GitHub.

## Finalidade

Centralizar workflows de CI/CD e templates usados na colaboração via GitHub (issues e pull requests).

## Estrutura

```
.github/
├── workflows/        # Pipelines de CI/CD (GitHub Actions) — lint, testes, build de imagens
└── ISSUE_TEMPLATE/   # Templates para abertura de issues (bug report, feature request, etc.)
```

## Convenções

- Workflows devem rodar as mesmas verificações descritas em [`docs/setup.md`](../docs/setup.md#7-qualidade-de-código) (lint, type-check, testes) para backend e frontend.
- Cada workflow deve ser disparado apenas para os arquivos relevantes (ex: mudanças em `backend/` não devem re-rodar o pipeline do `frontend/`).

Nenhum workflow ou template foi implementado ainda — esta pasta faz parte da fundação do projeto.
