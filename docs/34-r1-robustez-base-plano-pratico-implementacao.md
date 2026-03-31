# 34 — R1 Robustez Base — Plano Prático de Implementação

Base de referência:
- `docs/33-r1-robustez-base-tarefas-executaveis.md`
- `docs/31-sprint-r1-r3-robustez-base.md`
- `docs/29-backend-evolution-boundaries.md`
- `docs/30-ui-modernization-direction.md`

## Objetivo deste documento

Transformar os blocos do R1 em um plano mais operacional, com:
- estratégia de implementação por bloco
- ordem prática de execução
- arquivos prováveis de mudança
- riscos por bloco
- critérios objetivos de sucesso
- métricas simples para avaliar se o bloco realmente entregou robustez

---

## Regra de execução do R1

Cada bloco deve seguir o mesmo ciclo:

1. mapear o estado atual
2. fazer mudanças pequenas e reversíveis
3. validar visual/funcionalmente
4. rodar o gate mínimo de testes
5. registrar o que mudou

### Gate mínimo recorrente
- `python3 -m py_compile app.py`
- `node --check web/*.js` (ao menos os arquivos tocados)
- `PYTHONPATH=. python3 scripts/test_roles_delete_regression.py`
- `PYTHONPATH=. python3 scripts/test_inactive_role_lockdown.py`
- `bash scripts/smoke_r1_r3.sh`

Quando houver mudança em shell/sidebar/layout base, incluir também:
- `bash scripts/test_navigation.sh`

---

# BLOCO R1.1 — Auditoria rápida de consistência visual/funcional

## Objetivo
Corrigir pequenas incoerências nas telas principais sem entrar em redesign amplo.

## Estratégia de implementação

### Etapa 1 — Criar inventário rápido das telas principais
Telas-alvo:
- `web/index.html`
- `web/projects.html`
- `web/kanban.html`
- `web/edit.html`
- `web/settings.html`
- `web/admin-users.html`
- `web/profile.html`

Para cada uma, revisar:
- estrutura do header
- hierarquia de título/subtítulo
- posição da ação principal
- padrão de cards/panels
- estados vazios
- feedbacks textuais
- alinhamento de botões

### Etapa 2 — Classificar inconsistências em 3 níveis
- **Nível A:** quebra visível clara (layout desalinhado, header inconsistente, ação sem destaque)
- **Nível B:** inconsistência de acabamento (spacing, tipografia, rótulo, botão)
- **Nível C:** refinamento cosmético sem impacto relevante

Implementar primeiro A, depois B. C só entra se o custo for muito baixo.

### Etapa 3 — Padronizar o mínimo comum
Convergir para padrões únicos de:
- page header
- subtitle/help text
- bloco de ação principal
- feedback inline
- empty state

## Arquivos prováveis
- `web/index.html`
- `web/projects.html`
- `web/kanban.html`
- `web/edit.html`
- `web/settings.html`
- `web/admin-users.html`
- `web/profile.html`
- `web/styles.css`

## Riscos
- Corrigir uma tela e criar divergência em outra.
- Ajustar markup demais e gerar regressão JS.
- Misturar consistência com redesign excessivo.

## Estratégia de mitigação
- Alterações em pequenos lotes.
- Sempre validar a tela tocada e pelo menos mais uma tela não tocada.
- Evitar renomear IDs usados por JS sem necessidade.

## Métricas de sucesso

### Métricas visuais/funcionais
- 100% das 7 telas principais com header coerente entre si.
- 100% das telas com ação principal identificável sem ambiguidade.
- 100% das telas com estados vazios legíveis onde aplicável.
- 0 regressão de navegação nas telas principais.

### Sinal qualitativo esperado
- O produto parece mais uniforme sem parecer retrabalhado do zero.

## Critério objetivo de aceite
- Revisão das 7 telas concluída.
- Inconsistências Nível A zeradas.
- Inconsistências Nível B reduzidas ao mínimo aceitável.
- `test_navigation.sh` e smoke passando.

---

# BLOCO R1.2 — Hardening do shell autenticado

## Objetivo
Consolidar sidebar, header e containers como fundação estável do produto autenticado.

## Estratégia de implementação

### Etapa 1 — Identificar regras ad hoc do shell
Mapear no `web/styles.css`:
- regras duplicadas
- espaçamentos arbitrários
- estilos específicos de página que deveriam ser compartilhados
- diferenças entre containers equivalentes

### Etapa 2 — Criar fundação explícita
Padronizar classes e comportamento para:
- layout principal autenticado
- sidebar
- content shell
- page header
- section/panel/card base
- grids administrativos

### Etapa 3 — Validar responsividade mínima
Sem buscar mobile-first completo agora. Apenas garantir:
- leitura razoável em larguras menores
- botões não quebrando de forma grotesca
- headers e actions reorganizando sem colidir

## Arquivos prováveis
- `web/styles.css`
- `web/sidebar.js`
- `web/sidebar-project-select.js`
- HTMLs autenticados que usem shell comum

## Riscos
- CSS global impactar telas antigas de forma lateral.
- Refino estrutural quebrar espaçamento de componentes específicos.
- Sidebar/header ficar melhor em uma tela e pior em outra.

