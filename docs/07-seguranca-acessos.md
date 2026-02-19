# 07 — Segurança e Controle de Acesso

## Autenticação

- Login por usuário/senha
- Cookie de sessão:
  - `HttpOnly`
  - `SameSite=Lax`
  - TTL de 24h
- Sessões armazenadas em memória no processo Python

## Senhas

- Hash com PBKDF2-HMAC-SHA256
- Salt aleatório por senha
- Não armazenar senha em texto puro

## Autorização (RBAC)

- `member`
  - operações de criação/edição de projeto
- `admin`
  - operações administrativas + exclusões sensíveis

## Regras de proteção

- Bloqueio backend para exclusão de usuários admin
- Bloqueio backend para exclusão do próprio usuário
- Exclusão de usuários com confirmação forte na UI

## Auditoria

Ações críticas são auditadas em `audit_logs`, incluindo:
- create/update/delete de usuário
- create de convite
- create/update/delete de projeto

## Pontos de melhoria recomendados

1. Persistir sessões no banco/Redis (atual: memória)
2. CSRF token para operações mutáveis
3. Políticas de senha (complexidade/expiração)
4. Rotação e invalidação central de sessões
5. Suporte a 2FA para admin
