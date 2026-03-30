from __future__ import annotations

"""
backend.auth.session
====================

Módulo responsável por autenticação básica local e gerenciamento de sessão em
memória.

Objetivo deste módulo
---------------------
Concentrar a lógica mais reutilizável de:
- hash/verificação de senha
- criação de sessão
- leitura de cookie
- resolução do usuário autenticado

How it should be used
-------------------
- O backend principal delega para este módulo em vez de manter a lógica toda
  espalhada em `app.py`.
- Este módulo não conhece regras de página, RBAC avançado ou roteamento HTTP;
  ele trabalha apenas com autenticação e sessão.

Limitação atual
---------------
As sessões vivem em memória. Isso é suficiente para o estágio atual da app,
mas não é desenho final para cenários com múltiplos processos ou execução
horizontal.
"""

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime
from http import cookies


# ---------------------------------------------------------------------------
# Hash de senha local
# ---------------------------------------------------------------------------
def hash_password(password: str, salt_hex: str | None = None) -> str:
    """
    Gera um hash PBKDF2-HMAC SHA-256 para a senha informada.

    Parameters
    ----------
    password:
        Senha em texto puro.
    salt_hex:
        Salt já existente em hexadecimal. Quando omitido, um novo salt aleatório
        é gerado.

    Return
    -------
    str
        String no formato `salt_hex$digest_hex`.

    How it should be used
    -------------------
    - Na criação de usuário
    - Na troca de senha
    - Na redefinição administrativa de senha
    - Na verificação, via `verify_password(...)`
    """
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


# ---------------------------------------------------------------------------
# Verificação de senha
# ---------------------------------------------------------------------------
def verify_password(password: str, stored: str) -> bool:
    """
    Verifica se a senha informada corresponde ao hash persistido.

    Parameters
    ----------
    password:
        Senha em texto puro enviada pelo usuário.
    stored:
        Hash persistido no formato `salt_hex$digest_hex`.

    Return
    -------
    bool
        `True` quando a senha é válida; `False` em qualquer falha.

    Observação
    ----------
    O uso de `hmac.compare_digest` evita comparação ingênua de strings.
    """
    try:
        salt_hex, digest_hex = stored.split('$', 1)
        return hmac.compare_digest(hash_password(password, salt_hex), f"{salt_hex}${digest_hex}")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Criação de sessão autenticada
# ---------------------------------------------------------------------------
def create_session(sessions: dict[str, dict], session_ttl_seconds: int, username: str, role: str) -> str:
    """
    Creates a new  sessão em memória e devolve o token correspondente.

    Parameters
    ----------
    sessions:
        Estrutura em memória usada pelo app para armazenar sessões ativas.
    session_ttl_seconds:
        Tempo de vida da sessão em segundos.
    username:
        Nome do usuário autenticado.
    role:
        Role atual do usuário.

    Return
    -------
    str
        Token hexadecimal de sessão.

    How it should be used
    -------------------
    Chamada pelo fluxo de login do backend. O token retornado deve ser gravado
    no cookie de sessão configurado pela aplicação.
    """
    token = secrets.token_hex(24)
    sessions[token] = {
        'username': username,
        'role': role,
        'exp': datetime.now(UTC).timestamp() + session_ttl_seconds,
    }
    return token


# ---------------------------------------------------------------------------
# Parsing de cookie bruto HTTP
# ---------------------------------------------------------------------------
def parse_cookie(raw: str | None) -> dict:
    """
    Converte o header bruto `Cookie` em um dicionário simples.

    Parameters
    ----------
    raw:
        Valor bruto do header `Cookie` recebido na requisição.

    Return
    -------
    dict
        Mapa `nome -> valor` de cookies.
    """
    if not raw:
        return {}
    jar = cookies.SimpleCookie()
    jar.load(raw)
    return {k: v.value for k, v in jar.items()}


# ---------------------------------------------------------------------------
# Resolução do usuário atual a partir do cookie
# ---------------------------------------------------------------------------
def current_user_from_cookie(sessions: dict[str, dict], session_cookie: str, raw_cookie: str | None) -> dict | None:
    """
    Resolve o usuário autenticado a partir do cookie de sessão.

    Parameters
    ----------
    sessions:
        Estrutura em memória de sessões ativas.
    session_cookie:
        Nome do cookie que carrega o token da sessão.
    raw_cookie:
        Header bruto `Cookie` da requisição atual.

    Return
    -------
    dict | None
        Retorna um dicionário com `username`, `role` e `token` quando a sessão
        é válida. Retorna `None` quando não existe, expirou ou está inválida.

    How it should be used
    -------------------
    Deve ser chamada pelo backend principal sempre que uma rota precisar
    identificar o usuário autenticado a partir da requisição HTTP.
    """
    tok = parse_cookie(raw_cookie).get(session_cookie)
    if not tok or tok not in sessions:
        return None
    s = sessions[tok]
    if datetime.now(UTC).timestamp() > s['exp']:
        sessions.pop(tok, None)
        return None
    return {'username': s['username'], 'role': s['role'], 'token': tok}
