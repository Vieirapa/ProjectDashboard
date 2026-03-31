# 33 — R1 Robustez Base — Tarefas Executáveis

Base de referência:
- `docs/31-sprint-r1-r3-robustez-base.md`
- `docs/29-backend-evolution-boundaries.md`
- `docs/30-ui-modernization-direction.md`
- `docs/32-sprint-operacional-fechamento-2026-03-31.md`

## Objetivo do R1

Consolidar a base atual para que backend, installer e UI modernizada fiquem mais seguros para continuar evoluindo, sem regressão aberta e com smoke test como gate obrigatório.

---

## Princípios operacionais do R1

1. Entregas pequenas, reversíveis e auditáveis.
2. Cada bloco fecha com smoke test.
3. Não avançar com regressão funcional aberta.
4. Priorizar robustez real acima de “embelezamento”.

---

## Sequência executável recomendada

### Bloco R1.1 — Auditoria rápida de consistência visual/funcional
**Objetivo:** identificar e corrigir pequenas quebras de consistência nas telas principais, sem redesign amplo.

#### Tarefas
1. Revisar visual e comportamento das telas:
   - dashboard/home
   - projects
   - kanban
   - edit/details
   - settings
   - admin-users
   - profile
2. Mapear inconsistências de:
   - espaçamento
   - títulos/subtítulos
   - ações primárias/secundárias
   - estados vazios
   - mensagens de erro/sucesso
3. Corrigir os desvios de baixo risco direto em HTML/CSS/JS.

#### Definition of Done
- Telas principais com padrão visual mais consistente.
- Nenhuma quebra de navegação ou renderização.
- Smoke test passando.

#### Estimativa
- Pequeno/Médio

---

### Bloco R1.2 — Hardening do shell autenticado
**Objetivo:** consolidar sidebar/header/containers como base estável do produto.

#### Tarefas
1. Revisar `web/styles.css` para reduzir regras ad hoc do shell.
2. Padronizar:
   - header de página
   - containers principais
   - grids base
   - cards/panels administrativos
3. Validar comportamento visual mínimo em resoluções menores.
4. Garantir consistência entre páginas autenticadas.

#### Definition of Done
- Shell autenticado parece uma base única e previsível.
- Menos variação estrutural entre páginas.
- Navegação preservada.
- Smoke test + teste de navegação passando.

#### Estimativa
- Médio

---

### Bloco R1.3 — Fechar fragilidades conhecidas de UX operacional
**Objetivo:** transformar pontos “quase bons” em fluxos mais robustos para uso real.

#### Tarefas
1. Refinar feedbacks de backup/restore/diagnóstico.
2. Tornar leitura do diagnóstico mais imediata quando houver warnings/falhas.
3. Revisar estados vazios e mensagens acionáveis nas áreas administrativas.
4. Padronizar confirmações de ações destrutivas.

#### Definition of Done
- Usuário entende melhor o estado atual e a próxima ação.
- Menos mensagens ambíguas.
- Fluxos administrativos mais previsíveis.

#### Estimativa
- Pequeno/Médio

---

### Bloco R1.4 — Formalizar checklist de smoke e evidência por sprint
**Objetivo:** tornar a disciplina de validação parte do processo, não memória informal.

#### Tarefas
1. Criar checklist curto reutilizável de smoke das telas obrigatórias.
2. Criar modelo de registro de execução por sprint.
3. Referenciar scripts já existentes:
   - `scripts/smoke_r1_r3.sh`
   - `scripts/test_navigation.sh`
4. Definir convenção de “go / bloqueado”.

#### Definition of Done
- Há checklist simples para reuso.
- Há modelo de evidência por execução.
- Processo de fechamento de sprint fica repetível.

#### Estimativa
- Pequeno

---

### Bloco R1.5 — Revisão do installer / redeploy sem regressão de operação
**Objetivo:** garantir que evolução de UI/base não comprometa instalação e atualização.

#### Tarefas
1. Revisar `install.sh` e `scripts/redeploy_dev_vm.sh` contra a estrutura atual.
2. Validar se docs de deploy continuam alinhados com o projeto.
3. Ajustar inconsistências pequenas de operação/documentação.

#### Definition of Done
- Fluxo de instalação/redeploy continua coerente.
- Sem divergência gritante entre docs e comportamento esperado.

#### Estimativa
- Pequeno/Médio

---

### Bloco R1.6 — Fechamento do R1
**Objetivo:** encerrar R1 com evidência objetiva e sem regressão aberta.

#### Tarefas
1. Rodar:
   - validação sintática relevante
   - testes de regressão disponíveis
   - smoke test
2. Registrar resultado final.
3. Listar qualquer pendência residual não bloqueante.
4. Declarar pronto para avançar a modularização backend.

#### Definition of Done
- Smoke test final passando.
- Registro de fechamento criado.
- Próxima etapa destravada.

#### Estimativa
- Pequeno

---

## Ordem recomendada de execução

1. **R1.1** Auditoria rápida de consistência visual/funcional
2. **R1.2** Hardening do shell autenticado
3. **R1.3** Fragilidades de UX operacional
4. **R1.4** Checklist/evidência de smoke
5. **R1.5** Installer/redeploy/docs operacionais
6. **R1.6** Fechamento do R1

---

## Gate obrigatório ao final de cada bloco

Executar no mínimo:
- `python3 -m py_compile app.py`
- `node --check web/settings.js`
- `PYTHONPATH=. python3 scripts/test_roles_delete_regression.py`
- `PYTHONPATH=. python3 scripts/test_inactive_role_lockdown.py`
- `./scripts/smoke_r1_r3.sh`

Quando o bloco não tocar navegação/layout base, o teste de navegação pode ser opcional.
Quando tocar shell/layout/sidebar, incluir também:
- `./scripts/test_navigation.sh`

---

## Riscos do R1

- Corrigir visual e sem querer gerar regressão funcional.
- Aumentar escopo tentando “modernizar demais”.
- Misturar robustez base com modularização backend cedo demais.

### Mitigação
- Commits pequenos.
- Gate de smoke frequente.
- Não abrir refactor estrutural profundo dentro do R1.

---

## Saída esperada do R1

Ao final do R1, o ProjectDashboard deve estar com:
- telas principais mais coesas
- shell autenticado mais sólido
- UX operacional mais previsível
- disciplina de smoke/fechamento mais clara
- base pronta para iniciar modularização backend com menos risco
