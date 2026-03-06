# Testes de Aceitação — ProjectDashboard

Esta pasta centraliza os testes funcionais/operacionais para manter histórico auditável.

## Estrutura

- `checklists/`: checklists base reutilizáveis (templates oficiais)
- `runs/`: execuções realizadas (histórico com evidências e resultado)

## Como usar

1. Escolha uma checklist em `checklists/`.
2. Copie para `runs/YYYY-MM-DD-<ambiente>-<objetivo>.md`.
3. Preencha status (`[x]`, `[ ]`, `N/A`), evidências e observações.
4. Faça commit do arquivo de run para registrar histórico.

## Convenções recomendadas

- Nome de arquivo de run: `YYYY-MM-DD-ubuntu-ubuntu-server-acceptance.md`
- Sempre registrar:
  - commit/branch testado
  - ambiente (Ubuntu versão, VM/cloud/local)
  - resultado final (`PASS` ou `FAIL`)
  - pendências abertas
