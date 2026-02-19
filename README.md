# ProjectDashboard (Kanban simples)

Dashboard web para visualizar e gerenciar projetos em paralelo.

## Novidades (Onda 1+)

- Layout com **barra lateral** e categorias (Workspace/Administração)
- Login por usuário
- Edição em **página dedicada** (`/edit.html?slug=...`) com todos os campos
- Criação de projeto pela UI
- Filtros (busca, status, prioridade, responsável)
- Ordenação por prioridade
- Administração de usuários e convites (`/admin-users.html`)
- Troca de senha pelo painel admin
- Edição de role (admin/member) pelo painel admin
- Exclusão de usuários (somente admin), com dupla confirmação
- Exibição de tarefas associadas ao usuário no momento da exclusão
- Botão de exclusão desabilitado para contas admin
- Log de auditoria (quem fez o quê e quando)
- RBAC inicial:
  - `admin`: gerencia usuários/convites, troca role/senha, exclui usuários e pode apagar projetos
  - `member`: cria/edita projetos, mas **não apaga** projetos nem acessa admin

## Banco de dados (preparado para evolução)

Agora o dashboard usa **SQLite** (`data/projectdashboard.db`) para persistir:

- usuários
- projetos

Isso prepara o projeto para futura migração para MySQL/PostgreSQL com mudanças concentradas na camada de persistência do backend.

## Usuário inicial

No primeiro boot, é criado automaticamente:

- usuário: `admin`
- senha: `admin123` (ou valor de `PDASH_INITIAL_PASSWORD`)

> Troque essa senha assim que possível.

## Documentação completa

A documentação técnica e operacional completa está em:

- `docs/README.md`

## Como rodar

```bash
cd /home/panosso/.openclaw/workspace/projects/ProjectDashboard
python3 app.py
```

Depois abra no navegador:

- `http://127.0.0.1:8765/login.html`

## Estrutura esperada dos projetos

Os projetos continuam na pasta:

`/home/panosso/.openclaw/workspace/projects`

Cada projeto mantém arquivos (`README.md`, `TASKS.md`) e também `project.json` para compatibilidade local.
