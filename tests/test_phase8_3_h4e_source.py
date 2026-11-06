"""Frozen-source gates fail before any runtime or credential operation."""
import hashlib
import io
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_source as source
import phase8_3_h4e_contract as c


@pytest.mark.parametrize('name,kind', [('run_agent.py', 'file'), ('../escape', 'file'),
                                    ('auth.json', 'file'), ('alias', 'link')])
def test_archive_identity_and_safe_members(tmp_path, monkeypatch, name, kind):
    archive = tmp_path / 'source.tar'
    with tarfile.open(archive, 'w') as stream:
        entry = tarfile.TarInfo(name)
        if kind == 'link':
            entry.type = tarfile.SYMTYPE; entry.linkname = '/etc/passwd'
            stream.addfile(entry)
        else:
            entry.size = 4; stream.addfile(entry, io.BytesIO(b'test'))
    with pytest.raises(c.H4EBlocked): source.verify_archive(archive)
    monkeypatch.setattr(c, 'HERMES_ARCHIVE_SHA256', source.digest(archive))
    if name == 'run_agent.py':
        source.prepare_source(archive, tmp_path / 'source')
        assert (tmp_path / 'source/run_agent.py').read_bytes() == b'test'
        assert (tmp_path / 'source/run_agent.py').stat().st_mode & 0o077 == 0
        with pytest.raises(FileExistsError): source.prepare_source(archive, tmp_path / 'source')
    else:
        with pytest.raises(c.H4EBlocked): source.verify_archive(archive)


def test_release_requires_complete_exact_manifest_and_clean_head(tmp_path, monkeypatch):
    monkeypatch.setattr(source, 'ROOT', tmp_path)
    monkeypatch.setattr(source, 'load_allowlist', lambda _: ['one.py'])
    monkeypatch.setattr(source, 'select_source_files', lambda *a, **k: ['one.py'])
    monkeypatch.setattr(source, 'validate_export_paths', lambda _: [])
    def git(args, **kwargs): return 'a' * 40 if args[-1] == 'HEAD' else ''
    monkeypatch.setattr(source.subprocess, 'check_output', git)
    (tmp_path / 'one.py').write_bytes(b'original')
    manifest = tmp_path / 'manifest'
    manifest.write_text(hashlib.sha256(b'original').hexdigest() + '  one.py\n')
    assert source.verify_release('a' * 40, manifest) == source.digest(manifest)
    (tmp_path / 'one.py').write_bytes(b'drift')
    with pytest.raises(c.H4EBlocked): source.verify_release('a' * 40, manifest)
    (tmp_path / 'one.py').write_bytes(b'original')
    manifest.write_text(manifest.read_text() * 2)
    with pytest.raises(c.H4EBlocked): source.verify_release('a' * 40, manifest)
    monkeypatch.setattr(source.subprocess, 'check_output', lambda *a, **k: 'dirty')
    with pytest.raises(c.H4EBlocked): source.verify_release('a' * 40, manifest)
