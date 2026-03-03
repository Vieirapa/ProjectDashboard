# 08 — Operação e Deploy

## Instalação automatizada (servidor)

Script:
- `install.sh` (v2)

Exemplo básico:

```bash
cd /caminho/ProjectDashboard
sudo ./install.sh
```

Exemplo com domínio/HTTPS:

```bash
sudo DOMAIN=dashboard.seudominio.com LE_EMAIL=admin@seudominio.com ./install.sh
```

Resultado da instalação:
- app copiado para `/opt/projectdashboard`
- serviço `projectdashboard.service` habilitado no boot
- arquivo de ambiente em `/etc/projectdashboard.env`
- nginx configurado como reverse proxy (quando habilitado)
- HTTPS com Let's Encrypt (quando domínio+e-mail são informados)
- backup diário automático via `projectdashboard-backup.timer`
- usuário inicial garantido: `admin` / `admin`

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
