# 25 - QA Note (manual) — Roles delete fix validated

**Data:** 2026-03-24  
**Status:** ✅ Aprovado em QA manual

## Cenário validado

1. Login como admin.
2. Remoção das roles `member` e `desenhista`.
3. Refresh de interface.
4. Logout admin e login com role `diretor`.
5. Navegação na interface.
6. Logout `diretor` e novo login como admin.
7. Conferência final em Controle de Roles.

## Resultado

- `member` e `desenhista` **não reaparecem** após refresh/troca de sessão.
- Fluxo de gerenciamento de roles está consistente com a regra de negócio.

## Rastreabilidade

- Fix commit: `a60f594`
- Teste automatizado relacionado: `scripts/test_roles_delete_regression.py`
