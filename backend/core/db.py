from __future__ import annotations

"""
backend.core.db
================

Módulo de infraestrutura responsável por concentrar operações básicas de acesso
à base SQLite e inspeção leve de schema.

Objetivo deste módulo
---------------------
Reduzir o acoplamento do `app.py` com detalhes repetitivos de banco, deixando
as regras de negócio focadas no domínio e não em boilerplate de conexão ou
checagens estruturais simples.

How it should be used
-------------------
- `connect_db(...)` deve ser chamado pelo factory principal de conexão do app.
- `ensure_column(...)` deve ser usado apenas em rotinas de bootstrap/migração
  leve, nunca como substituto de uma estratégia formal de migrations.
- `table_exists(...)` e `column_exists(...)` devem ser usados em migrações
  defensivas, compatibilidade legada e checagens condicionais de schema.

Observação
----------
Este módulo não contém regras de negócio. Ele oferece apenas utilitários de
infraestrutura de banco.
"""

import sqlite3
from pathlib import Path


# ---------------------------------------------------------------------------
# Conexão principal SQLite
# ---------------------------------------------------------------------------
def connect_db(data_dir: Path, db_path: Path) -> sqlite3.Connection:
    """
    Cria e devolve uma conexão SQLite pronta para uso pela aplicação.

    O que faz
    ---------
    - Garante que o diretório de dados exista.
    - Abre a conexão SQLite no caminho informado.
    - Configura `row_factory` para `sqlite3.Row`, permitindo acesso por nome
      de coluna no restante do sistema.

    Parameters
    ----------
    data_dir:
        Diretório-base onde os arquivos de dados da aplicação vivem.
    db_path:
        Caminho completo do arquivo `.sqlite3`/banco principal.

    Return
    -------
    sqlite3.Connection
        Conexão pronta para leitura/escrita.

    How it should be used no restante do programa
    -------------------------------------------
    Normalmente ela é chamada indiretamente por `app.db()`, que atua como
    factory central de conexão.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Migração leve de coluna
# ---------------------------------------------------------------------------
def ensure_column(conn: sqlite3.Connection, table: str, col: str, ddl: str):
    """
    Garante que uma coluna exista em uma tabela SQLite.

    O que faz
    ---------
    - Lê o schema atual da tabela via `PRAGMA table_info`.
    - Se a coluna ainda não existir, executa `ALTER TABLE ... ADD COLUMN`.

    Parameters
    ----------
    conn:
        Conexão ativa do banco.
    table:
        Nome da tabela a ser inspecionada.
    col:
        Nome lógico da coluna que deve existir.
    ddl:
        Trecho DDL completo da coluna para `ADD COLUMN`.
        Exemplo: `priority TEXT DEFAULT 'Média'`.

    Return
    -------
    None

    How it should be used no restante do programa
    -------------------------------------------
    Deve ser usada apenas em bootstrap/migração leve. Se o projeto evoluir para
    migrations versionadas formais, este helper deve permanecer como apoio
    defensivo e não como estratégia principal de evolução de schema.
    """
    cols = {r['name'] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


# ---------------------------------------------------------------------------
# Inspeção de existência de tabela
# ---------------------------------------------------------------------------
def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """
    Informa se uma tabela existe no banco atual.

    Parameters
    ----------
    conn:
        Conexão ativa do banco.
    name:
        Nome da tabela a ser verificada.

    Return
    -------
    bool
        `True` quando a tabela existe, `False` caso contrário.

    Uso típico
    ----------
    Utilizado em rotinas de compatibilidade/migração e em caminhos de código
    que precisam respeitar instalações antigas ou bancos parcialmente migrados.
    """
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


# ---------------------------------------------------------------------------
# Inspeção de existência de coluna
# ---------------------------------------------------------------------------
def column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    """
    Informa se uma coluna específica existe em uma tabela.

    Parameters
    ----------
    conn:
        Conexão ativa do banco.
    table:
        Nome da tabela.
    col:
        Nome da coluna.

    Return
    -------
    bool
        `True` quando a coluna existe, `False` quando não existe ou quando a
        inspeção falha por ausência da tabela.

    Observação
    ----------
    O tratamento defensivo com `except Exception` é intencional aqui para evitar
    quebrar caminhos de bootstrap/migração em cenários de schema parcial.
    """
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return False
    return col in cols
