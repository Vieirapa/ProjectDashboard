# 20 — Plano Diário de Execução da Sprint

Base: `docs/19-backlog-executavel-sprint-proxima.md`

Objetivo: transformar o backlog da próxima sprint em tarefas técnicas diárias, com entrega incremental e validação contínua.

---

## Visão geral da cadência

- **D1:** Fundamentos de “Documentos Apagados” (filtros + contrato API)
- **D2:** Paginação completa + integração UI
- **D3:** Backup permission check (backend + UI)
- **D4:** Badge de saúde no diagnóstico
- **D5:** Teste E2E de regressão login → Kanban
- **D6:** QA PT-BR + fechamento da sprint

---

## D1 — Filtros em Documentos Apagados (base)

### Meta do dia
Entregar filtros funcionais no backend e primeira versão da UI de filtros.

### Tarefas técnicas
1. **Mapear endpoint atual de deletados**
   - localizar rota e query SQL atual.
   - documentar payload atual (request/response).

2. **Implementar filtros no backend**
   - adicionar parâmetros opcionais:
     - `q` (nome/slug)
     - `deleted_by`
     - `deleted_from`
     - `deleted_to`
   - aplicar filtros com SQL parametrizado (sem concatenação insegura).

3. **Ajustar UI de Configurações (Documentos Apagados)**
   - adicionar campos de filtro.
   - adicionar botões “Filtrar” e “Limpar”.

4. **Garantir fallback sem filtros**
   - manter comportamento atual quando nenhum filtro for enviado.

### Critério de pronto do dia
- Filtros funcionam isolados e combinados em ambiente local.
- Sem regressão na listagem atual.

### Evidências esperadas
- commit com backend+frontend do filtro.
- atualização de notas de teste rápido no PR/arquivo de validação.

---

## D2 — Paginação em Documentos Apagados

### Meta do dia
Entregar paginação backend/frontend integrada aos filtros.

### Tarefas técnicas
1. **Backend paginação**
   - parâmetros: `page`, `page_size` (com max seguro).
   - incluir no response:
     - `total`, `page`, `page_size`, `total_pages`.

2. **Frontend paginação**
   - controles: anterior/próxima e indicador de página.
   - preservar estado de filtros ao trocar página.

3. **Validação de carga**
   - popular dados de teste para validar comportamento com maior volume.

4. **Ajustes de UX**
   - desabilitar botões em limites (primeira/última página).
   - mensagens de “sem resultados” com contexto de filtro.

### Critério de pronto do dia
- Paginação funcional e estável com filtros ativos.
- Metadados corretos no payload.

### Evidências esperadas
- commit de paginação backend/frontend.
- print/log de validação com múltiplas páginas.

---

## D3 — Teste de permissões do caminho de backup

### Meta do dia
Adicionar diagnóstico preventivo de permissão de backup no admin.

### Tarefas técnicas
1. **Novo endpoint de teste**
   - validar existência do caminho.
   - validar escrita (teste seguro sem efeitos colaterais permanentes).
   - retornar status + mensagem + remediação.

2. **Integração na tela de Configurações**
   - botão “Testar permissões do caminho”.
   - feedback de sucesso/erro para usuário final.

3. **Tratamento de erros comuns**
   - caminho inexistente
   - permissão negada
   - erro inesperado de IO

4. **Padronização de mensagens**
   - linguagem clara para operação (sem excesso técnico).

### Critério de pronto do dia
- Admin consegue validar caminho antes de rodar backup.
- Mensagens de remediação orientam ação prática.

### Evidências esperadas
- commit do endpoint + UI.
- validação manual com cenário positivo e negativo.

---

## D4 — Badge de saúde no diagnóstico

### Meta do dia
Transformar diagnóstico em status visual imediato (verde/amarelo/vermelho).

### Tarefas técnicas
1. **Definir regra de severidade**
   - mapear checks críticos, warnings e falhas graves.

2. **Ajustar payload do diagnóstico**
   - incluir severidade final e resumo sintético.

3. **Renderizar badge no frontend**
   - cor + texto + resumo.
   - manter detalhamento técnico no textarea existente.

4. **Casos de validação**
   - cenário “ok”, cenário “warning”, cenário “critical”.

### Critério de pronto do dia
- Badge exibido e coerente com diagnóstico retornado.

### Evidências esperadas
- commit backend/frontend do badge.
- registro dos 3 cenários testados.

---

## D5 — Teste E2E de regressão (login → Kanban)

### Meta do dia
Automatizar proteção contra regressão do primeiro carregamento do Kanban.

### Tarefas técnicas
1. **Criar cenário E2E**
   - login válido
   - navegação para Kanban com projeto ativo
   - assert de render inicial (cards/elementos principais).

2. **Integrar à rotina de regressão**
   - script de execução local/documentado.

3. **Estabilizar teste**
   - reduzir flakiness com waits baseados em estado (não sleep fixo).

4. **Documentar execução**
   - incluir no material de testes/checklist.

### Critério de pronto do dia
- Teste falha quando há regressão e passa no estado atual.

### Evidências esperadas
- commit do teste E2E.
- output de execução “pass”.

---

## D6 — QA PT-BR + Fechamento da sprint

### Meta do dia
Concluir consistência textual da UI e fechar sprint com validação final.

### Tarefas técnicas
1. **Revisão de microcopy**
   - Home, Kanban, Projetos, Perfil, Usuários/Convites, Configurações.
   - corrigir ortografia, acentuação, termos inconsistentes.

2. **Checklist de linguagem**
   - criar checklist em `docs/tests/checklists/` para reutilização futura.

3. **Validação final de perfis**
   - admin, lider_projeto, member/revisor (fluxos principais).

4. **Documento de fechamento da sprint**
   - resumo do que foi entregue
   - pendências remanescentes
   - decisão go/no-go

### Critério de pronto do dia
- UI revisada em PT-BR com checklist salvo.
- sprint encerrada com evidências.

### Evidências esperadas
- commit de QA textual + checklist + relatório de fechamento.

---

## Quadro de controle diário (modelo)

Use este bloco para checkpoint rápido por dia:

- **Dia:** Dn
- **Planejado:**
- **Entregue:**
- **Bloqueios:**
- **Próximo passo:**
- **Status:** on-track | atenção | bloqueado

---

## Meta de entrega por marco (resumo)

- **Marco A (D1–D2):** Documentos Apagados robusto (filtro + paginação)
- **Marco B (D3–D4):** Operação admin mais segura e legível (backup+diagnóstico)
- **Marco C (D5–D6):** Qualidade/estabilidade final (E2E + PT-BR + fechamento)
