# 01 — Visão Geral

## Objetivo do sistema

O **ProjectDashboard** é uma aplicação web para gestão de projetos em formato Kanban, com:
- autenticação por usuário
- níveis de acesso (admin/member)
- administração de usuários
- convites de cadastro
- auditoria de ações

## Funcionalidades principais (estado atual)

- Kanban com colunas: Backlog, Em andamento, Bloqueado, Concluído
- Criação de projetos pela interface
- Edição completa de projetos em página dedicada
- Filtros por texto, status, prioridade e responsável
- Administração:
  - criar usuário
  - alterar role (admin/member)
  - trocar senha de usuário
  - excluir usuário (com restrições)
  - gerar link de convite
  - visualizar log de auditoria

## Regras de negócio de acesso

- **admin**
  - acesso ao painel de administração
  - gerencia usuários e convites
  - pode excluir projetos
- **member**
  - cria e edita projetos
  - não acessa admin
  - não exclui projetos

## Regras de exclusão de usuários

- Exclusão permitida apenas para admin
- Não é permitido excluir:
  - o próprio usuário logado
  - usuários com role `admin`
- UI aplica confirmação em duas etapas:
  1. `confirm()`
  2. digitação de `EXCLUIR`
- UI mostra número de tarefas/projetos associados (campo `owner`)
