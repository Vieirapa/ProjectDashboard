# 09 — Maintenance and Evolution

## Maintenance checklist

- [ ] verify service health (`systemctl status projectdashboard`)
- [ ] verify backups and retention
- [ ] review active admin users
- [ ] test login and critical pages after changes
- [ ] check audit logs for anomalies

## Recommended conventions

1. API changes must update `04-api.md`
2. Schema changes must update `06-banco-de-dados.md`
3. Security-sensitive changes must update `07-seguranca-acessos.md`

## Suggested technical roadmap

### Short term
- self-service password change
- richer audit log filtering/pagination
- improved validation/error consistency

### Mid term
- repository/data access layer extraction
- formal DB migration tooling
- test coverage expansion (API + UI)

### Long term
- PostgreSQL migration
- multi-tenant boundaries
- observability stack (metrics/tracing/alerts)

## SQLite → PostgreSQL/MySQL migration strategy

1. isolate persistence layer contracts
2. introduce migration tooling
3. run schema parity tests
4. optional temporary dual-write phase
5. cut over and validate with rollback plan
