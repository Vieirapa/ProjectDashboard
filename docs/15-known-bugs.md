# 15 - Known Bugs / Pendências

## BUG-2026-03-05-001 — Kanban vazio logo após login

**Status:** Resolvido em 2026-03-08 (landing + rota dedicada de Kanban + sincronização de navegação)

### Sintoma
- Após login, a tela do Kanban pode abrir com a lista de projeto mostrando um projeto selecionado,
  mas sem exibir os cards esperados naquele primeiro carregamento.

### Observações
- O fluxo foi estabilizado ao separar landing (`/`) e Kanban (`/kanban.html`).
- A sincronização de `project_id` passou a ocorrer antes do render principal.

### Ação de prevenção
- Manter teste E2E de login + primeiro carregamento de Kanban no ciclo de regressão.
