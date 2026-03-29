# 31 — Sprint Plan R1 → R3 (Robustez Base)

## Objetivo central

Transformar o ProjectDashboard de uma aplicação funcional monolítica em amadurecimento para uma plataforma operacional profissional, com:

- base técnica modular
- UX consistente
- deploy e evolução mais previsíveis
- capacidade real de absorver novas funcionalidades sem colapsar

---

## Regra operacional aprovada

Para executar R1 → R3:

1. Cada sprint deve terminar com smoke test.
2. Se smoke test falhar, corrigir antes de avançar.
3. Não avançar para o sprint seguinte com regressão aberta.
4. Preferir mudanças incrementais, auditáveis e reversíveis.

---

## Sprint R1 — Robustez Base

### Objetivo
Consolidar a base atual para que backend, installer e UI modernizada fiquem mais seguros para continuar evoluindo.

### Escopo
- QA e ajustes finos da UI modernizada
- hardening do layout base
- limpeza de pontos frágeis conhecidos
- preparação documental/operacional para modularização contínua
- smoke test validando fluxo principal

### Entregas-alvo
- checklist de smoke validado
- correções finas de consistência visual/funcional
- installer e redeploy preservados
- UI principal navegável e consistente

---

## Sprint R2 — Modularização e Evolução Segura

### Objetivo
Expandir a modularização do backend e preparar a base para crescimento com menos acoplamento.

### Escopo
- continuar extração por domínio
- preparar base de migrations versionadas
- reduzir responsabilidade direta de `app.py`
- melhorar previsibilidade do schema
- smoke test validando integridade após refactor

### Entregas-alvo
- novos módulos extraídos
- plano ou base executável de migrations
- `app.py` mais focado em composição/rotas

---

## Sprint R3 — Robustez Funcional do Domínio

### Objetivo
Fortalecer os subdomínios centrais para absorver novas funcionalidades com menos regressão.

### Escopo
- consolidar RBAC avançado
- revisar review notes
- revisar dependencies / lifecycle do documento
- revisar recoverable docs / reports em termos de consistência
- smoke test cobrindo fluxos críticos

### Entregas-alvo
- regras centrais mais explícitas
- menos espalhamento de lógica sensível
- fluxo funcional principal mais robusto

---

## Smoke test mínimo ao final de cada sprint

1. login
2. dashboard/home
3. projects
4. kanban
5. edit/details
6. settings
7. admin-users
8. profile

### Critério de bloqueio
Qualquer falha funcional relevante nesses fluxos bloqueia avanço para o próximo sprint.
