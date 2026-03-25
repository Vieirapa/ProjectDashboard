# 24 - Release Checklist (hotfix) — Roles não ressuscitam após delete

**Data:** 2026-03-24  
**Escopo:** bug de gerenciamento de roles (`member` / `desenhista` reaparecendo)

## Checklist de fechamento

- [x] Causa raiz identificada e reproduzida
- [x] Correção aplicada no backend (`deleted_roles` + limpeza legada robusta)
- [x] Regressão automatizada atualizada (`scripts/test_roles_delete_regression.py`)
- [x] Testes locais passando (3/3)
- [x] Commit aplicado e enviado para `develop`
- [x] Validação manual em interface (troca de sessão admin ↔ diretor)
- [x] Bug marcado como resolvido em `docs/15-known-bugs.md`

## Referências

- Commit: `a60f594`
- Branch: `develop`
- Bug ID: `BUG-2026-03-24-002`
