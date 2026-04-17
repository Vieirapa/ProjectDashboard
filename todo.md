# TODO — ProjectDashboard

> Arquivo central de trabalho do projeto.
>
> Objetivo: concentrar bugs, melhorias, frentes abertas, débitos técnicos e próximos passos.
>
> Regra operacional: novas ideias, bugs e melhorias futuras devem ser registradas aqui antes ou junto da execução.

## Convenções de classificação

### Tipos
- `bug`: falha funcional, regressão, comportamento incorreto ou incoerente
- `backend`: arquitetura, APIs, banco, regras de negócio, refactor estrutural
- `ux`: interface, fluxo, microcopy, navegação, feedback visual, clareza de uso
- `ops`: deploy, backup, restore, validação operacional, saúde do sistema, runbooks
- `wishlist`: desejos, novas features, melhorias futuras e ideias ainda não priorizadas para execução imediata

### Prioridades
- `P0`: bug crítico, segurança, perda de dados, indisponibilidade, risco alto ao sistema
- `P1`: bug relevante, confiabilidade, operação crítica, UX/UI com impacto direto no uso principal
- `P2`: melhoria importante, evolução estrutural, melhoria operacional não crítica
- `P3`: wishlist, refinamentos, ideias futuras, melhorias não urgentes

### Owners sugeridos
- `Kevin`: implementação backend/código e correções gerais
- `Dave`: desenho/revisão de frontend, UX e fluxos visuais
- `Bob`: revisão crítica, QA, regressão, segurança e confiabilidade
- `Eve`: estruturação, priorização, consolidação e coordenação

## Estado atual do projeto
- Aplicação instalada e validada localmente na VM de desenvolvimento.
- Kevin está atuando como agente principal de codificação.
- Bob é o revisor padrão de alterações do Kevin.
- Dave entra antes da revisão final quando a mudança tiver peso forte de frontend/UX.
- Fluxo recente concluído: melhoria da mensagem de sucesso em `CONFIGURAÇÕES > FLUXO`, já enviada ao GitHub.

## Regras de operação deste arquivo
- Registrar aqui:
  - bugs encontrados
  - ideias de melhoria
  - backlog técnico
  - próximos passos do produto
  - follow-ups de revisão/QA/deploy
- Ao concluir um item importante:
  - marcar status com `[X]`
  - apontar commit/PR quando existir
  - registrar próximo passo ou decisão
- Ao abrir item novo:
  - classificar tipo, prioridade e owner
  - quebrar em subtarefas executáveis
  - posicionar na ordem de prioridade correta

---

## A. Histórico preservado

### A1. Bugs documentados já resolvidos
Source: `docs/15-known-bugs.md`

- [X] [bug][P0][owner: Kevin/Bob] **BUG-2026-03-05-001** Kanban vazio logo após login
  - [X] Correção entregue em 2026-03-08
  - [X] Item preservado apenas para histórico

- [X] [bug][P0][owner: Kevin/Bob] **BUG-2026-03-24-002** Roles apagadas reaparecem após troca de sessão
  - [X] Correção documentalmente resolvida
  - [ ] Manter regressão manual sempre que tocar RBAC/roles

---

## B. Backlog ativo priorizado

> Ordem de execução padrão: P1 primeiro, depois P2, depois P3.
> Dentro de cada prioridade, seguir a ordem listada salvo decisão explícita em contrário.

### B1. Prioridade imediata, ciclo atual

#### B1.1 [P1][ux][owner: Dave/Bob] Validar manualmente a melhoria da mensagem de sucesso em `CONFIGURAÇÕES > FLUXO`
Source: memória recente + código (`web/settings.js`), último commit conhecido `c2a9668`

- [ ] Confirmar comportamento ao salvar sem alterar nada
- [ ] Confirmar comportamento ao mudar só prazo padrão
- [ ] Confirmar comportamento ao mudar só status máximo com dependências pendentes
- [ ] Confirmar comportamento ao mudar ambos
- [ ] Registrar evidência do comportamento observado
- [ ] Decidir: aprovado, ajuste pequeno, ou bug novo

#### B1.2 [P1][ux/backend][owner: Kevin/Dave] Confirmar status real de `Documentos Apagados` (filtros + paginação)
Source: `docs/19-backlog-executavel-sprint-proxima.md`

- [ ] Inspecionar backend atual do módulo de Documentos Apagados
- [ ] Inspecionar frontend atual do módulo de Documentos Apagados
- [ ] Verificar se filtros combinados mantêm resultado consistente
- [ ] Verificar se estado dos filtros é refletido corretamente na UI
- [ ] Verificar se paginação backend usa `page` e `page_size`
- [ ] Verificar se controles anterior/próxima existem e funcionam
- [ ] Verificar se filtros são preservados durante navegação entre páginas
- [ ] Classificar resultado em uma das opções:
  - [ ] já entregue, doc desatualizada
  - [ ] parcialmente entregue, precisa ajuste
  - [ ] ainda pendente, requer implementação
