# Checklist de Aceitação — Ubuntu + Ubuntu Server

> Projeto: **ProjectDashboard**

## Metadados da execução

- Data:
- Executor:
- Ambiente(s): Ubuntu Desktop / Ubuntu Server
- Versão(ões) Ubuntu: 22.04 / 24.04 (preencher)
- Commit testado:
- Branch:
- Resultado final: `PASS` / `FAIL`

---

## 1) Pré-requisitos

- [ ] `apt-get update` executado com sucesso
- [ ] `git` e `curl` instalados
- [ ] Repositório clonado com sucesso
- [ ] Diretório do projeto acessível

Comandos base:

```bash
sudo apt-get update
sudo apt-get install -y git curl
git clone git@github.com:Vieirapa/ProjectDashboard.git
cd ProjectDashboard
```

---

## 2) Instalação cenário A (sem domínio/HTTPS)

- [ ] Instalador executado: `sudo ENABLE_NGINX=yes ENABLE_HTTPS=no ./install.sh`
- [ ] `projectdashboard` habilitado no boot
- [ ] `projectdashboard` ativo
- [ ] `nginx` habilitado no boot
- [ ] `nginx` ativo
- [ ] `curl -I http://127.0.0.1/login.html` retornou 200/302

---

## 3) Instalação cenário B (com domínio + HTTPS)

- [ ] Instalador executado com `DOMAIN` e `LE_EMAIL`
- [ ] `projectdashboard` ativo
- [ ] `nginx` ativo
- [ ] certificado presente em `certbot certificates`
- [ ] acesso HTTPS válido em `/login.html`

Comando base:

```bash
sudo DOMAIN=dashboard.seudominio.com LE_EMAIL=voce@dominio.com ./install.sh
```

---

## 4) Aceite funcional da aplicação

- [ ] Login com `admin/admin`
- [ ] Troca de senha admin realizada
- [ ] Projeto criado em `projects.html`
- [ ] Card criado no Kanban
- [ ] Status/prioridade do card alterados
- [ ] RBAC validado (admin total + bloqueio por role sem permissão)

---

## 5) Backup e restauração

### 5.1 Backup

- [ ] `projectdashboard-backup.timer` ativo
- [ ] `projectdashboard-backup.service` executado manualmente
- [ ] backup do DB gerado (`projectdashboard-db-*.sqlite3`)
- [ ] backup do docs_repo gerado (`projectdashboard-docs-repo-*.tar.gz`)
- [ ] backup de documents gerado (`projectdashboard-documents-*.tar.gz`)

### 5.2 Restore

- [ ] `restore_backup.sh` executado com arquivos de DB + docs_repo + documents
- [ ] Serviço voltou ativo após restore
- [ ] Dados restaurados validados

Comando base:

```bash
sudo ./scripts/restore_backup.sh \
  --db-backup /var/backups/projectdashboard/projectdashboard-db-AAAA-MM-DD_HHMMSS.sqlite3 \
  --docs-repo-backup /var/backups/projectdashboard/projectdashboard-docs-repo-AAAA-MM-DD_HHMMSS.tar.gz \
  --documents-backup /var/backups/projectdashboard/projectdashboard-documents-AAAA-MM-DD_HHMMSS.tar.gz
```

---

## 6) Teste de reboot

- [ ] Máquina reiniciada
- [ ] `projectdashboard` voltou ativo automaticamente
- [ ] `nginx` voltou ativo automaticamente
- [ ] App acessível após reboot

---

## 7) Validação Ubuntu Desktop

- [ ] Acesso local em navegador (`http://127.0.0.1/login.html`)
- [ ] Fluxo de uso básico funcional

## 8) Validação Ubuntu Server

- [ ] Acesso remoto por IP/DNS funcional
- [ ] UFW com regras corretas (`OpenSSH`, `Nginx Full`)
- [ ] Sem intervenção manual pós-boot

---

## Evidências

- Logs/comandos:
- Prints/URLs:
- Observações:

## Pendências abertas

- Item:
- Responsável:
- Prazo:
