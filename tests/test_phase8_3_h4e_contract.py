"""H4E approval and one-shot filesystem boundaries, using synthetic files."""
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_contract as contract


def test_fresh_scope_refuses_reuse_and_symlinked_ancestor(tmp_path):
    root = tmp_path / 'private/phase8_3_h4e_real'
    root.parent.mkdir(mode=0o700)
    contract.check_fresh_root(root)
    root.mkdir(mode=0o700)
    with pytest.raises(contract.H4EBlocked):
        contract.check_fresh_root(root)
    root.rmdir()
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    root.parent.rmdir()
    root.parent.symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(contract.H4EBlocked):
        contract.check_fresh_root(root)


def test_deadline_is_shared_and_never_reset(monkeypatch):
    monkeypatch.setattr(time, 'monotonic', lambda: 100.0)
    assert contract.remaining(190.0) == 90.0
    monkeypatch.setattr(time, 'monotonic', lambda: 175.0)
    assert contract.remaining(190.0) == 15.0
    for value in (175.0, 174.0, float('nan'), float('inf'), 266.0):
        with pytest.raises(contract.H4EBlocked):
            contract.remaining(value)


def test_no_authority_is_inferred_from_offline_readiness(tmp_path):
    with pytest.raises(contract.H4EBlocked):
        contract.read_authorization(tmp_path / 'missing.json', 'a' * 40, 'b' * 64)
    approval = tmp_path / 'approval.json'
    data = contract.authorization_fields('a' * 40, 'b' * 64)
    data.update(owner_decision='APPROVE_ONE_H4E_ATTEMPT', expires_at=time.time() + 3600)
    approval.write_text(json.dumps(data))
    approval.chmod(0o600)
    assert contract.read_authorization(approval, 'a' * 40, 'b' * 64)['case_id'] == 'h4e_missing_read'
    for key, value in [('case_id', 'h4d_missing_read'), ('physical_request_cap', 4),
                       ('single_run_seconds', 91), ('model', 'other'),
                       ('automatic_retries', True), ('payg', True),
                       ('source_sha', 'c' * 40), ('expires_at', time.time() - 1)]:
        wrong = {**data, key: value}
        approval.write_text(json.dumps(wrong))
        with pytest.raises(contract.H4EBlocked):
            contract.read_authorization(approval, 'a' * 40, 'b' * 64)
