# 15 - Known Bugs / Pendências

## BUG-2026-03-05-001 — Kanban vazio logo após login

**Status:** Aberto (adiado por solicitação do usuário)

### Sintoma
- Após login, a tela do Kanban pode abrir com a lista de projeto mostrando um projeto selecionado,
  mas sem exibir os cards esperados naquele primeiro carregamento.

### Observações
- Há melhora parcial no comportamento com fallback de `project_id`,
  porém ainda existem cenários em que a seleção visual e o dataset carregado divergem no primeiro render.

### Próximos passos sugeridos
1. Instrumentar logs temporários de frontend para capturar:
   - `project_id` na URL
   - `selectedProjectId` retornado por `/api/documents`
   - total de `documents` no primeiro render
2. Instrumentar backend para registrar `selected_project_id` em `GET /api/documents`.
3. Garantir fluxo único no frontend:
   - sem `project_id` na URL => carregar API sem query
   - usar `selectedProjectId` da API
   - sincronizar URL **antes** de filtros/render de colunas
4. Cobrir com teste E2E (login -> primeiro load de Kanban -> assert de cards visíveis).