- [ ] Registrar backlog residual exato desta frente

#### B1.3 [P1][ops][owner: Eve] Formalizar preflight de desenvolvimento do Kevin via Claude CLI
Source: memória recente + regra operacional

- [ ] Executar `openclaw models status` antes de novas sessões de desenvolvimento com Kevin
- [ ] Confirmar autenticação válida de `claude-cli` antes de delegar codificação
- [ ] Registrar falha de autenticação como bloqueador operacional quando ocorrer
- [ ] Padronizar esta checagem como etapa fixa do ciclo

### B2. Próxima camada P1, baixo risco e alta utilidade

#### B2.1 [P1][ops][owner: Kevin] Backup, teste preventivo de permissão
Source: `docs/19-backlog-executavel-sprint-proxima.md`

- [ ] Mapear endpoint, backend e tela atual de backup
- [ ] Definir como validar permissão de escrita antes da operação crítica
- [ ] Definir mensagem de erro com remediação clara para operador
- [ ] Implementar validação preventiva
- [ ] Validar comportamento em cenário permitido
- [ ] Validar comportamento em cenário sem permissão
- [ ] Registrar evidência e risco residual

#### B2.2 [P1][ops][owner: Kevin/Bob] Diagnóstico e saúde operacional, classificação de severidade
Source: `docs/19-backlog-executavel-sprint-proxima.md`

- [ ] Revisar lógica atual de health/status
- [ ] Identificar estados possíveis e sua severidade real
- [ ] Definir critérios explícitos por severidade
- [ ] Ajustar mensagens para orientar a próxima ação operacional
- [ ] Validar com Bob risco de falso positivo ou falso negativo
- [ ] Registrar regra final adotada

#### B2.3 [P1][ux][owner: Dave/Bob] QA linguístico e microcopy
Source: `docs/tests/checklists/projectdashboard-qa-linguagem-ptbr.md`

- [ ] Aplicar checklist de linguagem pt-BR nas telas de admin
- [ ] Aplicar checklist de linguagem pt-BR nas telas de kanban
- [ ] Identificar problemas de ortografia e acentuação
- [ ] Identificar termos inconsistentes entre telas
- [ ] Identificar mensagens sem orientação clara de próxima ação
- [ ] Consolidar backlog de correções de microcopy
- [ ] Priorizar correções rápidas vs correções estruturais

### B3. Frentes estruturais P1 e P2

#### B3.1 [P1][backend][owner: Kevin/Bob] Consolidar evolução do sistema de roles e permissões
Source: `docs/21-role-module-access-control-plan.md`, `docs/22-technical-execution-plan-role-modules.md`, `docs/26-rbac-module-first-custom-roles.md`, `docs/ROLE_SYSTEM_REFACTOR_PLAN.md`

- [ ] Revisar status real da implementação contra as docs
- [ ] Listar o que já foi entregue com evidência em código
- [ ] Listar o que permanece apenas como plano
- [ ] Identificar riscos funcionais ainda abertos
- [ ] Priorizar somente gaps que ainda geram risco real
- [ ] Definir próximo pacote incremental de execução
- [ ] Garantir regressão manual para role admin e exclusão de roles

#### B3.2 [P2][backend][owner: Kevin/Bob] Modularização backend incremental
Source: `docs/29-backend-evolution-boundaries.md`, `docs/31-sprint-r1-r3-robustez-base.md`

- [ ] Identificar blocos de menor risco em `app.py`
- [ ] Escolher primeiro recorte incremental de extração
- [ ] Definir teste mínimo/regressão para esse recorte
- [ ] Executar extração em commit pequeno
- [ ] Validar fluxos críticos após cada extração
- [ ] Registrar limites de acoplamento encontrados
- [ ] Planejar próximo recorte somente após validação

#### B3.3 [P2][backend][owner: Kevin/Bob] Consolidar estado de exportação e arquivamento
Source: `docs/27-project-export-archive-spec-v1.md`, `docs/28-project-export-archive-phase-breakdown-v1.md`, `docs/36-project-export-archive-v1.md`

- [ ] Validar estado real atual do recurso no código
- [ ] Validar estado real atual do recurso na VM
- [ ] Confirmar export com arquivos reais no ZIP
- [ ] Confirmar comportamento de archive no fluxo atual
- [ ] Identificar gaps restantes de UX
- [ ] Identificar gaps restantes de validação
- [ ] Decidir se import futura entra no backlog agora ou depois
- [ ] Organizar backlog residual desta frente

