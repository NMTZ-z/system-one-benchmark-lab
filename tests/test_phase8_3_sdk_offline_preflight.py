"""No-provider SDK bootstrap security and request-shape regressions."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase8_3_sdk_offline_preflight as pre


def test_sdk_clean_environment_strips_keys_credential_paths_and_provider_proxy():
    input_env = {
        "STEPFUN_API_KEY": "REDACTED_SECRET_TEST",
        "OPENAI_API_KEY": "FAKE",
        "HERMES_HOME": "/my/production/home",
        "HTTPS_PROXY": "https://hostile.invalid",
        "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX": "a" * 64,
        "PATH": "/bin:/usr/bin",
        "LANG": "C",
    }
    private = Path("/tmp/isolated_sdk_no_key")
    output = pre.clean_environment(private, input_env)
    assert output["HOME"] == output["DSH_HOME"] == str(private)
    assert output["DSH_TELEMETRY_MODE"] == "DISABLED"
    assert output["PATH"] == "/bin:/usr/bin"
    assert set(output).isdisjoint({
        "STEPFUN_API_KEY", "OPENAI_API_KEY", "HERMES_HOME",
        "HTTPS_PROXY", "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX",
    })
    assert "REDACTED_SECRET_TEST" not in str(output)


@pytest.mark.parametrize("forbidden", [
    "session/prompt", "tools/call", "agent/run", "completion",
    "model/complete", "get_credentials",
])
def test_sdk_preflight_can_never_submit_agent_tasks(forbidden):
    with pytest.raises(pre.SDKPreflightError):
        pre.rpc(5, forbidden, {"prompt": "not allowed"})


def test_sdk_rpc_allowlist_and_no_secret_content():
    init = pre.rpc(1, "initialize", {"provider": "stepfun", "model": "step-5-preview"})
    shutdown = pre.rpc(2, "shutdown", {})
    assert '"method":"initialize"' in init
    assert '"method":"shutdown"' in shutdown
    assert 'session/prompt' not in init + shutdown
    assert 'STEPFUN_API_KEY' not in init + shutdown
