# 10 — Mapa de Arquivos e Responsabilidades

## Backend

- `app.py`
  - servidor HTTP
  - rotas API
  - autenticação/sessão
  - RBAC
  - persistência SQLite
  - auditoria

## Frontend

- `web/index.html` + `web/app.js`
  - tela principal Kanban
- `web/edit.html` + `web/edit.js`
  - edição de projeto
- `web/login.html` + `web/login.js`
  - autenticação
- `web/signup.html` + `web/signup.js`
  - cadastro com convite
- `web/admin-users.html` + `web/admin-users.js`
  - administração de usuários e auditoria
- `web/styles.css`
  - layout global (sidebar, painéis, tabelas)

## Dados

- `data/projectdashboard.db`
  - estado persistente do sistema

## Documentação

- `docs/*.md`
  - documentação técnica e operacional
