from __future__ import annotations

"""
backend.rbac.roles
==================

Módulo responsável pelo núcleo de catálogo e estado de roles do sistema.

Objetivo deste módulo
---------------------
Concentrar a parte mais estável e coesa do RBAC, especialmente:
- catálogo de roles
- verificação de existência
- verificação de ativação
- fallback seguro de role

How it should be used
-------------------
- O `app.py` delega para este módulo em operações centrais de leitura do
  catálogo de roles.
- Regras mais amplas de permissões por módulo/página continuam fora daqui por
  enquanto, para manter esta extração pequena e segura.

Escopo deste módulo
-------------------
Este módulo não faz CRUD administrativo completo nem calcula permissões
efetivas por módulo. Seu foco é o estado e a disponibilidade das roles.
"""

import sqlite3
from collections.abc import Callable


# ---------------------------------------------------------------------------
# Catálogo efetivo de roles
# ---------------------------------------------------------------------------
def list_role_catalog(
    db_factory: Callable[[], sqlite3.Connection],
    default_roles: list[str],
    include_admin: bool = True,
) -> list[str]:
    """
    Retorna o catálogo efetivo de roles conhecidas pela aplicação.

    Estratégia de funcionamento
    ---------------------------
    1. Tenta usar a tabela oficial `roles` quando ela existir e estiver populada.
    2. Se isso ainda não estiver disponível, usa fallback legado combinando:
       - roles padrão da aplicação
       - roles encontradas em usuários
       - roles encontradas na matriz role_modules
       - roles declaradas em projetos

    Parameters
    ----------
    db_factory:
        Factory de conexão com o banco, normalmente `app.db`.
    default_roles:
        Lista de roles padrão embutidas no sistema, usada como fallback.
    include_admin:
        Define se `admin` deve aparecer no retorno.

    Return
    -------
    list[str]
        Lists the rdenada por descoberta/ordem de banco, sem duplicidades.

    How it should be used
    -------------------
    Deve ser chamada por partes do sistema que precisem:
    - montar selects de role
    - validar choices em UI/admin
    - listar roles disponíveis no momento atual
    """
    out: list[str] = []
    seen: set[str] = set()

    def add_role(value: str | None):
        role = str(value or '').strip().lower()
        if not role or role in seen:
            return
        seen.add(role)
        out.append(role)

    with db_factory() as conn:
        role_rows = conn.execute(
            "SELECT role_key FROM roles WHERE active=1 ORDER BY id"
        ).fetchall()
        if role_rows:
            for r in role_rows:
                add_role(r['role_key'])
        else:
            for role in default_roles:
                add_role(role)

            user_roles = conn.execute(
                "SELECT DISTINCT role FROM users WHERE role IS NOT NULL AND TRIM(role)<>''"
            ).fetchall()
            module_roles = conn.execute(
                "SELECT DISTINCT role_name FROM role_modules WHERE role_name IS NOT NULL AND TRIM(role_name)<>''"
            ).fetchall()
            project_roles = conn.execute(
                "SELECT DISTINCT allowed_roles FROM projects WHERE allowed_roles IS NOT NULL AND TRIM(allowed_roles)<>''"
            ).fetchall()

            for r in user_roles:
                add_role(r['role'])
            for r in module_roles:
                add_role(r['role_name'])
            for r in project_roles:
                for role in str(r['allowed_roles'] or '').split(','):
                    add_role(role)

    if include_admin:
        return out
    return [r for r in out if r != 'admin']


# ---------------------------------------------------------------------------
# Existência de role
# ---------------------------------------------------------------------------
def role_exists(
    db_factory: Callable[[], sqlite3.Connection],
    role_key: str,
    active_only: bool = True,
) -> bool:
    """
    Informa se uma role existe no catálogo.

    Parameters
    ----------
    db_factory:
        Factory de conexão com o banco.
    role_key:
        Identificador lógico da role.
    active_only:
        Quando `True`, considera apenas roles ativas.

    Return
    -------
    bool
        `True` quando a role existe dentro do critério escolhido.

    Uso típico
    ----------
    Utilizado em validações administrativas, formulários e regras defensivas.
    """
    role = str(role_key or '').strip().lower()
    if not role:
        return False
    with db_factory() as conn:
        if active_only:
            row = conn.execute('SELECT 1 FROM roles WHERE role_key=? AND active=1', (role,)).fetchone()
        else:
            row = conn.execute('SELECT 1 FROM roles WHERE role_key=?', (role,)).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Ativação de role
# ---------------------------------------------------------------------------
def role_is_active(
    db_factory: Callable[[], sqlite3.Connection],
    role_key: str,
    default_roles: list[str],
) -> bool:
    """
    Informa se uma role está ativa para uso no sistema.

    Parameters
    ----------
    db_factory:
        Factory de conexão com o banco.
    role_key:
        Role a verificar.
    default_roles:
        Roles padrão da app, usadas como fallback em instalações antigas ou
        durante bootstrap parcial.

    Return
    -------
    bool
        `True` para roles ativas; `False` caso contrário.

    Observação
    ----------
    Em caso de `OperationalError`, o módulo assume fallback legado para não
    quebrar bootstrap/migrações ainda não concluídas.
    """
    role = str(role_key or '').strip().lower()
    if not role:
        return False
    try:
        with db_factory() as conn:
            row = conn.execute('SELECT active FROM roles WHERE role_key=?', (role,)).fetchone()
            if row is None:
                return False
            return bool(int(row['active'] or 0))
    except sqlite3.OperationalError:
        return role in {r.lower() for r in default_roles}


# ---------------------------------------------------------------------------
# Fallback seguro de role
# ---------------------------------------------------------------------------
def resolve_fallback_role(
    db_factory: Callable[[], sqlite3.Connection],
    preferred: str = 'member',
) -> str:
    """
    Resolve uma role segura para fallback quando a role desejada não pode ser usada.

    Estratégia de fallback
    ----------------------
    1. Usa a role preferida, se estiver ativa.
    2. Caso contrário, escolhe a primeira role ativa que não seja `admin`.
    3. Se não houver outra opção, usa `admin`.

    Parameters
    ----------
    db_factory:
        Factory de conexão com o banco.
    preferred:
        Role preferencial desejada pelo chamador.

    Return
    -------
    str
        Role final resolvida para uso seguro.

    How it should be used
    -------------------
    Útil em cenários de:
    - reatribuição de usuários
    - remoção/inativação de role
    - normalização de estado administrativo
    """
    pref = str(preferred or '').strip().lower()
    with db_factory() as conn:
        if pref:
            row = conn.execute('SELECT role_key FROM roles WHERE role_key=? AND active=1', (pref,)).fetchone()
            if row:
                return str(row['role_key'])

        row = conn.execute(
            "SELECT role_key FROM roles WHERE active=1 AND role_key!='admin' ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            return str(row['role_key'])

        admin_row = conn.execute("SELECT role_key FROM roles WHERE role_key='admin' LIMIT 1").fetchone()
        if admin_row:
            return str(admin_row['role_key'])

    return 'admin'
