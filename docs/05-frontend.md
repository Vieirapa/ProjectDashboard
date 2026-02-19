# 05 — Frontend

## Páginas e responsabilidades

- `index.html` / `app.js`
  - dashboard Kanban
  - filtros
  - criação de projeto
  - edição rápida de status/prioridade

- `edit.html` / `edit.js`
  - edição completa de projeto
  - exclusão de projeto (somente admin)

- `login.html` / `login.js`
  - autenticação

- `signup.html` / `signup.js`
  - cadastro com token de convite

- `admin-users.html` / `admin-users.js`
  - criar usuário
  - gerar convite
  - alterar role
  - trocar senha
  - excluir usuário
  - visualizar auditoria

## Sidebar e navegação

A UI segue layout com barra lateral e categorias:
- Workspace
- Administração

Elementos administrativos são ocultados para usuários não-admin no frontend.

## Observação importante

As regras críticas de acesso **não dependem do frontend**. O backend também valida role em endpoints sensíveis.
