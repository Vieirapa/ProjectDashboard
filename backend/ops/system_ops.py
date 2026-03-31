from __future__ import annotations

"""
backend.ops.system_ops
======================

Operações operacionais do sistema relacionadas a backup, restauração,
catálogo de snapshots e diagnóstico básico.
"""

import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import Callable
import sqlite3


def test_backup_path_permissions(get_admin_settings_fn, backup_config_fn, resolve_backup_path_fn, backup_permission_hint_fn, path_raw: str | None = None) -> tuple[bool, str, dict]:
    settings = get_admin_settings_fn()
    cfg = backup_config_fn(settings)
    target = resolve_backup_path_fn(path_raw or cfg['path'])
    detail = {'path': str(target), 'exists': False, 'writable': False}
    try:
        detail['exists'] = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        probe = target / f'.pdash-permcheck-{int(time.time())}.tmp'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink(missing_ok=True)
        detail['writable'] = True
        return True, f'Caminho de backup OK para escrita: {target}', detail
    except PermissionError:
        return False, backup_permission_hint_fn(target), detail
    except Exception as e:
        return False, f"Falha ao validar caminho de backup '{target}': {e}", detail


def run_system_backup(get_admin_settings_fn, backup_config_fn, resolve_backup_path_fn, backup_permission_hint_fn, audit_fn, data_dir: Path, actor: str = 'system', path_override: str | None = None) -> tuple[bool, str]:
    settings = get_admin_settings_fn()
    cfg = backup_config_fn(settings)
    primary_out_dir = resolve_backup_path_fn(path_override or cfg['path'])
    fallback_out_dir = (data_dir / 'backups').resolve()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    db_src = data_dir / 'projectdashboard.db'
    docs_src = data_dir / 'docs_repo'

    def _write_backup(target_dir: Path) -> list[str]:
        target_dir.mkdir(parents=True, exist_ok=True)
        copied_local: list[str] = []
        if db_src.exists():
            db_out = target_dir / f'projectdashboard-db-{stamp}.sqlite3'
            db_out.write_bytes(db_src.read_bytes())
            copied_local.append(db_out.name)
        if docs_src.exists() and docs_src.is_dir():
            archive = target_dir / f'projectdashboard-docs-{stamp}.tar.gz'
            subprocess.run(['tar', '-czf', str(archive), '-C', str(data_dir), 'docs_repo'], check=True)
            copied_local.append(archive.name)
        return copied_local

    used_dir = primary_out_dir
    try:
        copied = _write_backup(primary_out_dir)
    except PermissionError:
        try:
            copied = _write_backup(fallback_out_dir)
            used_dir = fallback_out_dir
            hint = backup_permission_hint_fn(primary_out_dir)
            msg = f"backup salvo em {used_dir} ({', '.join(copied)}) | Obs: caminho configurado sem permissão. {hint}"
            audit_fn(actor, 'system.backup.run', str(used_dir), msg)
            return True, msg
        except Exception as e2:
            return False, f'falha no backup. {backup_permission_hint_fn(primary_out_dir)} | detalhe: {e2}'
    except Exception as e:
        return False, f'falha no backup: {e}'

    if not copied:
        return False, 'nenhum artefato encontrado para backup'

    audit_fn(actor, 'system.backup.run', str(used_dir), ', '.join(copied))
    return True, f"backup salvo em {used_dir} ({', '.join(copied)})"


def list_available_backups(get_admin_settings_fn, backup_config_fn, resolve_backup_path_fn, path_raw: str | None = None) -> tuple[bool, str, dict]:
    settings = get_admin_settings_fn()
    cfg = backup_config_fn(settings)
    backup_dir = resolve_backup_path_fn(path_raw or cfg['path'])
    if not backup_dir.exists() or not backup_dir.is_dir():
        return True, 'ok', {'path': str(backup_dir), 'items': [], 'total': 0}

    db_re = re.compile(r'^projectdashboard-db-(\d{8}-\d{6})\.sqlite3$')
    docs_re = re.compile(r'^projectdashboard-docs-(\d{8}-\d{6})\.tar\.gz$')
    grouped: dict[str, dict] = {}
    for p in backup_dir.iterdir():
        if not p.is_file():
            continue
        mdb = db_re.match(p.name)
        if mdb:
            stamp = mdb.group(1)
            item = grouped.setdefault(stamp, {'stamp': stamp, 'db_backup': None, 'docs_backup': None})
            item['db_backup'] = str(p)
            continue
        mdocs = docs_re.match(p.name)
        if mdocs:
            stamp = mdocs.group(1)
            item = grouped.setdefault(stamp, {'stamp': stamp, 'db_backup': None, 'docs_backup': None})
            item['docs_backup'] = str(p)
    items = [v for v in grouped.values() if v.get('db_backup')]
    items.sort(key=lambda x: x.get('stamp') or '', reverse=True)
    for it in items:
        st = str(it.get('stamp') or '')
        try:
            dt = datetime.strptime(st, '%Y%m%d-%H%M%S')
            it['when'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            it['when'] = st
    return True, 'ok', {'path': str(backup_dir), 'items': items, 'total': len(items)}


def get_runtime_build_info(app_dir: Path) -> dict:
    env_mode = str(os.getenv('PDASH_BUILD_INFO_MODE', 'dev')).strip().lower()
    show_in_sidebar = env_mode in {'dev', 'development', 'on', 'true', '1'}

    commit = 'unknown'
    branch = 'unknown'
    source = 'filesystem'

    try:
        res = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=str(app_dir), capture_output=True, text=True, check=False)
        if res.returncode == 0 and (res.stdout or '').strip():
            commit = res.stdout.strip()
            source = 'git'
    except Exception:
        pass

    try:
        res = subprocess.run(['git', 'branch', '--show-current'], cwd=str(app_dir), capture_output=True, text=True, check=False)
        if res.returncode == 0 and (res.stdout or '').strip():
            branch = res.stdout.strip()
    except Exception:
        pass

    return {
        'showInSidebar': show_in_sidebar,
        'mode': env_mode,
        'commit': commit,
        'branch': branch,
        'source': source,
    }


