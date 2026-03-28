# 29 — Backend Evolution Boundaries (Sprint B1)

## Objetivo

Definir os limites de evolução do backend do ProjectDashboard para reduzir a concentração de responsabilidades em `app.py` sem reescrever o sistema inteiro.

A meta desta fase não é trocar stack, framework ou modelo de deploy. A meta é criar uma estrutura interna mais legível, modular e segura para continuar evoluindo o produto.

---

## Estado atual

O backend atual está concentrado em `app.py`, que reúne:

- bootstrap de banco e migrações leves
- utilitários gerais
- autenticação e sessão
- autorização e RBAC
- catálogo de roles e módulos
- projetos e documentos
- dependências entre documentos
- revisão e versionamento
- usuários e perfil
- configurações administrativas
- relatórios periódicos
- backup e diagnóstico
- roteamento HTTP e entrega de arquivos estáticos

Esse modelo funcionou bem para chegar ao estágio atual, mas já começa a aumentar:

- custo cognitivo de manutenção
- risco de regressão por mudança lateral
- dificuldade de teste por domínio
- dificuldade de evolução paralela por múltiplos agentes/devs

---

## Princípios da evolução

1. **Não fazer reescrita total agora**
   - Preservar o comportamento atual.
   - Evitar trocas grandes de stack ou framework nesta fase.

2. **Extrair por domínio, não por moda**
   - Cada extração deve ter um objetivo claro de legibilidade, encapsulamento e redução de risco.

3. **Começar pelos blocos de menor risco**
   - Primeiro helpers, auth/session, RBAC e utilitários infra.
   - Só depois mexer mais profundamente no domínio principal.

4. **Manter `app.py` como ponto de composição temporário**
   - Nesta fase, `app.py` ainda pode continuar concentrando boot e rotas.
   - O objetivo é deixá-lo menor e mais legível a cada ciclo.

5. **Não misturar refactor estrutural com mudança funcional grande**
   - Sempre que possível, refatorar mantendo comportamento equivalente.

---

## Módulos-alvo

A proposta de evolução do backend é convergir para esta organização lógica:

### 1. `backend/core/db.py`
Responsabilidades:
- abrir conexão SQLite
- helpers de schema (`ensure_column`, `_table_exists`, `_column_exists`)
- utilitários base de persistência
- eventual ponte para futura estratégia de migrations

### 2. `backend/core/http.py`
Responsabilidades:
- helpers HTTP/JSON
- parse de requests/respostas
- helpers reutilizáveis de rotas
- eventual abstração leve para respostas e erros

### 3. `backend/auth/session.py`
Responsabilidades:
- hashing/verificação de senha
- criação e leitura de sessão
- parse de cookie
- resolução do usuário atual
- logout/invalidação local

### 4. `backend/rbac/roles.py`
Responsabilidades:
- catálogo de roles
- roles ativas/inativas
- fallback de role
- CRUD administrativo de roles
- regras de proteção da role `admin`

### 5. `backend/rbac/modules.py`
Responsabilidades:
- catálogo de módulos
- matrix role-module
- permissões efetivas
- allowed pages/modules
- sync de módulos

### 6. `backend/projects/service.py`
Responsabilidades:
- listagem, criação, edição, exclusão de projetos
- templates de projeto
- allowed roles por projeto
- regras de visibilidade de projeto

### 7. `backend/documents/service.py`
Responsabilidades:
- listagem e CRUD de documentos/cards
- owner/status/priority
- dependências entre documentos
- integração com projetos

### 8. `backend/documents/revisions.py`
Responsabilidades:
- upload de documento
- histórico de revisões
- metadados de arquivo
- consulta de versões

### 9. `backend/review_notes/service.py`
Responsabilidades:
- criação de review notes
- resolução/reabertura
- regras por papel/estado

### 10. `backend/admin/settings.py`
Responsabilidades:
- settings administrativas
- SMTP
- defaults operacionais
- parâmetros de backup/diagnóstico

### 11. `backend/reports/service.py`
Responsabilidades:
- periodic reports
- composição de relatórios
- envio por e-mail
- scheduler/report execution

### 12. `backend/ops/backup.py`
Responsabilidades:
- backup manual
- teste de permissões
- listagem de backups
- restore e metadata operacional

### 13. `backend/ops/diagnostics.py`
Responsabilidades:
- diagnósticos do sistema
- badge/estado de saúde
- checks de ambiente e storage

### 14. `backend/audit/service.py`
Responsabilidades:
- auditoria de ações críticas
- listagem de audit logs
- padronização de eventos sensíveis

---

## Ordem de extração recomendada

### Fase B1.1 — Extrações de baixo risco
1. `core/db.py`
2. `auth/session.py`
3. `audit/service.py`

### Fase B1.2 — Extrações infra + governança
4. `rbac/roles.py`
5. `rbac/modules.py`
6. `ops/backup.py`
7. `ops/diagnostics.py`
8. `reports/service.py`

### Fase B1.3 — Extrações do domínio principal
9. `projects/service.py`
10. `documents/service.py`
11. `documents/revisions.py`
12. `review_notes/service.py`
13. `admin/settings.py`

> A ordem acima reduz risco porque extrai primeiro blocos mais coesos e menos cruzados com rendering HTTP.

---

## Responsabilidades que devem continuar em `app.py` nesta fase

Até segunda ordem, `app.py` pode continuar concentrando:

- boot da aplicação
- `Handler(BaseHTTPRequestHandler)`
- roteamento principal de endpoints
- static file serving
- composição de chamadas para módulos extraídos

O objetivo é que `app.py` deixe de conter a maior parte da lógica de negócio e passe a ser um arquivo de composição e integração.

---

## Limites desta sprint

Esta sprint **não deve**:

- trocar `http.server` por Flask/FastAPI agora
- trocar SQLite por PostgreSQL agora
- reescrever todas as rotas
- introduzir ORM completo nesta fase
- quebrar compatibilidade de deploy com `install.sh`
- alterar o contrato de API sem necessidade clara

Esta sprint **deve**:

- preparar o código para crescer melhor
- reduzir acoplamento
- tornar as áreas críticas mais identificáveis
- criar base para próximos ciclos de refactor seguro

---

## Estratégia de migrations

Nesta sprint, o objetivo é apenas preparar o terreno para uma estratégia formal de migrations.

### Proposta mínima
Criar base para:

- diretório `migrations/`
- tabela `schema_migrations`
- versão atual do schema registrada
- execução incremental por versão

### Fora do escopo imediato
- adoção de Alembic
- troca completa do bootstrap atual

---

## Critérios de aceite da frente estrutural

Considerar a frente estrutural bem-sucedida quando:

- `app.py` estiver menor ou com menos responsabilidades diretas
- os blocos extraídos tiverem fronteiras claras
- auth/session e DB helpers já não dependerem de lógica espalhada
- RBAC tiver desenho modular explícito
- o sistema continuar funcional nos fluxos principais

---

## Fluxos obrigatórios para regressão após cada extração

Após cada extração relevante, validar ao menos:

1. login/logout
2. carregamento inicial do dashboard
3. carregamento do kanban
4. abertura da tela de detalhe
5. acesso admin básico (`users/settings` quando aplicável)
6. checagem de permissões por perfil

---

## Próximo passo recomendado

Após este documento:

1. extrair `core/db.py`
2. extrair `auth/session.py`
3. revisar chamadas internas de `app.py`
4. só então iniciar modularização explícita do RBAC
