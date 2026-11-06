"""H4C shared verifier scopes, no real Agent/Provider execution."""
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_h4b_adjudicate as code
import phase8_3_h4b_transaction as tx


def test_H4C_verifier_cannot_read_old_H4B_when_bound_to_new_case():
    original={k:getattr(code,k) for k in (
        "RUN_ID","CASE_DIR","POST_DB","PRE_STATE","POST_STATE",
        "FINAL_REPORT","HMAC_FILE","OBSERVER","PUBLIC")}
    try:
        code.configure_for_case("h4c_missing_read")
        assert code.RUN_ID=="h4c_missing_read"
        assert code.CASE_DIR==code.PRIVATE/"runs/h4c_missing_read"
        assert code.POST_DB==code.PRIVATE/"h4c_recovery/state_after.private.db"
        assert code.PRE_STATE==code.PRIVATE/"h4c_recovery/plugin_before.private.json"
        assert code.POST_STATE==code.PRIVATE/"h4c_recovery/plugin_after.private.json"
        assert code.FINAL_REPORT==code.PRIVATE/"h4c_recovery/rollback_status.private.json"
        assert code.HMAC_FILE==code.PRIVATE/"h4c_correlation_key.private.bin"
        assert code.OBSERVER==code.PRIVATE/"h4c_http.private.jsonl"
        assert code.PUBLIC==ROOT/"results/processed/phase8_3_h4c_real_native_adjudicated.json"
        with pytest.raises(code.AdjudicationBlocked,match="H4C"):
            code.configure_for_case("h4b_missing_read")
    finally:
        for k,v in original.items():
            setattr(code,k,v)
        tx.bind_case("h4b_missing_read")


def test_H4C_replay_initially_blocked_without_new_original_evidence():
    source=(ROOT/"scripts/phase8_3_h4c_adjudicate.py").read_text()
    assert 'configure_for_case("h4c_missing_read")' in source
    assert "source.main()" in source
    assert "phase8_3_h4b_adjudicate" in source
