# Role System Refactor Plan (Fases 1 → 5)

## Objetivo
Evoluir o sistema de papéis (roles) para um modelo dinâmico e administrável por usuários `admin`, com:

- criação/edição/remoção de roles (com regras de proteção)
- controle de acesso por módulo baseado em role cadastrada no banco
- `admin` sempre com acesso total e protegido contra alteração destrutiva
- base preparada para crescimento de módulos e novas interfaces

---

## Premissas de negócio (acordadas)
1. Apenas `admin` gerencia roles.
2. Role `admin` é imutável para operações críticas:
   - não pode ser excluída
   - `role_key` não pode ser alterada
   - acesso a módulos sempre `true`
3. Novas roles iniciam com acesso padrão `false` para módulos (exceto `admin`).
4. UI usa `display_name`; backend/autorização usa `role_key` e/ou `role_id`.

---

## Modelo alvo (dados)

### Tabela `roles`
- `id` (PK)
- `role_key` (TEXT UNIQUE, imutável p/ regra de negócio)
- `display_name` (TEXT)
- `is_system` (INTEGER bool)
- `is_superadmin` (INTEGER bool)
- `active` (INTEGER bool)
- `created_at`, `updated_at`, `created_by`, `updated_by`

### Tabela `role_module_permissions`
- `role_id` (FK -> roles.id)
- `module_id` (FK lógica -> app_modules.module_id)
- `can_access` (INTEGER bool)
- `updated_at`, `updated_by`
- PK composta: `(role_id, module_id)`

### Evoluções futuras (faseada)
- `users.role_id` (substitui gradualmente `users.role` textual)
- `project_allowed_roles(project_id, role_id)` (substitui gradualmente CSV `projects.allowed_roles`)

---

## Fase 1 — Fundação de schema + compatibilidade

### Entregas
1. Criar tabela `roles` e seed inicial (`admin`, `lider_projeto`, `member`, `desenhista`, `colaborador`, `revisor`, `cliente`).
2. Criar `role_module_permissions`.
3. Migrar permissões existentes de `role_modules` para `role_module_permissions`.
4. Garantir bootstrap de `admin` como `is_system=1`, `is_superadmin=1`, `active=1`.
5. Compatibilidade temporária com estrutura atual para não quebrar deploy/local.

### Arquivos provavelmente afetados
- `app.py` (init DB, migrações e bootstrap)
- `docs/` (nota de migração)

### Critério de aceite
- Banco inicializa sem erro em instalação limpa e em base já existente.
- Catálogo de roles é carregado do banco.

---

## Fase 2 — Backend (APIs + autorização)

### Entregas
1. Refatorar serviços de autorização para usar `roles` + `role_module_permissions`.
2. Criar APIs administrativas de roles (somente admin):
   - `GET /api/admin/roles`
   - `POST /api/admin/roles`
   - `PATCH /api/admin/roles/{id|role_key}`
   - `DELETE /api/admin/roles/{id|role_key}`
3. Regras de proteção:
   - bloquear delete/rename estrutural de `admin`
   - bloquear alterações inválidas em role inativa/sistêmica conforme regra
4. Novo módulo criado em `app_modules`:
   - `admin` recebe `true`
   - demais roles recebem `false` por padrão (on-demand/sync)

### Arquivos provavelmente afetados
- `app.py` (rotas, helpers de auth, sync de módulos)

### Critério de aceite
- `admin` gerencia roles com segurança.
- Matriz de módulos continua funcional.

---

## Fase 3 — Frontend (Controle de ROLES + Projetos)

### Entregas
1. Evoluir UI de `settings.html` / `settings.js`:
   - CRUD de roles
   - edição de `display_name`
   - ativar/desativar
   - impedir ação destrutiva na role `admin`
2. Manter matriz de permissões por módulo usando catálogo dinâmico.
3. Ajustar `projects.html`/`projects.js` para catálogo de roles vindo do backend novo.

### Arquivos provavelmente afetados
- `web/settings.html`
- `web/settings.js`
- `web/projects.html`
- `web/projects.js`
- `web/styles.css` (se houver ajustes visuais)

### Critério de aceite
- Role nova aparece automaticamente em `projects` e no controle de permissões.

---

## Fase 4 — Migração de vínculos (users + projects)

### Entregas
1. `users.role` → `users.role_id` (com migração e fallback controlado).
2. `projects.allowed_roles` (CSV) → `project_allowed_roles` (relacional).
3. Endpoints de projetos passam a persistir/ler via tabela relacional.
4. Estratégia de backward compatibility temporária durante a transição.

### Arquivos provavelmente afetados
- `app.py` (modelagem, consultas, migrações e validações)
- `web/projects.js` (payload/consumo)

### Critério de aceite
- Sem perda de permissões de usuários/projetos existentes.
- Comportamento igual ou melhor no fluxo atual.

---

## Fase 5 — Limpeza técnica + hardening + documentação final

### Entregas
1. Removesr legado desnecessário (`ROLES` hardcoded, CSV legado após janela de migração).
2. Revisar auditoria para ações de role management.
3. Cobrir com testes (unitários/integrados/manuais):
   - criação/edição/exclusão de roles
   - bloqueios em `admin`
   - herança de permissão default em módulo novo
   - projetos + usuários com role dinâmica
4. Updatesr documentação operacional e runbooks.

### Arquivos provavelmente afetados
- `app.py`
- `docs/` (arquitetura e operação)
- `README.md`

### Critério de aceite
- Fluxo de roles totalmente baseado em banco, estável e documentado.

---

## Riscos e mitigação

1. **Quebra de compatibilidade em ambientes antigos**
   - Mitigação: migração incremental com fallback temporário.

2. **Perda de permissões durante migração**
   - Mitigação: backup obrigatório + validação pré/pós + script de auditoria de equivalência.

3. **Inconsistência entre catálogo de roles e matriz de módulos**
   - Mitigação: rotina de sync idempotente ao iniciar app e ao criar role/módulo.

4. **Confusão entre `role_key` e `display_name`**
   - Mitigação: definir claramente onde cada campo é usado (backend vs UI).

---

## Ordem recomendada de implementação (execução)
1. Fase 1
2. Fase 2
3. Fase 3
4. Fase 4
5. Fase 5

> Após cada fase: validar localmente em `127.0.0.1:8765` antes de qualquer envio para ambiente de cliente.

---

## Checklist de gate entre fases
- [ ] Migração DB executa sem erro em base nova e existente
- [ ] Login/autorização continuam funcionais
- [ ] Tela de Projetos mostra roles dinâmicas corretas
- [ ] Controle de ROLES acessível apenas para admin
- [ ] Role `admin` protegida
- [ ] Testes de regressão mínimos executados
