# 02 — Arquitetura

## Stack

- **Backend:** Python 3 (`http.server`)
- **Banco de dados:** SQLite (`data/projectdashboard.db`)
- **Frontend:** HTML + CSS + JavaScript vanilla
- **Serviço:** systemd user service (`projectdashboard.service`)

## Estrutura de diretórios

```text
ProjectDashboard/
├── app.py
├── data/
│   └── projectdashboard.db
├── web/
│   ├── index.html
│   ├── app.js
│   ├── edit.html
│   ├── edit.js
│   ├── login.html
│   ├── login.js
│   ├── signup.html
│   ├── signup.js
│   ├── admin-users.html
│   ├── admin-users.js
│   └── styles.css
├── docs/
│   └── *.md
└── README.md
```

## Componentes principais

1. **Servidor HTTP (`app.py`)**
   - serve páginas estáticas em `/web`
   - expõe API REST simples
   - gerencia autenticação via cookie de sessão

2. **Persistência (`sqlite3`)**
   - usuários, projetos, convites, auditoria

3. **Frontend por página**
   - Kanban (`index.html + app.js`)
   - Edição de projeto (`edit.html + edit.js`)
   - Login (`login.html + login.js`)
   - Cadastro via convite (`signup.html + signup.js`)
   - Administração (`admin-users.html + admin-users.js`)

## Fluxo alto nível

1. Usuário faz login (`/api/login`)
2. Backend cria sessão em memória + cookie HttpOnly
3. Frontend chama endpoints autenticados
4. Backend valida role (`admin`/`member`) por endpoint
5. Alterações relevantes geram registros em `audit_logs`
