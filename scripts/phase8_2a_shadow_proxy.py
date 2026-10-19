"""Phase 8.2A isolated loopback-only Shadow observation transport recorder.

The proxy forwards request/response bytes UNCHANGED and stores only fixed metadata.
Native provider and Agent sessions run separately; this is NOT a mock Runtime.
Do not expose the listening port or log raw headers, prompts, tools or responses.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import urllib.request
import urllib.error

ROUTES = frozenset({
    "/v1/workflows/completion-gate",
    "/v1/workflows/retry-escalation-gate",
})
LOG_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    destination = "http://127.0.0.1:18782"
    evidence_path: Path

    def log_message(self, *_args):
        return  # Never emit incoming content, headers or tools.

    def do_POST(self):  # noqa: N802
        start = time.perf_counter()
        path = self.path.partition("?")[0]
        if path not in ROUTES or self.client_address[0] != "127.0.0.1":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768:
                self.send_error(413)
                return
            raw = self.rfile.read(size)
            request = json.loads(raw)
            if not isinstance(request, dict):
                self.send_error(400)
                return
        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return
        rid = request.get("request_id")
        # request IDs can encode session IDs: only save a salted one-way hash,
        # never the original linkable identity or a task/response body.
        request_hash = hashlib.sha256((self.server.run_salt + str(rid)).encode()).hexdigest()[:20]
        # Strict causal correlation remains conditional: callers must separately
        # normalize adapter/native events using this SAME private run key.
        secret = getattr(self.server, "correlation_secret", None)
        decision_request_ref = (
            hmac.new(secret, ("decision_request\x00" + rid).encode(),
                     hashlib.sha256).hexdigest()[:32]
            if isinstance(secret, bytes) and len(secret) >= 32
            and isinstance(rid, str) and rid else None
        )
        status, response = 502, b""
        try:
            proxy_request = urllib.request.Request(
                self.destination + path, data=raw,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(proxy_request, timeout=8) as result:
                status, response = result.status, result.read(65536)
        except urllib.error.HTTPError as error:
            status, response = error.code, error.read(65536)
        except (urllib.error.URLError, OSError, TimeoutError):
            status, response = 503, b'{"error":"isolated_runtime_unavailable"}'
        try:
            d = json.loads(response)
            if not isinstance(d, dict):
                d = {}
        except (ValueError, UnicodeDecodeError):
            d = {}
        safe = {
            "phase8_2a": True,
            "phase8_2b": True,
            "run_id": getattr(self.server, "run_id", "legacy"),
            "event_ref": os.urandom(16).hex(),
            "decision_request_ref": decision_request_ref,
            "response_matches_request_id": (
                d.get("request_id") == rid
                if isinstance(rid, str) and rid and isinstance(d.get("request_id"), str)
                else None
            ),
            "correlation_status": "request_ref_only" if decision_request_ref else "missing",
            "ts_unix": round(time.time(), 3),
            "path": path,
            "request_hash": request_hash,
            "http_status": status,
            "duration_ms": round((time.perf_counter() - start) * 1000, 3),
            "workflow": d.get("workflow") if d.get("workflow") in {"completion_gate", "retry_escalation_gate"} else None,
            "decision": d.get("decision") if isinstance(d.get("decision"), str) else None,
            "decision_source": d.get("decision_source") if d.get("decision_source") in {"rule", "model"} else None,
            "backend": d.get("backend") if d.get("backend") in {"rule", "mlx", "ane"} else None,
            "advisory_only": d.get("advisory_only") if isinstance(d.get("advisory_only"), bool) else None,
        }
        with LOG_LOCK:
            with self.evidence_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(safe, separators=(",", ":")) + "\n")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18783)
    parser.add_argument("--destination", default="http://127.0.0.1:18782")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--run-id", default="legacy", help="Bounded public run alias, not native Session ID")
    parser.add_argument("--private-key-file", type=Path, default=None,
                        help="Optional ignored private key used by a separate evidence normalizer")
    opts = parser.parse_args()
    if not 1024 < opts.port < 65536 or opts.destination != "http://127.0.0.1:18782":
        parser.error("Only the audited localhost destination and an unprivileged port are supported")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", opts.run_id):
        parser.error("invalid public run alias")
    os.umask(0o077)
    correlation_key = os.urandom(32)
    if opts.private_key_file is not None:
        private_root = (Path(__file__).resolve().parents[1] / "private").resolve()
        key_file = opts.private_key_file.resolve()
        if not key_file.is_relative_to(private_root) or not key_file.is_file():
            parser.error("correlation key must be an existing ignored private file")
        if key_file.stat().st_mode & 0o077:
            parser.error("correlation key file must not be group/world accessible")
        correlation_key = key_file.read_bytes()
        if len(correlation_key) < 32:
            parser.error("correlation key must contain 32+ random bytes")
    opts.evidence.parent.mkdir(parents=True, exist_ok=True)
    with ThreadingHTTPServer(("127.0.0.1", opts.port), Handler) as server:
        server.run_salt = os.urandom(16).hex()
        server.correlation_secret = correlation_key
        server.run_id = opts.run_id
        Handler.destination = opts.destination
        Handler.evidence_path = opts.evidence
        print(f"8.2A evidence proxy listening on 127.0.0.1:{opts.port}; no raw payload logging", flush=True)
        server.serve_forever(poll_interval=0.5)

if __name__ == "__main__":
    main()