## Estratégia de mitigação
- Fazer primeiro extração/organização de CSS, depois ajustes visuais.
- Testar pelo menos dashboard, settings e kanban a cada lote.
- Preservar classes existentes quando possível; adicionar novas antes de remover antigas.

## Métricas de sucesso

### Métricas estruturais
- Redução perceptível de regras duplicadas/ad hoc no shell.
- 100% das páginas autenticadas com mesma fundação visual de header/container.
- Sidebar estável e previsível em todas as páginas principais.

### Métricas de validação
- `test_navigation.sh` passando.
- Smoke passando.
- Nenhuma página principal com overflow/quebra visual evidente em viewport intermediária.

## Critério objetivo de aceite
- Shell autenticado reconhecível como uma base única.
- Sem divergência gritante entre pages core.
- Navegação e layout preservados após mudanças.

---

# BLOCO R1.3 — Fechar fragilidades conhecidas de UX operacional

## Objetivo
Melhorar os fluxos administrativos e operacionais que já funcionam, mas ainda podem causar dúvida, atrito ou percepção de fragilidade.

## Estratégia de implementação

### Etapa 1 — Priorizar fluxos mais críticos
Ordem sugerida:
1. backup / restore
2. diagnóstico
3. documentos recuperáveis
4. confirmações destrutivas
5. feedbacks gerais de sucesso/erro

### Etapa 2 — Revisar a lógica de mensagem e estado
Perguntas para cada fluxo:
- O usuário entende o que acabou de acontecer?
- O usuário entende o que fazer se falhar?
- O texto diferencia warning, erro e sucesso?
- A ação perigosa parece realmente perigosa?

### Etapa 3 — Refinar sem trocar comportamento funcional
O foco aqui não é refatorar domínio, e sim:
- melhorar microcopy
- melhorar clareza do feedback
- melhorar previsibilidade do estado da tela
- tornar erros mais acionáveis

## Arquivos prováveis
- `web/settings.js`
- `web/settings.html`
- `web/styles.css`
- eventualmente pequenos ajustes em `app.py` se algum payload precisar ficar mais claro

## Riscos
- Mudar texto e mascarar erro real.
- Aumentar ruído visual com excesso de feedback.
- Abrir refactor backend desnecessário para resolver detalhe de UX.

## Estratégia de mitigação
- Alterar primeiro UI/mensagens.
- Só tocar payload backend quando o problema for realmente de contrato/dados.
- Preferir mensagens curtas + remediação clara.

## Métricas de sucesso

### Métricas de UX operacional
- 100% dos fluxos críticos com mensagem explícita de sucesso/erro.
- 100% das ações destrutivas com confirmação clara.
- 100% dos erros operacionais críticos com orientação de próxima ação.

### Exemplos de aferição
- Backup: usuário sabe onde foi salvo ou por que falhou.
- Restore: usuário entende risco + confirmação necessária.
- Diagnóstico: usuário distingue estado saudável vs atenção.
- Recuperáveis: usuário entende se a lista está vazia, filtrada ou indisponível.

## Critério objetivo de aceite
- Fluxos administrativos principais testados manualmente sem ambiguidade relevante.
- Mensagens genéricas ou confusas reduzidas ao mínimo.
- Smoke passando após os ajustes.

---

# BLOCO R1.4 — Formalizar checklist de smoke e evidência por sprint

## Objetivo
Transformar validação recorrente em processo explícito e repetível.

## Estratégia de implementação

### Etapa 1 — Criar checklist enxuto e reutilizável
Cobrir o mínimo obrigatório:
- login
- home/dashboard
- projects
- kanban
- edit/details
- settings
- admin-users
- profile

### Etapa 2 — Criar modelo de evidência
Registrar por execução:
- data
- branch/commit
- scripts rodados
- resultado
- bloqueios encontrados
- decisão final: go ou bloqueado

### Etapa 3 — Ligar o checklist aos scripts reais
Referenciar explicitamente:
- `scripts/smoke_r1_r3.sh`
- `scripts/test_navigation.sh`
- testes Python de regressão relevantes

## Arquivos prováveis
- `docs/tests/checklists/...`
- `docs/tests/runs/...`
- `docs/tests/README.md`

## Riscos
- Criar checklist burocrático demais.
- Duplicar informação sem utilidade operacional.
- Virar documento que ninguém consulta.

## Estratégia de mitigação
- Mantê-lo curto.
- Focar em decisão operacional, não em “papelada”.
- Reaproveitar scripts existentes em vez de criar processo paralelo.

## Métricas de sucesso

### Métricas de processo
- Existe 1 checklist padrão reutilizável.
- Existe 1 template simples de run.
- Toda sprint/R1 increment pode ser fechada com o mesmo padrão.

### Sinal qualitativo esperado
- Qualquer pessoa do projeto consegue entender rapidamente se o incremento está “go” ou “bloqueado”.

## Critério objetivo de aceite
- Checklist criado.
- Template de run criado.
- Um exemplo real de execução registrado.

---

