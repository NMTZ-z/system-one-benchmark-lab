"""Explicit H4E identity, approval and one-shot boundaries; no execution."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = 'h4e_missing_read'
PRIVATE = ROOT / 'private/phase8_3_h4e_real'
CASE = PRIVATE / 'runs' / CASE_ID
RECOVERY = PRIVATE / 'recovery'
SOURCE = PRIVATE / 'source'
MODEL = 'step-5-preview'
PROVIDER = 'stepfun'
PROXY = 'http://127.0.0.1:18794'
UPSTREAM = 'https://api.stepfun.com/step_plan/v1/chat/completions'
PHYSICAL_CAP = 3
SECONDS = 90
LEDGER_SHA = '5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb'
HERMES_REV = '4d04303818b61bf3aa09278af48356315515965b'
HERMES_ARCHIVE_SHA256 = '80b083e924d72e6e2203c977992dc521b7ad2040593d0cf53ac52dac0c457b09'


class H4EBlocked(ValueError):
    """A bounded H4E prerequisite failed; never retry automatically."""


def remaining(deadline: float) -> float:
    if type(deadline) not in (float, int) or not math.isfinite(deadline):
        raise H4EBlocked('invalid shared deadline')
    value = deadline - time.monotonic()
    if not 0 < value <= SECONDS:
        raise H4EBlocked('shared deadline expired or exceeds 90 seconds')
    return value


def safe_path(path: Path) -> Path:
    if (not path.is_absolute() or path != path.resolve(strict=False)
            or any(c in str(path) for c in ('"', '\\', '\n', '\r'))
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise H4EBlocked('noncanonical or symlinked H4E path')
    return path


def check_fresh_root(root: Path = PRIVATE) -> None:
    safe_path(root)
    if (root.name != 'phase8_3_h4e_real' or root.parent.name != 'private'
            or root.exists() or root.is_symlink()):
        raise H4EBlocked('H4E evidence root must be unused')
    if root.parent.exists() and (not root.parent.is_dir() or root.parent.stat().st_uid != os.getuid()):
        raise H4EBlocked('H4E evidence parent is not owned')


def authorization_fields(source_sha: str, manifest_sha: str) -> dict:
    if not re.fullmatch('[0-9a-f]{40}', source_sha) or not re.fullmatch('[0-9a-f]{64}', manifest_sha):
        raise H4EBlocked('exact source and release manifest required')
    return {'schema': 'local-system-one/h4e-owner-approval-v1', 'case_id': CASE_ID,
            'source_sha': source_sha, 'manifest_sha256': manifest_sha,
            'model': MODEL, 'provider': PROVIDER, 'upstream': UPSTREAM,
            'physical_request_cap': PHYSICAL_CAP, 'single_run_seconds': SECONDS,
            'historical_ledger_sha256': LEDGER_SHA, 'automatic_retries': False,
            'payg': False, 'active_canary': False}


def read_authorization(path: Path, source_sha: str, manifest_sha: str) -> dict:
    try:
        safe_path(path)
        info = path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 4096):
            raise H4EBlocked('owner approval file must be private and regular')
        data = json.loads(path.read_text())
        expected = authorization_fields(source_sha, manifest_sha)
        if not isinstance(data, dict) or set(data) != set(expected) | {'owner_decision', 'expires_at'}:
            raise H4EBlocked('exact owner approval fields required')
        if any(type(data[k]) is not type(v) or data[k] != v for k, v in expected.items()):
            raise H4EBlocked('owner approval does not match frozen H4E limits')
        expiry = data['expires_at']
        if (data['owner_decision'] != 'APPROVE_ONE_H4E_ATTEMPT'
                or type(expiry) not in (int, float) or not math.isfinite(expiry)
                or not 0 < expiry - time.time() <= 86400):
            raise H4EBlocked('fresh explicit owner approval required')
        return data
    except (OSError, ValueError, TypeError, KeyError):
        raise H4EBlocked('H4E owner approval unavailable or invalid') from None


def original_ledger(owner: Path) -> Path:
    safe_path(owner)
    if not owner.is_dir() or owner.stat().st_uid != os.getuid():
        raise H4EBlocked('original ledger owner is invalid')
    path = owner / 'Projects/system-one-phase8-3/private/phase8_3_native_real/provider_real_ledger.private.jsonl'
    safe_path(path)
    if not path.is_file() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise H4EBlocked('original global ledger is unavailable or unsafe')
    return path


def attest_original_ledger(owner: Path) -> dict:
    path = original_ledger(owner)
    if hashlib.sha256(path.read_bytes()).hexdigest() != LEDGER_SHA:
        raise H4EBlocked('original 8/24 ledger changed')
    return {'historic_reservations': 8, 'global_cap': 24,
            'historic_H1_UNKNOWN': 1, 'ledger_sha256': LEDGER_SHA}


def protected_metadata(owner: Path) -> dict:
    """No credential bytes: track old experiment and production control-file metadata."""
    roots = [owner / '.hermes' / name for name in ('config.yaml', 'auth.json', '.env', 'plugins')]
    roots += [p / 'private/phase8_3_native_real' for p in (owner / 'Projects').glob('system-one-phase8-3*')
              if p != ROOT and p.is_dir() and not p.is_symlink()]
    ledger = original_ledger(owner)
    excluded = {ledger, ledger.with_name(ledger.name + '.lock')}
    rows = {}
    for root in roots:
        paths = [root, *root.rglob('*')] if root.is_dir() and not root.is_symlink() else [root]
        for path in paths:
            if path in excluded: continue
            name = str(path.relative_to(owner))
            try:
                st = path.lstat()
                rows[name] = [st.st_ino, st.st_size, st.st_mode, st.st_uid, st.st_mtime_ns]
            except FileNotFoundError:
                rows[name] = None
    return rows


def write_new_json(path: Path, data: dict) -> None:
    safe_path(path)
    with path.open('x', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        stream.write(json.dumps(data, sort_keys=True, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(path.parent)


def fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