def next_backup_run(get_admin_settings_fn, backup_config_fn) -> dict:
    settings = get_admin_settings_fn()
    cfg = backup_config_fn(settings)
    result = {
        'enabled': bool(cfg.get('enabled')),
        'weekdays': [str(x) for x in (cfg.get('weekdays') or [])],
        'run_time': str(cfg.get('run_time') or '03:00'),
        'next_run_iso': None,
        'next_run_human': None,
    }
    if not result['enabled'] or not result['weekdays']:
        return result
    try:
        hh, mm = result['run_time'].split(':')
        hour = int(hh); minute = int(mm)
    except Exception:
        hour, minute = 3, 0
    allowed = {int(x) for x in result['weekdays'] if str(x).isdigit()}
    now = datetime.now()
    for i in range(0, 15):
        d = now + timedelta(days=i)
        if d.weekday() not in allowed:
            continue
        candidate = d.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            continue
        result['next_run_iso'] = candidate.isoformat()
        result['next_run_human'] = candidate.strftime('%Y-%m-%d %H:%M')
        break
    return result


def restore_backup_from_stamp(list_available_backups_fn, audit_fn, app_dir: Path, stamp: str, path_raw: str | None, actor: str) -> tuple[bool, str]:
    ok, msg, payload = list_available_backups_fn(path_raw)
    if not ok:
        return False, msg
    target = None
    for it in payload.get('items', []):
        if str(it.get('stamp') or '') == str(stamp or ''):
            target = it
            break
    if not target:
        return False, 'Backup selecionado não encontrado'
    db_backup = str(target.get('db_backup') or '').strip()
    docs_backup = str(target.get('docs_backup') or '').strip()
    if not db_backup:
        return False, 'Backup de banco não encontrado para o snapshot selecionado'
    script = app_dir / 'scripts' / 'restore_backup.sh'
    if not script.exists():
        return False, f'Script de restore não encontrado: {script}'
    cmd = [str(script), '--db-backup', db_backup, '--install-dir', str(app_dir), '--allow-non-root']
    if docs_backup:
        cmd.extend(['--docs-backup', docs_backup])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception as e:
        return False, f'Falha ao executar restore: {e}'
    out = (r.stdout or '').strip()
    err = (r.stderr or '').strip()
    detail = (out + ('\n' + err if err else '')).strip()
    if r.returncode != 0:
        return False, f'Restore falhou (code={r.returncode}). {detail[:1200]}'
    audit_fn(actor, 'system.backup.restore', str(stamp), f"path={payload.get('path')} docs={bool(docs_backup)}")
    return True, f'Restore concluído para {stamp}. {detail[:800]}'


def run_system_diagnostics(get_admin_settings_fn, setting_fn, now_iso_fn, db_path: Path, data_dir: Path, base_dir: Path, app_dir: Path) -> dict:
    settings = get_admin_settings_fn()
    repo_url = setting_fn(settings, 'system.git_repo', 'PDASH_GIT_REPO', 'https://github.com/Vieirapa/ProjectDashboard.git')
    repo_branch = setting_fn(settings, 'system.git_branch', 'PDASH_GIT_BRANCH', 'develop')
    diagnostics = {
        'timestamp': now_iso_fn(),
        'checks': [],
        'version': {
            'local': 'unknown',
            'remote': 'unknown',
            'repo': repo_url,
            'branch': repo_branch,
            'updateAvailable': False,
        }
    }

    build_info = get_runtime_build_info(app_dir)

    def add_check(name: str, ok: bool, detail: str):
        diagnostics['checks'].append({'name': name, 'ok': bool(ok), 'detail': detail})

    add_check('Banco de dados', db_path.exists(), str(db_path))
    add_check('Pasta de dados', data_dir.exists(), str(data_dir))
    add_check('Pasta de documentos', base_dir.exists(), str(base_dir))

    if (app_dir / '.git').exists():
        try:
            local = subprocess.check_output(['git', '-C', str(app_dir), 'rev-parse', 'HEAD'], text=True, timeout=6).strip()
            diagnostics['version']['local'] = local
            add_check('Git local', True, local[:12])
        except Exception as e:
            add_check('Git local', False, str(e))
    elif build_info.get('commit') and build_info.get('commit') != 'unknown':
        diagnostics['version']['local'] = str(build_info.get('commit'))
        detail = f"{build_info.get('commit')} ({build_info.get('source', 'runtime')})"
        add_check('Build local', True, detail)
    else:
        add_check('Git local', False, 'instalação sem .git (normal em deploy via rsync)')

    try:
        remote_line = subprocess.check_output(['git', 'ls-remote', repo_url, f'refs/heads/{repo_branch}'], text=True, timeout=10).strip()
        remote = remote_line.split()[0] if remote_line else ''
        if remote:
            diagnostics['version']['remote'] = remote
            add_check('GitHub remoto', True, remote[:12])
        else:
            add_check('GitHub remoto', False, 'branch não encontrada')
    except Exception as e:
        add_check('GitHub remoto', False, str(e))

    local = diagnostics['version']['local']
    remote = diagnostics['version']['remote']
    diagnostics['version']['updateAvailable'] = bool(local and remote and local != 'unknown' and remote != 'unknown' and local != remote)
    return diagnostics
