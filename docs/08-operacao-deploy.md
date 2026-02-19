# 08 — Operação e Deploy

## Execução manual

```bash
cd /home/panosso/.openclaw/workspace/projects/ProjectDashboard
python3 app.py
```

Acesso:
- `http://127.0.0.1:8765/login.html`

## Execução automática (systemd user)

Serviço:
- `~/.config/systemd/user/projectdashboard.service`

Comandos úteis:

```bash
systemctl --user status projectdashboard.service
systemctl --user restart projectdashboard.service
journalctl --user -u projectdashboard.service -f
```

## Dependências

- Python 3.10+
- SQLite (embutido no Python)

## Backup

Itens essenciais para backup:
- `projects/ProjectDashboard/data/projectdashboard.db`
- pasta `projects/` (conteúdo dos projetos)

## Restore

1. restaurar diretórios/arquivos
2. reiniciar serviço systemd
3. validar login e endpoints principais