# BLOCO R1.5 — Revisão do installer / redeploy sem regressão de operação

## Objetivo
Garantir que a evolução da base não quebre a operação de instalação e atualização.

## Estratégia de implementação

### Etapa 1 — Revisão cruzada código vs docs
Comparar:
- `install.sh`
- `scripts/redeploy_dev_vm.sh`
- `scripts/upgrade_from_github.sh`
- docs de operação/deploy

Checar principalmente:
- caminhos esperados
- nomes de arquivos e serviços
- variáveis de ambiente
- dependências assumidas
- smoke pós-instalação

### Etapa 2 — Corrigir divergências pequenas
Exemplos:
- texto/documentação desatualizada
- referência a caminho antigo
- instrução de operação inconsistente
- parâmetros de script não documentados

### Etapa 3 — Validar fluxo mínimo
Não precisa fazer instalação full em toda iteração, mas deve validar coerência operacional.

## Arquivos prováveis
- `install.sh`
- `scripts/redeploy_dev_vm.sh`
- `scripts/upgrade_from_github.sh`
- `docs/08-operacao-deploy.md`
- `README.md`
- docs correlatas de operação

## Riscos
- Tocar script operacional sem necessidade real.
- Melhorar docs mas esquecer comportamento real.
- Introduzir “limpeza” que afeta upgrade path.

## Estratégia de mitigação
- Tratar mudanças de script como conservadoras.
- Preferir alinhar docs primeiro quando o comportamento real estiver correto.
- Se tocar script, validar cenários mínimos e registrar claramente.

## Métricas de sucesso

### Métricas operacionais
- 0 divergência crítica entre script principal e documentação oficial.
- Parâmetros principais de install/redeploy/upgrade documentados.
- Smoke continua sendo o gate operacional oficial.

## Critério objetivo de aceite
- Scripts principais revisados.
- Docs operacionais alinhadas.
- Nenhum gap crítico aberto para install/redeploy conhecido.

---

# BLOCO R1.6 — Fechamento do R1

## Objetivo
Encerrar R1 com evidência objetiva, sem regressões abertas e com base preparada para modularização backend.

## Estratégia de implementação

### Etapa 1 — Consolidar o que foi entregue
Registrar:
- melhorias visuais/estruturais
- UX operacional refinada
- checklist/processo de smoke institucionalizado
- ajustes operacionais/deploy aplicados

### Etapa 2 — Rodar gate final completo
Rodar:
- sintaxe Python relevante
- sintaxe JS relevante
- regressões Python existentes
- navegação (se shell foi tocado)
- smoke completo

### Etapa 3 — Registrar pendências remanescentes
Separar claramente:
- pendência bloqueante
- pendência não bloqueante
- itens que pertencem à fase seguinte (modularização)

## Arquivos prováveis
- `docs/` de fechamento do R1
- eventualmente `CHANGELOG.md`
- evidência em `docs/tests/runs/...`

## Riscos
- Declarar pronto com regressão escondida.
- Misturar fechamento do R1 com início da modularização.
- Não deixar claro o que ficou para a fase seguinte.

## Estratégia de mitigação
- Gate final obrigatório.
- Documento de fechamento curto e objetivo.
- Critério explícito para “pronto para modularização”.

## Métricas de sucesso

### Métricas de saída
- Smoke final PASS.
- Navegação PASS (se aplicável).
- 0 regressão funcional relevante aberta nas telas principais.
- Próxima etapa definida com fronteira clara.

## Critério objetivo de aceite
- Documento de fechamento do R1 criado.
- Gate final verde.
- Time consegue iniciar modularização backend sem voltar para apagar incêndio visual/operacional.

---

# Ordem prática sugerida de execução

## Ordem macro
1. R1.1
2. R1.2
3. R1.3
4. R1.4
5. R1.5
6. R1.6

## Ordem micro recomendada

### Primeiro ciclo
- R1.1 em lote pequeno
- smoke

### Segundo ciclo
- R1.2 shell/base
- test_navigation + smoke

### Terceiro ciclo
- R1.3 UX operacional
- smoke

### Quarto ciclo
- R1.4 processo/checklists
- validação documental

### Quinto ciclo
- R1.5 operação/deploy
- smoke se houver impacto relevante

### Sexto ciclo
- R1.6 fechamento

---

# Métrica global de sucesso do R1

Ao final do R1, considerar sucesso se:

1. **Produto mais coeso**
   - páginas principais parecem parte do mesmo sistema

2. **Operação mais previsível**
   - fluxos de settings/admin geram menos dúvida

3. **Validação mais institucionalizada**
   - smoke/checklists/evidências deixam de depender de memória informal

4. **Base pronta para modularização**
   - não há necessidade de voltar para resolver fragilidade visual/operacional básica antes do backend refactor

---

# Recomendação prática final

Se a ideia for maximizar ganho com menor risco, começar por:
- **R1.1 + R1.2 juntos em escopo controlado**
- depois **R1.3**
- depois fechar processo/documentação com **R1.4** e **R1.5**

Essa ordem entrega robustez perceptível primeiro, sem abrir refactor estrutural cedo demais.
