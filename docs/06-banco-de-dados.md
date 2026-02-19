# 06 — Banco de Dados (SQLite)

Arquivo:
- `data/projectdashboard.db`

## Tabelas

### `users`
- `id` (PK)
- `username` (UNIQUE)
- `password_hash`
- `role` (`admin` ou `member`)
- `created_at`

### `projects`
- `id` (PK)
- `slug` (UNIQUE)
- `name`
- `status`
- `priority`
- `owner`
- `due_date`
- `description`
- `path`
- `updated_at`

### `invites`
- `id` (PK)
- `token` (UNIQUE)
- `role`
- `created_by`
- `used_by`
- `expires_at`
- `created_at`

### `audit_logs`
- `id` (PK)
- `actor`
- `action`
- `target`
- `details`
- `created_at`

## Migrations atuais

Não há framework formal de migração. O sistema usa:
- `CREATE TABLE IF NOT EXISTS`
- `ensure_column(...)` para adições pontuais de colunas

## Estratégia de migração futura (recomendada)

Para crescimento, adotar:
- Alembic (se migrar para SQLAlchemy)
- ou scripts versionados de migração SQL
