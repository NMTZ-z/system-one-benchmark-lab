"""Prepare and remove only the credentials and plist owned by this LaunchAgent."""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_system_one.first_run import _access_token, _remove_access_token, _state_dir, _state_lock

LABEL = 'ai.localsystemone.service'


def private_bytes(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o077 or info.st_size > 65536):
            raise ValueError('LaunchAgent ownership file is not private')
        return handle.read(65537)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    info = os.fstat(fd)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            current = path.lstat()
            if (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino):
                path.unlink()
        except OSError:
            pass
        raise


def prepare(repo: Path, plist: Path, logs: Path) -> None:
    directory = _state_dir('launchd')
    with _state_lock(directory):
        marker = directory / 'launchd-owner.json'
        if marker.exists() or marker.is_symlink() or plist.exists() or plist.is_symlink():
            raise ValueError('an existing LaunchAgent or ownership record needs review')
        credential, created = _access_token(directory)
        credential_hash = digest(credential.encode())
        made_plist = False
        try:
            data = plistlib.dumps({
                'Label': LABEL,
                'ProgramArguments': ['/bin/zsh', str(repo / 'scripts/run_local_system_one_service.sh')],
                'WorkingDirectory': str(repo),
                'EnvironmentVariables': {'LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE': str(directory / 'access-token'),
                                         'LOCAL_SYSTEM_ONE_AUTH_TOKEN': '', 'HF_HUB_OFFLINE': '1'},
                'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 30,
                'StandardOutPath': str(logs / 'stdout.log'), 'StandardErrorPath': str(logs / 'stderr.log'),
            })
            write_new(plist, data)
            made_plist = True
            write_new(marker, json.dumps({'schema': 1, 'token_sha256': credential_hash,
                                         'plist_sha256': digest(data)}).encode())
        except BaseException:
            if made_plist and plist.exists() and private_bytes(plist) == data:
                plist.unlink()
            if created:
                _remove_access_token(directory, credential_hash)
            raise


def verify(directory: Path, plist: Path) -> dict:
    value = json.loads(private_bytes(directory / 'launchd-owner.json'))
    if (not isinstance(value, dict) or value.get('schema') != 1
            or any(not isinstance(value.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', value[key])
                   for key in ('token_sha256', 'plist_sha256'))):
        raise ValueError('invalid LaunchAgent ownership record')
    if digest(private_bytes(plist)) != value['plist_sha256']:
        raise ValueError('LaunchAgent configuration was changed; refusing removal')
    return value


def operate(action: str, plist: Path) -> None:
    directory = _state_dir('launchd')
    with _state_lock(directory):
        owner = verify(directory, plist)
        if action == 'remove':
            _remove_access_token(directory, owner['token_sha256'])
            plist.unlink()
            (directory / 'launchd-owner.json').unlink()


if __name__ == '__main__':
    try:
        action, raw_repo, raw_plist, raw_logs = sys.argv[1:]
        repo, plist, logs = Path(raw_repo), Path(raw_plist), Path(raw_logs)
        if action == 'prepare':
            prepare(repo, plist, logs)
        elif action in {'verify', 'remove'}:
            operate(action, plist)
        else:
            raise ValueError('unsupported LaunchAgent operation')
    except (OSError, ValueError, TypeError) as error:
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(f'LaunchAgent operation failed: {detail}', file=sys.stderr)
        raise SystemExit(1)
