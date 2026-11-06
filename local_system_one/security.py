"""Private local bearer credentials shared by the managed Runtime and clients."""

from __future__ import annotations

import os
import hashlib
import hmac
import http.client
import json
from pathlib import Path
import re
import secrets
import stat
import urllib.parse


def access_token_path(profile: str | None = None) -> Path:
    profile = profile or os.environ.get("LOCAL_SYSTEM_ONE_PROFILE", "default")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", profile):
        raise ValueError("invalid profile name")
    root = Path(os.environ.get("LOCAL_SYSTEM_ONE_STATE_HOME", Path.home() / "Library/Application Support/Local System One"))
    return root / "profiles" / profile / "access-token"


def read_access_token(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "r", encoding="ascii") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 128):
            raise ValueError("access token file is not private")
        token = handle.read(129)
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError("invalid access token file")
    return token


def verified_request(base_url: str, method: str, path: str, body: bytes | None,
                     token: str, timeout: float) -> tuple[int, bytes]:
    """Authenticate the listener before sending a token or task on the same socket."""
    target = urllib.parse.urlsplit(base_url)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=timeout)
    try:
        nonce = secrets.token_hex(16)
        connection.request("GET", "/_local_system_one/identity", headers={"X-Local-System-One-Challenge": nonce})
        response = connection.getresponse()
        identity = response.read(1025)
        if response.status != 200:
            raise RuntimeError(f"Local System One HTTP {response.status}")
        try:
            proof = json.loads(identity)["proof"]
        except (ValueError, KeyError, TypeError):
            raise RuntimeError("Local System One HTTP 401") from None
        sock = connection.sock
        peer = sock.getpeername() if sock else ("", 0)
        expected = hmac.new(token.encode(), f"identity:{nonce}:{peer[0]}:{peer[1]}".encode(), hashlib.sha256).hexdigest()
        if not isinstance(proof, str) or not hmac.compare_digest(proof, expected) or sock is None:
            raise RuntimeError("Local System One HTTP 401")
        # Reconnecting after verification would send the secret to an unverified listener.
        def no_reconnect():
            raise ConnectionError("verified Runtime connection was closed")
        connection.connect = no_reconnect
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        if connection.sock is not sock:
            raise ConnectionError("verified Runtime connection changed")
        response = connection.getresponse()
        return response.status, response.read(1_048_577)
    finally:
        connection.close()
