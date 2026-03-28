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

---

## BUG-2026-03-24-002 — Roles apagadas reaparecem após troca de sessão

**Status:** Resolvido em 2026-03-24

### Sintoma
- Admin apaga `member` e `desenhista` em **Controle de Roles**.
- Após navegar/logar com outro usuário (ex.: `diretor`) e voltar ao admin, as roles reapareciam.

### Causa raiz
- Fontes legadas (`role_modules` e sincronizações de foundation) podiam reintroduzir roles removidas.
- Limpeza incompleta quando existiam variações com espaços/casing em dados legados.

### Correção aplicada
- Tabela de tombstone `deleted_roles` para bloquear ressureição automática de role removida.
- Delete de vínculos legados com `LOWER(TRIM(...))` (case-insensitive + trim).
- Bloqueio de recriação implícita em atualização de permissões para roles tombstonadas.
- Teste de regressão ampliado para cobrir cenário legado.

### Evidência
- Commit: `a60f594` (`fix(roles): prevent legacy sources from resurrecting deleted roles`)
- Teste automatizado: `scripts/test_roles_delete_regression.py` (3 testes, OK)
- QA manual do usuário: fluxo completo aprovado em 2026-03-24.
