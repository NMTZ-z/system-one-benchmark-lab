"""Actual kernel identity checks inside Seatbelt, including denied queries."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def test_kernel_identity_and_group_queries_work_without_setuid_ps(tmp_path):
    if sys.platform != 'darwin':
        pytest.skip('Darwin libproc and Seatbelt required')
    from phase8_3_init_diagnostic import build_policy
    from phase8_3_h4e_process_identity import identity, group_members
    python = Path(sys.executable)
    policy = build_policy(owner=Path.home(), readable=[ROOT / 'scripts', python.parent.parent.resolve(),
        python.resolve().parent.parent], mutable=tmp_path)
    policy += '(allow process-info-pidinfo)\n(allow process-info-listpids)\n'
    code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
            'from phase8_3_h4e_process_identity import identity,group_members;'
            'print(json.dumps({"identity":identity(int(sys.argv[2])),"members":group_members(int(sys.argv[2]))}))')
    process = subprocess.Popen(['/bin/sleep', '10'], start_new_session=True)
    try:
        result = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, str(python), '-I', '-B', '-c', code,
            str(ROOT / 'scripts'), str(process.pid)], capture_output=True, text=True, timeout=4)
        assert result.returncode == 0, result.stderr
        record = json.loads(result.stdout)
        assert record['identity'] == identity(process.pid)
        assert record['identity']['pid'] == record['identity']['pgid'] == process.pid
        assert record['identity']['uid'] == os.getuid() and record['members'] == [process.pid]
        denied = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy + '\n(deny process-info-pidinfo)\n(deny process-info-listpids)\n',
            str(python), '-I', '-B', '-c', code, str(ROOT / 'scripts'), str(process.pid)],
            capture_output=True, text=True, timeout=4)
        assert denied.returncode != 0 and 'PermissionError' in denied.stderr
    finally:
        process.terminate(); process.wait(timeout=3)
    assert identity(process.pid) is None and group_members(process.pid) == []
