# ProjectDashboard (Kanban simples)

Dashboard web simples para visualizar e gerenciar projetos em paralelo.

## Como rodar

```bash
cd /home/panosso/.openclaw/workspace/projects/ProjectDashboard
python3 app.py
```

Depois abra no navegador:

`http://127.0.0.1:8765`

## Estrutura esperada

O dashboard lê os projetos da pasta:

`/home/panosso/.openclaw/workspace/projects`

Cada projeto pode ter um arquivo `project.json`:

```json
{
  "name": "NomeProjeto",
  "status": "Backlog",
  "description": "Resumo curto"
}
```

Status aceitos:
- `Backlog`
- `Em andamento`
- `Bloqueado`
- `Concluído`
