from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _fake_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    home = tmp_path / "home"
    root = home / ".hermes"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    root.mkdir(parents=True)
    log = tmp_path / "hermes.log"
    fake = bin_dir / "hermes"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'echo "HERMES_HOME=${HERMES_HOME:-} :: $*" >> "$FAKE_HERMES_LOG"\n'
        'if [[ "${1:-}" == plugins && "${2:-}" == validate ]]; then exit 0; fi\n'
        'if [[ "${1:-}" == plugins && "${2:-}" == show ]]; then echo "fake plugin show"; exit 0; fi\n'
        'if [[ "${1:-}" == config && "${2:-}" == get ]]; then exit 1; fi\n'
        "exit 0\n"
    )
    fake.chmod(0o755)
    curl = bin_dir / "curl"
    curl.write_text("#!/usr/bin/env bash\nexit 1\n")
    curl.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "LOCAL_SYSTEM_ONE_HERMES_ROOT": str(root),
            "PATH": f"{bin_dir}:{env['PATH']}",
            "FAKE_HERMES_LOG": str(log),
        }
    )
    return env, root, log


def _run(
    script: str, *args: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPTS / script), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_install_default_is_off_and_excludes_bytecode(tmp_path):
    env, root, log = _fake_env(tmp_path)
    result = _run("install_hermes_system_one_plugin.sh", env=env)
    assert result.returncode == 0, result.stderr
    target = root / "plugins/local-system-one-hermes"
    assert (target / "__init__.py").is_file()
    assert (target / "plugin.yaml").is_file()
    assert not (target / "__pycache__").exists()
    commands = log.read_text()
    assert (
        "config unset plugins.entries.local-system-one-hermes.settings.mode" in commands
    )
    assert "settings.canary_acknowledged false --force" in commands
    assert "plugins enable local-system-one-hermes --no-allow-tool-override" in commands


def test_install_named_profile_and_upgrade_preserves_settings(tmp_path):
    env, root, log = _fake_env(tmp_path)
    (root / "profiles/demo").mkdir(parents=True)
    first = _run("install_hermes_system_one_plugin.sh", "demo", env=env)
    assert first.returncode == 0
    log.write_text("")
    second = _run("install_hermes_system_one_plugin.sh", "demo", env=env)
    assert second.returncode == 0, second.stderr
    assert "existing settings and activation state preserved" in second.stdout
    commands = log.read_text()
    assert "plugins validate" in commands
    assert "config set" not in commands
    assert "plugins enable" not in commands


def test_canary_mode_requires_explicit_ack(tmp_path):
    env, root, log = _fake_env(tmp_path)
    (root / "profiles/demo/plugins/local-system-one-hermes").mkdir(parents=True)
    denied = _run("set_hermes_system_one_mode.sh", "demo", "canary", env=env)
    assert denied.returncode == 2
    assert "explicit acknowledgement" in denied.stderr
    allowed = _run(
        "set_hermes_system_one_mode.sh",
        "demo",
        "canary",
        "--ack-canary",
        env=env,
    )
    assert allowed.returncode == 0, allowed.stderr
    commands = log.read_text()
    assert "settings.canary_acknowledged true --force" in commands
    assert "settings.mode canary --force" in commands


def test_leaving_canary_revokes_ack(tmp_path):
    env, root, log = _fake_env(tmp_path)
    (root / "profiles/demo/plugins/local-system-one-hermes").mkdir(parents=True)
    result = _run("set_hermes_system_one_mode.sh", "demo", "shadow", env=env)
    assert result.returncode == 0
    commands = log.read_text()
    assert "settings.mode shadow --force" in commands
    assert "settings.canary_acknowledged false --force" in commands


def test_uninstall_cleans_code_config_and_plugin_state(tmp_path):
    env, root, log = _fake_env(tmp_path)
    profile = root / "profiles/demo"
    target = profile / "plugins/local-system-one-hermes"
    target.mkdir(parents=True)
    (target / "plugin.yaml").write_text("name: local-system-one-hermes\n")
    state = profile / "plugin-data/agent-plugin-local-system-one-hermes-deadbeef"
    state.mkdir(parents=True)
    (state / "state.json").write_text("{}")
    result = _run("uninstall_hermes_system_one_plugin.sh", "demo", env=env)
    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert not state.exists()
    commands = log.read_text()
    assert "plugins disable local-system-one-hermes" in commands
    assert "plugins remove local-system-one-hermes" in commands
    assert "config unset plugins.entries.local-system-one-hermes" in commands


def test_off_mode_unsets_string_mode_and_revokes_ack(tmp_path):
    env, root, log = _fake_env(tmp_path)
    (root / "profiles/demo/plugins/local-system-one-hermes").mkdir(parents=True)
    result = _run("set_hermes_system_one_mode.sh", "demo", "off", env=env)
    assert result.returncode == 0
    commands = log.read_text()
    assert (
        "config unset plugins.entries.local-system-one-hermes.settings.mode" in commands
    )
    assert "settings.canary_acknowledged false --force" in commands


def test_default_profile_canary_ack_short_form(tmp_path):
    env, root, log = _fake_env(tmp_path)
    (root / "plugins/local-system-one-hermes").mkdir(parents=True)
    result = _run("set_hermes_system_one_mode.sh", "canary", "--ack-canary", env=env)
    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert f"HERMES_HOME={root} :: config set" in commands
    assert "settings.mode canary --force" in commands
