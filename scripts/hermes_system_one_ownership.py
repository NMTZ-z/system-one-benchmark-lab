"""Identify and remove only the plugin files installed by this project."""

import hashlib
import json
import re
import sys
from pathlib import Path

MARKER = ".local-system-one-install.json"
FILES = ("__init__.py", "plugin.yaml", "README.md")
LEGACY = {
    "__init__.py": "23571e6d457c711256c7e628c19c99b1e13ed048ce97bc281b08e022d7c5a79a",
    "plugin.yaml": "3beed4fea99e526f73c0acf9d4b7f92ec8aa5f795b9e151f60fa066f4e734a1d",
    "README.md": "83ffabc65617e53aba7bb263839bfa11b9add9148031b5959864533cae006e67",
}


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing file or symbolic link")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(path):
    if path.is_symlink() or not path.is_dir():
        raise ValueError("plugin directory is missing or is a symbolic link")
    marker = path / MARKER
    if marker.exists():
        if marker.is_symlink():
            raise ValueError("invalid ownership marker")
        data = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid ownership marker")
        expected = data.get("files") if data.get("schema") == 1 else None
        if not isinstance(expected, dict) or not {"__init__.py", "plugin.yaml"} <= set(expected) <= set(FILES):
            raise ValueError("invalid ownership marker")
    else:
        expected = {name: value for name, value in LEGACY.items() if (path / name).exists()}
        if not {"__init__.py", "plugin.yaml"} <= set(expected):
            raise ValueError("unrecognized plugin installation")
    if any(digest(path / name) != value for name, value in expected.items()):
        raise ValueError("installed plugin files differ from their ownership record")
    allowed = set(expected) | {MARKER, "__pycache__"}
    if any(entry.name not in allowed or entry.is_symlink() for entry in path.iterdir()):
        raise ValueError("plugin directory contains unrecognized files")
    cache = path / "__pycache__"
    if cache.exists():
        if not cache.is_dir() or any(
            entry.is_symlink() or not entry.is_file()
            or not re.fullmatch(r"[A-Za-z0-9_.-]+\.pyc", entry.name)
            for entry in cache.iterdir()
        ):
            raise ValueError("plugin bytecode directory contains unrecognized files")
    return expected


def remove_sessions(path):
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or not path.is_dir():
        raise ValueError("invalid session directory")
    files = list(path.iterdir())
    for file in files:
        if (not re.fullmatch(r"session-[0-9]+-[0-9a-f]{32}\.json", file.name)
                or file.is_symlink() or not file.is_file() or file.stat().st_size > 16384):
            raise ValueError("session directory contains an unrecognized file")
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != "0.10.0":
            raise ValueError("session directory contains an unrecognized record")
    for file in files:
        file.unlink()
    path.rmdir()


def main():
    action, path = sys.argv[1], Path(sys.argv[2])
    if action == "mark":
        expected = {name: digest(path / name) for name in FILES if (path / name).exists()}
        (path / MARKER).write_text(json.dumps({"schema": 1, "files": expected}) + "\n", encoding="utf-8")
    elif action in {"verify", "remove"}:
        expected = verify(path)
        if action == "remove":
            cache = path / "__pycache__"
            if cache.exists():
                for entry in cache.iterdir():
                    entry.unlink()
                cache.rmdir()
            for name in expected:
                (path / name).unlink()
            if (path / MARKER).exists():
                (path / MARKER).unlink()
            path.rmdir()
    elif action == "remove-sessions":
        remove_sessions(path)
    else:
        raise ValueError("unsupported action")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"Plugin ownership check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
