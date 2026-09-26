from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_public_release.py"


def load_release_module():
    spec = importlib.util.spec_from_file_location("build_public_release", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_release_build_is_allowlisted_and_sanitized(tmp_path):
    output = tmp_path / "public"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (output / "README.md").is_file()
    assert (output / "pyproject.toml").is_file()
    assert (output / "LICENSE").is_file()
    assert (
        output
        / "integrations/hermes/local-system-one-hermes/plugin.yaml"
    ).is_file()
    assert not (output / "private").exists()
    assert not (output / "models").exists()
    assert not (output / "results/raw").exists()

    metadata = json.loads((output / "PUBLIC-RELEASE.json").read_text())
    assert metadata["file_count"] > 0
    assert metadata["license_status"] == "included"
    assert metadata["publish_ready"] is (not metadata["source_dirty"])
    assert (output / "PUBLIC-MANIFEST.sha256").read_text().strip()


def test_public_release_scanner_rejects_user_home_and_token(tmp_path):
    module = load_release_module()
    user_home = "/" + "Users/example/secret\n"
    token = "API_KEY=" + "sk-" + "examplecredential123456789\n"
    (tmp_path / "bad.txt").write_text(user_home + token, encoding="utf-8")
    findings = module.scan_tree(tmp_path)
    assert any("macOS user home" in value for value in findings)
    assert any(
        "credential token prefix" in value or "assigned secret" in value
        for value in findings
    )


def test_allowlist_has_no_private_or_raw_result_prefix():
    module = load_release_module()
    entries = module.load_allowlist(ROOT / "release/public-files.txt")
    assert all(not value.startswith("private/") for value in entries)
    assert all(not value.startswith("results/raw/") for value in entries)