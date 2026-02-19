# 09 — Manutenção e Evolução

## Checklist de manutenção

- [ ] validar serviço (`systemctl --user status`)
- [ ] revisar log de auditoria periodicamente
- [ ] revisar usuários admin ativos
- [ ] fazer backup do banco
- [ ] testar login e páginas críticas após alterações

## Convenções recomendadas

1. Toda mudança em endpoint deve atualizar `04-api.md`
2. Toda mudança em schema deve atualizar `06-banco-de-dados.md`
3. Toda regra de acesso nova deve atualizar `07-seguranca-acessos.md`

## Roadmap técnico sugerido

### Curto prazo
- troca de senha do próprio usuário
- paginação/filtro avançado do log de auditoria
- associação explícita de tarefas (quando módulo de tasks for criado)

### Médio prazo
- extração de camada de repositório para DB
- migração para SQLAlchemy + migrations formais
- tokens CSRF

### Longo prazo
- multi-tenant real (times/workspaces)
- SSO/OAuth
- migração para PostgreSQL

## Estratégia para migração SQLite -> PostgreSQL/MySQL

1. Isolar SQL em camada de acesso (Repository)
2. Introduzir modelo ORM (SQLAlchemy)
3. Criar migrations versionadas
4. Rodar dupla escrita temporária (opcional)
5. Trocar backend de leitura/escrita e validar
