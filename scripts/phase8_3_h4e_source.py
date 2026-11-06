"""Bind H4E execution to a clean public release and the exact Hermes archive."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tarfile

import phase8_3_h4e_contract as contract
from build_public_release import load_allowlist, select_source_files, validate_export_paths

ROOT = contract.ROOT


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_release(source_sha: str, manifest: Path) -> str:
    contract.authorization_fields(source_sha, '0' * 64)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()
    if git('rev-parse', 'HEAD') != source_sha or git('status', '--porcelain'):
        raise contract.H4EBlocked('clean frozen H4E source required')
    entries, manifest_sha = verify_release_files(manifest)
    expected = select_source_files(load_allowlist(ROOT / 'release/public-files.txt'), root=ROOT)
    if sorted(entries) != expected:
        raise contract.H4EBlocked('release does not match the complete public allowlist')
    return manifest_sha


def verify_release_files(manifest: Path) -> tuple[dict, str]:
    """Verify approved content inside the proxy without executing Git or reading its metadata."""
    contract.safe_path(manifest)
    if not manifest.is_file() or manifest.stat().st_size > 250000:
        raise contract.H4EBlocked('public release manifest unavailable')
    entries = {}
    for line in manifest.read_text().splitlines():
        value, name = line.split('  ', 1)
        if name in entries or not re.fullmatch('[0-9a-f]{64}', value):
            raise contract.H4EBlocked('duplicate or malformed release manifest')
        entries[name] = value
    if not entries or validate_export_paths(list(entries)):
        raise contract.H4EBlocked('unsafe or empty release manifest')
    for name, value in entries.items():
        path = contract.safe_path(ROOT / name)
        if not path.is_relative_to(ROOT) or digest(path) != value:
            raise contract.H4EBlocked('release file differs from frozen source')
    return entries, digest(manifest)


def verify_archive(path: Path) -> str:
    contract.safe_path(path)
    if not path.is_file() or path.stat().st_size > 300_000_000 or digest(path) != contract.HERMES_ARCHIVE_SHA256:
        raise contract.H4EBlocked('exact credential-free Hermes Git archive required')
    with tarfile.open(path, mode='r:') as archive:
        for entry in archive:
            name = Path(entry.name)
            if (not name.parts or name.is_absolute() or '..' in name.parts or not (entry.isfile() or entry.isdir())
                    or name.parts[0] in {'.git', '.env', 'auth.json', 'state.db', '.venv'}):
                raise contract.H4EBlocked('unsafe member in pinned source archive')
    return contract.HERMES_ARCHIVE_SHA256


def prepare_source(archive: Path, destination: Path) -> None:
    verify_archive(archive)
    contract.safe_path(destination)
    destination.mkdir(mode=0o700)
    with tarfile.open(archive, mode='r:') as source:
        source.extractall(destination, filter='data')
    for path in destination.rglob('*'):
        path.chmod(0o700 if path.is_dir() or path.stat().st_mode & 0o111 else 0o600)
    verify_archive(archive)
