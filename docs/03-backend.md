# 03 — Backend (app.py)

## Constantes de configuração

- `BASE_DIR`: pasta com projetos do workspace
- `WEB_DIR`: pasta de arquivos web
- `DATA_DIR` / `DB_PATH`: armazenamento SQLite
- `HOST` / `PORT`: bind do servidor (atualmente `0.0.0.0:8765`)
- `STATUSES`, `PRIORITIES`, `ROLES`
- `SESSION_COOKIE`, `SESSION_TTL_SECONDS`

## Funções utilitárias

- `now_iso()`
  - gera timestamp UTC ISO sem microssegundos
- `slugify(name)`
  - normaliza nome para slug de projeto
- `hash_password(password, salt_hex=None)`
  - PBKDF2-HMAC-SHA256 com salt
- `verify_password(password, stored)`
  - valida senha com comparação segura (`hmac.compare_digest`)
- `read_text_if_exists(path)`
  - leitura segura de arquivo texto
- `infer_description(project_dir)`
  - extrai descrição inicial do README

## Camada de banco

- `db()`
  - abre conexão SQLite com `row_factory=sqlite3.Row`
- `ensure_column(conn, table, col, ddl)`
  - migração leve para adicionar colunas em upgrades
- `init_db()`
  - cria tabelas principais
  - cria usuário admin inicial se vazio
  - garante role admin para `username='admin'`

## Domínio de projetos

- `migrate_existing_projects()`
  - importa projetos existentes no filesystem para o banco
- `list_projects()`
- `get_project(slug)`
- `create_project(payload)`
- `patch_project(slug, payload)`
- `delete_project(slug)`
- `sync_project_meta(project)`
  - mantém compatibilidade escrevendo `project.json` na pasta do projeto

## Auditoria

- `audit(actor, action, target, details="")`
  - registra ação em `audit_logs`
- `list_audit_logs(limit=200)`

## Sessões

- `create_session(username, role)`
  - cria token randômico em memória (`SESSIONS`)
- `parse_cookie(raw)`
- `current_user_from_cookie(raw_cookie)`

## Classe HTTP Handler

### Helpers internos
- `_json()`
- `_serve()`
- `_read_json()`
- `_user()`
- `_require_auth()`
- `_require_admin()`

### Rotas por método
- `do_GET`
- `do_POST`
- `do_PATCH`
- `do_DELETE`

## Ponto de entrada

- `main()`
  - `init_db()`
  - `migrate_existing_projects()`
  - start HTTPServer