#### B3.4 [P2][ux][owner: Dave] Direção de modernização incremental da UI
Source: `docs/30-ui-modernization-direction.md`

- [ ] Revisar dashboard como base visual
- [ ] Identificar melhorias de hierarquia visual de menor risco
- [ ] Identificar ações principais mal destacadas
- [ ] Propor baseline visual para próximas telas
- [ ] Preparar `projects` como próxima tela de referência
- [ ] Separar melhorias cosméticas de melhorias de usabilidade

### B4. Operação, QA e readiness

#### B4.1 [P2][ops][owner: Kevin/Bob] Plano de testes de restore e backup recovery
Source: `docs/TODO-restore-tests.md`

- [ ] Revisar plano atual de restore
- [ ] Separar tarefas em checklist operacional vs implementação
- [ ] Identificar pré-requisitos reais para teste seguro de recovery
- [ ] Executar ou simular fluxo mínimo de recuperação
- [ ] Registrar evidência prática, lacunas e próximos passos
- [ ] Decidir se esta frente vira sprint própria ou rotina operacional

#### B4.2 [P2][ops][owner: Eve/Bob] Institucionalizar uso dos checklists de smoke e QA
Source:
- `docs/tests/checklists/projectdashboard-smoke-r1-r3.md`
- `docs/tests/checklists/projectdashboard-qa-linguagem-ptbr.md`
- `docs/tests/checklists/ubuntu-ubuntu-server-acceptance-checklist.md`

- [ ] Definir checklist mínima para mudanças de backend funcional
- [ ] Definir checklist mínima para mudanças de frontend/UX
- [ ] Definir checklist mínima para mudanças de deploy/operação
- [ ] Registrar regra de uso após mudanças relevantes
- [ ] Garantir que evidência de execução fique anexável ao histórico

#### B4.3 [P2][ops][owner: Eve/Bob] Consolidar critério atual de release readiness
Source:
- `docs/16-release-readiness-2026-03-05.md`
- `docs/24-release-checklist-roles-delete-fix-2026-03-24.md`
- `docs/32-sprint-operacional-fechamento-2026-03-31.md`
- `docs/35-r1-fechamento-2026-03-31.md`

- [ ] Revisar critérios existentes nas docs de readiness
- [ ] Consolidar critérios ainda válidos
- [ ] Remover critérios obsoletos ou duplicados
- [ ] Criar checklist única de go/no-go para o estado atual do produto
- [ ] Definir responsáveis por evidência de cada bloco crítico

### B5. Wishlist e triagem futura

#### B5.1 [P3][wishlist][owner: Eve] Revisar wishlist oficial e promover itens maduros
Source: `docs/13-future-wishlist.md`

- [ ] Revisar wishlist completa
- [ ] Separar itens de curto prazo
- [ ] Separar itens de médio prazo
- [ ] Separar parking lot
- [ ] Promover para backlog executável apenas itens maduros

---

## C. Próxima decisão de ciclo

### C1. Ordem recomendada de execução
- [ ] Validar manualmente a correção recente do bloco `CONFIGURAÇÕES > FLUXO`
- [ ] Confirmar status real de `Documentos Apagados` (filtros + paginação)
- [ ] Fechar preflight operacional do Kevin via Claude CLI
- [ ] Escolher próxima frente entre:
  - [ ] robustez operacional e admin
  - [ ] modularização backend
  - [ ] UX/UI incremental

### C2. Próxima frente recomendada por menor risco
- [ ] QA linguístico e microcopy
- [ ] backup permission test
- [ ] health e diagnóstico operacional

### C3. Próxima frente recomendada por impacto estrutural
- [ ] modularização backend incremental
- [ ] consolidação RBAC/module-first
- [ ] backlog residual de export/archive

---

## D. Inbox rápida para novos itens

> Registrar aqui primeiro, classificar depois.

- [ ] [wishlist][P3][owner: Eve]
- [ ] [wishlist][P3][owner: Eve]
- [ ] [wishlist][P3][owner: Eve]

---

## E. Decisões operacionais registradas
- Eve estrutura o trabalho.
- Kevin codifica.
- Bob revisa por padrão.
- Dave entra antes quando houver forte impacto de frontend/UX.
- Antes de usar Kevin em sessão de desenvolvimento, verificar autenticação do Claude CLI.
- Quando um work package for concluído e o usuário pedir envio ao GitHub, o fechamento padrão é `push + verificação`.
- Este arquivo passa a ser a trilha principal de acompanhamento de execução, com `[ ]` para pendente e `[X]` para entregue.
