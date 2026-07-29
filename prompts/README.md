# Prompts — Elevel Prospect AI

Repositório centralizado dos **prompts de IA** utilizados pelo produto para prospecção inteligente.

## Finalidade

Manter os prompts (de sistema e de tarefas específicas) versionados, desacoplados do código da aplicação, permitindo iteração e revisão independentes da lógica de negócio em `backend/`.

## Estrutura

```
prompts/
├── system/       # Prompts de sistema (definem persona, regras e limites do modelo)
└── templates/    # Templates de prompts reutilizáveis para tarefas específicas (ex: qualificação de lead, geração de mensagens)
```

## Convenções

- Cada prompt deve ser versionado em seu próprio arquivo (`.md` ou `.txt`), nomeado de forma descritiva.
- Variáveis dinâmicas dentro de um template devem ser destacadas com um padrão consistente (ex: `{{variavel}}`).
- Mudanças em prompts que afetam o comportamento do produto em produção devem ser revisadas como qualquer mudança de código.
