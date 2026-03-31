# ProjectDashboard — Checklist de Smoke R1-R3

Objetivo: validar rapidamente os fluxos principais antes de fechar um bloco técnico ou sprint.

## Pré-condições
- Aplicação iniciada
- Usuário válido de teste disponível
- Projeto com pelo menos um documento acessível (se possível)

## Fluxos obrigatórios
- [ ] Login (`/login.html` + `/api/login`)
- [ ] Home / Dashboard (`/`)
- [ ] Projetos (`/projects.html`)
- [ ] Kanban (`/kanban.html`)
- [ ] Configurações (`/settings.html`)
- [ ] Administração de usuários (`/admin-users.html`)
- [ ] Perfil (`/profile.html`)
- [ ] Edit / detalhe (`/edit.html?...`) quando houver documento acessível
- [ ] Sessão autenticada (`/api/me`)

## Scripts de suporte
- Smoke principal: `bash scripts/smoke_r1_r3.sh`
- Navegação/layout base: `bash scripts/test_navigation.sh`
- Regressões RBAC: `PYTHONPATH=. python3 scripts/test_roles_delete_regression.py`
- Lockdown de role inativa: `PYTHONPATH=. python3 scripts/test_inactive_role_lockdown.py`

## Critério de decisão
- **GO:** smoke verde e sem regressão funcional relevante observada
- **BLOQUEADO:** qualquer falha funcional relevante nos fluxos obrigatórios
