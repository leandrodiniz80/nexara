# Frontend — Elevel Prospect AI

Aplicação web construída com **Next.js 15**, **React**, **TypeScript** e **Tailwind CSS**, utilizando **Shadcn UI** como base de componentes.

## Finalidade

Fornecer a interface de usuário da plataforma Elevel Prospect AI, consumindo a API do backend (FastAPI) e apresentando os fluxos de prospecção assistida por IA.

## Stack

- **Next.js 15** (App Router)
- **React** + **TypeScript**
- **Tailwind CSS**
- **Shadcn UI** — biblioteca de componentes
- **React Query** (`@tanstack/react-query`) — cache e sincronização de dados assíncronos
- **Axios** — cliente HTTP
- **React Hook Form** — gerenciamento de formulários
- **Zod** — validação e tipagem de esquemas
- **ESLint** + **Prettier** — padronização e qualidade de código
- **Husky** — git hooks (lint/format antes de commits)

## Estrutura de pastas

```
frontend/
├── public/                # Arquivos estáticos
├── src/
│   ├── app/                # Rotas e páginas (App Router)
│   ├── components/
│   │   └── ui/              # Componentes Shadcn UI
│   ├── hooks/              # Hooks React customizados
│   ├── lib/
│   │   ├── api/              # Instância Axios e chamadas à API
│   │   ├── validations/      # Schemas Zod
│   │   └── utils/            # Funções utilitárias
│   ├── services/            # Camada de integração com a API (React Query)
│   ├── store/               # Estado global da aplicação
│   ├── types/                # Tipagens TypeScript compartilhadas
│   └── styles/               # Estilos globais / Tailwind
├── .husky/                 # Git hooks
├── .eslintrc.json
├── .prettierrc
├── tailwind.config.ts
├── tsconfig.json
└── next.config.js
```

## Como iniciar o frontend localmente

```bash
cd frontend
npm install
npm run dev
```

A aplicação ficará disponível em `http://localhost:3000`.

## Scripts disponíveis

| Comando | Descrição |
|---|---|
| `npm run dev` | Inicia o servidor de desenvolvimento |
| `npm run build` | Gera o build de produção |
| `npm run start` | Inicia o servidor em modo produção |
| `npm run lint` | Executa o ESLint |
| `npm run format` | Formata o código com Prettier |

Consulte também [`docs/setup.md`](../docs/setup.md) para instruções completas de ambiente.
