# Docs — Elevel Prospect AI

Documentação técnica e arquitetural do projeto, complementar aos `README.md` de cada pasta.

## Finalidade

Centralizar guias e decisões que não cabem em um único `README.md` de módulo: como subir o ambiente completo, convenções de arquitetura, e referências para onboarding de novos desenvolvedores.

## Índice

- [`setup.md`](setup.md) — guia completo de ambiente: subir com Docker, rodar frontend/backend localmente, criar migrations e iniciar os workers Celery.
- [`domain-prospecting.md`](domain-prospecting.md) — diagrama ER e estrutura de tabelas do domínio Prospecting (Company, Contact, Campaign, Prospect, Interaction, EmailTemplate, Tag e associativas).
- [`domain-mission.md`](domain-mission.md) — diagrama ER, `MissionEngine` e por que Mission é o aggregate root principal da plataforma (toda Campaign/Prospect pertence a uma Mission).

## Convenções

- Cada novo documento deve ser um arquivo `.md` autocontido, referenciado neste índice.
- Documentos aqui descrevem **como o sistema deve funcionar/ser operado**, não decisões de negócio (essas ficam em `Documentos/` fora do repositório) nem prompts de IA (esses ficam em [`prompts/`](../prompts)).
