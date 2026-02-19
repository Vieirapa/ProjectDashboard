# 04 — API (referência)

## Auth / Sessão

### `POST /api/login`
Login.

Body:
```json
{ "username": "admin", "password": "admin123" }
```

Resposta:
```json
{ "ok": true, "user": { "username": "admin", "role": "admin" } }
```

### `POST /api/logout`
Encerra sessão.

### `GET /api/me`
Retorna usuário atual da sessão.

---

## Projetos

### `GET /api/projects`
Lista projetos (auth required).

### `GET /api/projects/:slug`
Detalhe de projeto + enums (`statuses`, `priorities`).

### `POST /api/projects`
Cria projeto (auth required).

Campos aceitos:
- `name`
- `description`
- `status`
- `priority`
- `owner`
- `dueDate`

### `PATCH /api/projects/:slug`
Atualiza projeto (auth required).

### `DELETE /api/projects/:slug`
Exclui projeto (**admin only**).

---

## Administração

### `GET /api/admin/users`
Lista usuários (admin only), incluindo:
- `username`
- `role`
- `created_at`
- `associated_tasks` (contagem de projetos com `owner=username`)

### `POST /api/admin/users`
Cria usuário (admin only).

### `PATCH /api/admin/users/:username`
Atualiza usuário (admin only):
- `role`
- `password`

### `DELETE /api/admin/users/:username`
Exclui usuário (admin only), com regras:
- não pode excluir a si mesmo
- não pode excluir usuário admin

### `POST /api/admin/invites`
Gera convite (admin only).

Body:
```json
{ "role": "member" }
```

Resposta inclui `inviteUrl`.

### `GET /api/admin/audit`
Lista log de auditoria (admin only).

---

## Cadastro por convite

### `POST /api/signup`
Cria conta a partir de token de convite.

Body:
```json
{ "token": "...", "username": "novo", "password": "senha" }
```
