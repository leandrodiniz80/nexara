# Scripts — Elevel Prospect AI

Scripts utilitários de automação para tarefas de desenvolvimento, build e operação do projeto.

## Finalidade

Centralizar scripts que automatizam tarefas repetitivas do dia a dia (setup de ambiente, deploy, execução de migrations, rotinas de manutenção), evitando comandos manuais espalhados na documentação.

## Convenções

- Scripts shell (`.sh`) para uso em Linux/Mac/CI e `.ps1`/`.bat` para uso local no Windows, quando necessário.
- Cada script deve começar com um cabeçalho comentado explicando seu propósito e uso (`./scripts/nome.sh --help`).
- Scripts não devem conter segredos ou credenciais — usar sempre variáveis de ambiente (`.env`).
- Scripts específicos de um serviço (ex: apenas backend ou apenas frontend) devem indicar isso no nome do arquivo (ex: `backend-migrate.sh`).

Nenhum script foi implementado ainda — esta pasta faz parte da fundação do projeto.
