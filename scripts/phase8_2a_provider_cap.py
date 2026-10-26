"""Hard request budget for isolated *real* StepFun Plan Agent E2E.

Every forwarded main/auxiliary/retry request consumes one durable slot *before*
upstream I/O. Neither provider messages nor credentials are stored. This is a
pass-through, not a model stub; an exhausted cap always fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

UPSTREAM = "https://api.stepfun.com/step_plan/v1/chat/completions"
ALLOWED_MODEL = "step-5-preview"
MAX_BODY_BYTES = 2_000_000


class BudgetLedger:
    """Cross-process atomic reservations; never reclaim an attempted call."""

    def __init__(self, path: Path, *, total_limit: int, per_run_limit: int):
        self.path = path
        self.lock_path = path.with_name(path.name + ".lock")
        self.total_limit = total_limit
        self.per_run_limit = per_run_limit

    def _events(self) -> list[dict]:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if not isinstance(value, dict) or value.get("kind") not in {"reserved", "attempted", "responded", "outcome_unknown", "result"}:
                raise ValueError("invalid budget ledger")
            events.append(value)
        return events

    def _append(self, event: dict) -> None:
        with self.path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(event, separators=(",", ":")) + "\n")
            out.flush()
            os.fsync(out.fileno())

    def reserve(self, run: str) -> int | None:
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                events = self._events()
                if run=="h4d_missing_read":
                    # Concurrent physical send is the sole authoritative
                    # reservation boundary; recheck frozen H1-H3 ledger prefix
                    # INSIDE the same exclusive lock as the slot allocation.
                    if not self.path.is_file() or self.path.is_symlink():
                        raise ValueError("H4D original physical ledger prefix missing")
                    raw=self.path.read_bytes()
                    original=raw.splitlines(keepends=True)
                    if (len(original)<30 or
                        hashlib.sha256(b"".join(original[:30])).hexdigest()!=
                          "5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb" or
                        any(v.get("run") not in
                            {"h1_read_off","h2_read_shadow","h3_runtime_down","h4d_missing_read"}
                            for v in events)):
                        raise ValueError("H4D original physical ledger prefix or run set altered")
                used = [v for v in events if v["kind"] == "reserved"]
                if (len(used) >= self.total_limit
                        or sum(v["run"] == run for v in used) >= self.per_run_limit):
                    return None
                slot = len(used) + 1
                self._append({"kind": "reserved", "run": run, "slot": slot})
                return slot
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def mark(self, run: str, slot: int, kind: str, status: int | None = None) -> None:
        """Append a 8.2B request lifecycle fact without altering old result rows.

        Only this controlled HTTP outlet can truthfully emit attempted/response.
        """
        if kind not in {"attempted", "responded", "outcome_unknown"}:
            raise ValueError("unsupported budget lifecycle")
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                events = self._events()
                if not any(e.get("kind") == "reserved" and e.get("run") == run
                           and e.get("slot") == slot for e in events):
                    raise ValueError("budget lifecycle requires a reservation")
                if any(e.get("run") == run and e.get("slot") == slot
                       and e.get("kind") == kind for e in events):
                    raise ValueError("duplicate budget lifecycle")
                if kind != "attempted" and not any(
                    e.get("run") == run and e.get("slot") == slot
                    and e.get("kind") == "attempted" for e in events
                ):
                    raise ValueError("terminal outcome without attempt")
                entry = {"kind": kind, "run": run, "slot": slot}
                if kind == "responded":
                    if not isinstance(status, int) or not 100 <= status <= 599:
                        raise ValueError("invalid provider response status")
                    entry["http_status"] = status
                self._append(entry)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def finish(self, run: str, slot: int, status: int, elapsed_ms: float) -> None:
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                self._append({
                    "kind": "result", "run": run, "slot": slot,
                    "http_status": status, "duration_ms": round(elapsed_ms, 3),
                })
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def counts(self, run: str) -> tuple[int, int]:
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                used = [v for v in self._events() if v["kind"] == "reserved"]
                return len(used), sum(v["run"] == run for v in used)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


class ProviderCapHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_args):
        return  # Never emit provider headers, request text or tool responses.

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        if self.path != "/_budget" or self.client_address[0] != "127.0.0.1":
            self.send_error(404)
            return
        try:
            total, per_run = self.server.ledger.counts(self.server.run_id)
        except (OSError, ValueError):
            self._json(503, {"error": "budget_ledger_invalid"})
            return
        self._json(200, {
            "run": self.server.run_id, "used_total": total, "used_run": per_run,
            "total_cap": self.server.ledger.total_limit,
            "per_run_cap": self.server.ledger.per_run_limit,
        })

    def do_POST(self):  # noqa: N802
        if self.path != "/chat/completions" or self.client_address[0] != "127.0.0.1":
            self.send_error(404)
            return
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not auth.removeprefix("Bearer ").strip():
            self._json(401, {"error": "provider_key_missing"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                self._json(413, {"error": "body_limit"})
                return
            body = self.rfile.read(length)
            value = json.loads(body)
            if not isinstance(value, dict) or value.get("model") != ALLOWED_MODEL:
                self._json(400, {"error": "unapproved_model"})
                return
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "invalid_request"})
            return
        try:
            slot = self.server.ledger.reserve(self.server.run_id)
        except (OSError, ValueError):
            self._json(503, {"error": "budget_ledger_invalid"})
            return
        if slot is None:
            self._json(429, {"error": "phase8_2a_provider_cap_exhausted"})
            return
        began = time.monotonic()
        status = 0
        attempted = False
        try:
            upstream_request = urllib.request.Request(
                self.server.upstream, data=body, method="POST",
                headers={
                    "Authorization": auth,
                    "Content-Type": self.headers.get("Content-Type", "application/json"),
                    "Accept": self.headers.get("Accept", "text/event-stream"),
                },
            )
            # Pre-send durable marker; failure here prevents upstream I/O.
            self.server.ledger.mark(self.server.run_id, slot, "attempted")
            attempted = True
            try:
                upstream = urllib.request.urlopen(upstream_request, timeout=75)
            except urllib.error.HTTPError as exc:
                upstream = exc
            with upstream:
                status = upstream.status
                self.server.ledger.mark(self.server.run_id, slot, "responded", status)
                self.send_response(status)
                self.send_header("Content-Type", upstream.headers.get("Content-Type", "application/json"))
                self.send_header("Connection", "close")
                self.end_headers()
                while chunk := upstream.read1(8192):
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
        except (OSError, TimeoutError):
            if status == 0:
                # Remote execution/billing is unknown after outbound I/O.
                # The local 502 is NOT a remote Provider response.
                if attempted:
                    self.server.ledger.mark(self.server.run_id, slot, "outcome_unknown")
                status = 502
                try:
                    self._json(502, {"error": "real_provider_unavailable"})
                except OSError:
                    pass
        finally:
            # A reserved request is ALWAYS counted even if upstream times out.
            self.server.ledger.finish(
                self.server.run_id, slot, status,
                (time.monotonic() - began) * 1000,
            )


class CappedHTTPServer(ThreadingHTTPServer):
    request_queue_size = 64  # Small concurrent bursts must reach the budget gate.


def make_server(*, port: int, ledger: BudgetLedger, run: str,
                upstream: str = UPSTREAM) -> ThreadingHTTPServer:
    server = CappedHTTPServer(("127.0.0.1", port), ProviderCapHandler)
    server.ledger = ledger
    server.run_id = run
    server.upstream = upstream
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--private-ledger", required=True, type=Path)
    parser.add_argument("--run", required=True)
    parser.add_argument("--total-cap", required=True, type=int)
    parser.add_argument("--per-run-cap", required=True, type=int)
    parser.add_argument("--execute-real-provider", action="store_true", help="Required explicit opt-in to actual Step Plan HTTPS traffic")
    args = parser.parse_args()
    if not args.execute_real_provider:
        parser.error("real provider forwarding requires --execute-real-provider")
    if not (1024 < args.port < 65536 and re.fullmatch(r"[a-z0-9_-]{1,80}", args.run)
            and 1 <= args.per_run_cap <= args.total_cap <= 100):
        parser.error("invalid bounded isolated runner settings")
    # A test helper must not write a ledger or lock into production homes.
    private_root = (Path(__file__).resolve().parents[1] / "private").resolve()
    historic=Path.home()/"Projects/system-one-phase8-3/private/phase8_3_native_real/provider_real_ledger.private.jsonl"
    h4d_exception=(
        args.run=="h4d_missing_read" and not args.private_ledger.is_symlink()
        and args.private_ledger.absolute()==historic.absolute()
        and historic.is_file() and historic.stat().st_mode & 0o077==0
    )
    if not args.private_ledger.resolve().is_relative_to(private_root) and not h4d_exception:
        parser.error("budget ledger must be inside this repo private/ or exact H4D owner-global original")
    if args.run=="h4d_missing_read" and not h4d_exception:
        parser.error("H4D must use exactly the existing global physical ledger")
    if args.run=="h4d_missing_read" and (args.total_cap!=24 or args.per_run_cap!=3 or args.port!=18794):
        parser.error("H4D exact Plan cap/port required")
    if args.run=="h4d_missing_read":
        from phase8_3_transport_closeout import audited_snapshot
        state=audited_snapshot(historic,new_run=args.run)
        if (state["reserved_global"]!=8 or state["reserved_new"]!=0 or
            state["historic_h1_unresolved"]!=1 or
            state["ledger_digest_sha256"]!="5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb"):
            parser.error("H4D global budget no longer frozen at original 8/24")
    os.umask(0o077)
    args.private_ledger.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    ledger = BudgetLedger(args.private_ledger, total_limit=args.total_cap,
                          per_run_limit=args.per_run_cap)
    with make_server(port=args.port, ledger=ledger, run=args.run) as server:
        print(f"Isolated real Step Plan proxy ready: run={args.run}, port={args.port}", flush=True)
        server.serve_forever(poll_interval=0.3)


if __name__ == "__main__":
    main()
