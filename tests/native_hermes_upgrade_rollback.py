"""Verify an intentionally failed upgrade against a marked isolated Hermes profile."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

ROOT = Path(os.environ["LOCAL_SYSTEM_ONE_HERMES_ROOT"]).resolve()
HOME = Path(os.environ["HERMES_HOME"]).resolve()
SOURCE = Path(os.environ["LOCAL_SYSTEM_ONE_SOURCE_ROOT"]).resolve()
if not (ROOT / ".local-system-one-isolated-test").is_file() or HOME.parent != ROOT / "profiles":
    raise SystemExit("This native test requires a marked isolated named profile.")
target = HOME / "plugins/local-system-one-hermes"
real_hermes = shutil.which("hermes")
assert real_hermes and target.is_dir()

subprocess.run([real_hermes, "config", "set",
                "plugins.entries.local-system-one-hermes.settings.model_tier_gate_enabled", "true", "--force"],
               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
before_config = (HOME / "config.yaml").read_bytes()
before_files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()}
with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
    wrapper = Path(tmp) / "hermes"
    wrapper.write_text(
        '#!/bin/sh\nif [ "$1" = plugins ] && [ "$2" = validate ] && '
        '[ "$3" = "$HERMES_HOME/plugins/local-system-one-hermes" ]; then '
        'echo "intentional installed-validation failure" >&2; exit 1; fi\n'
        'exec "$LSO_REAL_HERMES" "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    env = os.environ.copy()
    env.update(PATH=f"{tmp}:{env['PATH']}", LSO_REAL_HERMES=real_hermes)
    result = subprocess.run(["bash", str(SOURCE / "scripts/install_hermes_system_one_plugin.sh"), HOME.name],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    assert result.returncode != 0 and b"intentional installed-validation failure" in result.stderr
after_files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()}
assert after_files == before_files
assert (HOME / "config.yaml").read_bytes() == before_config
config = yaml.safe_load(before_config)
assert config["plugins"]["entries"]["local-system-one-hermes"]["settings"]["model_tier_gate_enabled"] is True
assert "local-system-one-hermes" in config["plugins"]["enabled"]
subprocess.run([real_hermes, "plugins", "validate", str(target)],
               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
print("PASS: failed native upgrade restored plugin bytes and preserved configuration and activation")
