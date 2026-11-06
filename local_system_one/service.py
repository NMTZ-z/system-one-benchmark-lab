"""Small standard-library HTTP service for Local System One."""

from __future__ import annotations

import hmac
import hashlib
import ipaddress
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .engine import DecisionEngine
from .metrics import error_accounting_scope, record_error_once
from .schemas import DecisionRequest
from .workflows import (
    CompletionGate,
    CompletionGateRequest,
    ModelTierGate,
    ModelTierRequest,
    NotificationGate,
    NotificationGateRequest,
    SearchGate,
    SearchGateRequest,
    RetryEscalationGate,
    RetryEscalationRequest,
)

MAX_BODY_BYTES = 1_048_576
MAX_CONNECTIONS = 8
SOCKET_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 10.0


def _invalid_json_constant(_value: str) -> None:
    raise ValueError("non-finite numbers are not accepted")


class _BoundedHTTPServer(ThreadingHTTPServer):
    request_queue_size = MAX_CONNECTIONS
    daemon_threads = True

    def __init__(self, *args: Any):
        self.connections = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.inference = threading.BoundedSemaphore(1)
        super().__init__(*args)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(SOCKET_TIMEOUT_SECONDS)
        return request, address

    def process_request(self, request, address):
        if not self.connections.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.connections.release()

    def handle_error(self, request, client_address):
        pass


def create_server(
    engine: DecisionEngine,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    auth_token: str | None = None,
    owner_token: str | None = None,
) -> ThreadingHTTPServer:
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        raise ValueError("Runtime requires a loopback host")
    if not isinstance(auth_token, str) or not auth_token:
        raise ValueError("Runtime requires a bearer token")
    completion_gate = CompletionGate(engine)
    retry_escalation_gate = RetryEscalationGate(engine)
    search_gate = SearchGate(engine)
    model_tier_gate = ModelTierGate(engine)
    notification_gate = NotificationGate(engine)

    class Handler(BaseHTTPRequestHandler):
        server_version = "LocalSystemOne/0.1"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            # Avoid default request logging because URLs/metadata can become sensitive.
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            supplied_headers = self.headers.get_all("Authorization", [])
            if len(supplied_headers) != 1:
                return False
            supplied = supplied_headers[0]
            expected = f"Bearer {auth_token}"
            return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))

        def _owner_proof(self, action: str) -> str | None:
            nonce = self.headers.get("X-Local-System-One-Challenge", "")
            if not owner_token or not re.fullmatch(r"[0-9a-f]{32}", nonce):
                return None
            return hmac.new(owner_token.encode(), f"{action}:{nonce}".encode(), hashlib.sha256).hexdigest()

        def _read_payload(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            length = int(raw_length)
            if length < 0 or length > MAX_BODY_BYTES:
                raise ValueError("request body is too large")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("request body is incomplete")
            payload = json.loads(raw.decode("utf-8"), parse_constant=_invalid_json_constant)
            if not isinstance(payload, dict):
                raise TypeError("request body must be a JSON object")
            return payload

        def do_GET(self) -> None:
            if self.path == "/_local_system_one/identity":
                nonce = self.headers.get("X-Local-System-One-Challenge", "")
                if not re.fullmatch(r"[0-9a-f]{32}", nonce):
                    self.close_connection = True
                    self._json(400, {"error": "invalid_request"})
                    return
                address = self.connection.getsockname()
                proof = hmac.new(auth_token.encode(), f"identity:{nonce}:{address[0]}:{address[1]}".encode(), hashlib.sha256).hexdigest()
                self._json(200, {"proof": proof})
                return
            self.close_connection = True
            if self.path == "/_local_system_one/owner":
                proof = self._owner_proof("owner")
                if not proof:
                    self._json(403, {"error": "forbidden"})
                    return
                self._json(200, {"proof": proof})
                return
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/health":
                snapshot = engine.health_snapshot()
                if hasattr(engine, "runtime_identity"):
                    snapshot["runtime"] = engine.runtime_identity
                self._json(200, snapshot)
                return
            if self.path == "/metrics":
                self._json(200, engine.metrics_snapshot())
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            self.close_connection = True
            if self.path == "/_local_system_one/stop":
                expected = self._owner_proof("stop")
                supplied = self.headers.get("X-Local-System-One-Authorization", "")
                if not expected or not re.fullmatch(r"[0-9a-f]{64}", supplied) or not hmac.compare_digest(supplied, expected):
                    self._json(403, {"error": "forbidden"})
                    return
                self._json(200, {"stopping": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
                self._json(400, {"error": "invalid_request"})
                return
            if not re.fullmatch(r"[0-9]+", lengths[0]):
                self._json(400, {"error": "invalid_request"})
                return
            length = int(lengths[0])
            if length < 0 or length > MAX_BODY_BYTES:
                self._json(413, {"error": "request_too_large"})
                return
            if not self.server.inference.acquire(blocking=False):
                self._json(503, {"error": "overloaded"})
                return

            respond = self._json
            results: list[tuple[int, dict[str, Any]]] = []
            finished = threading.Event()
            self._json = lambda status, payload: results.append((status, payload))

            def execute() -> None:
                try:
                    with error_accounting_scope():
                        self._handle_post()
                except Exception:
                    results.append((500, {"error": "decision_failed"}))
                finally:
                    self.server.inference.release()
                    finished.set()

            try:
                threading.Thread(target=execute, daemon=True, name="local-system-one-request").start()
            except Exception:
                self.server.inference.release()
                respond(503, {"error": "overloaded"})
                return
            if not finished.wait(REQUEST_TIMEOUT_SECONDS):
                respond(504, {"error": "request_timeout"})
            elif results:
                respond(*results[0])
            else:
                respond(500, {"error": "decision_failed"})

        def _handle_post(self) -> None:
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/v1/workflows/retry-escalation-gate":
                try:
                    payload = self._read_payload()
                    request = RetryEscalationRequest.from_payload(payload)
                    response = retry_escalation_gate.decide(request)
                except TimeoutError:
                    self._json(408, {"error": "request_timeout"})
                    return
                except (ValueError, TypeError) as error:
                    # No user-provided data is echoed in errors/logs.
                    self._json(400, {"error": "invalid_request", "detail": type(error).__name__})
                    return
                except Exception as error:  # noqa: BLE001 - HTTP fail-open boundary
                    record_error_once(engine.metrics, error)
                    self._json(500, {"error": "decision_failed", "detail": type(error).__name__})
                    return
                self._json(200, response)
                return

            if self.path == "/v1/workflows/completion-gate":
                try:
                    payload = self._read_payload()
                    request = CompletionGateRequest.from_payload(payload)
                    response = completion_gate.decide(request)
                except TimeoutError:
                    self._json(408, {"error": "request_timeout"})
                    return
                except (ValueError, TypeError) as error:
                    self._json(400, {"error": "invalid_request", "detail": type(error).__name__})
                    return
                except Exception as error:  # noqa: BLE001 - service boundary
                    record_error_once(engine.metrics, error)
                    self._json(
                        500,
                        {
                            "error": "decision_failed",
                            "detail": type(error).__name__,
                        },
                    )
                    return
                self._json(200, response)
                return

            if self.path == "/v1/workflows/search-gate":
                try:
                    payload = self._read_payload()
                    request = SearchGateRequest.from_payload(payload)
                    response = search_gate.decide(request)
                except TimeoutError:
                    self._json(408, {"error": "request_timeout"})
                    return
                except (ValueError, TypeError) as error:
                    self._json(400, {"error": "invalid_request", "detail": type(error).__name__})
                    return
                except Exception as error:  # noqa: BLE001 - service boundary
                    record_error_once(engine.metrics, error)
                    self._json(
                        500,
                        {
                            "error": "decision_failed",
                            "detail": type(error).__name__,
                        },
                    )
                    return
                self._json(200, response)
                return

            if self.path == "/v1/workflows/model-tier-gate":
                try:
                    payload = self._read_payload()
                    request = ModelTierRequest.from_payload(payload)
                    response = model_tier_gate.decide(request)
                except TimeoutError:
                    self._json(408, {"error": "request_timeout"})
                    return
                except (ValueError, TypeError) as error:
                    self._json(400, {"error": "invalid_request", "detail": type(error).__name__})
                    return
                except Exception as error:  # noqa: BLE001 - service boundary
                    record_error_once(engine.metrics, error)
                    self._json(
                        500,
                        {
                            "error": "decision_failed",
                            "detail": type(error).__name__,
                        },
                    )
                    return
                self._json(200, response)
                return

            if self.path == "/v1/workflows/notification-gate":
                try:
                    payload = self._read_payload()
                    request = NotificationGateRequest.from_payload(payload)
                    response = notification_gate.decide(request)
                except TimeoutError:
                    self._json(408, {"error": "request_timeout"})
                    return
                except (ValueError, TypeError) as error:
                    self._json(400, {"error": "invalid_request", "detail": type(error).__name__})
                    return
                except Exception as error:  # noqa: BLE001 - service boundary
                    record_error_once(engine.metrics, error)
                    self._json(
                        500,
                        {
                            "error": "decision_failed",
                            "detail": type(error).__name__,
                        },
                    )
                    return
                self._json(200, response)
                return

            primitive_by_path = {
                "/v1/choice": "choice",
                "/v1/score": "score",
                "/v1/noul": "noul",
            }
            primitive = primitive_by_path.get(self.path)
            if primitive is None:
                self._json(404, {"error": "not_found"})
                return

            try:
                payload = self._read_payload()
                request = DecisionRequest.from_payload(primitive, payload)
                response = engine.decide(request)
            except TimeoutError:
                self._json(408, {"error": "request_timeout"})
                return
            except (ValueError, TypeError) as error:
                self._json(400, {"error": "invalid_request", "detail": type(error).__name__})
                return
            except Exception as error:  # noqa: BLE001 - service boundary
                record_error_once(engine.metrics, error)
                self._json(
                    500,
                    {
                        "error": "decision_failed",
                        "detail": type(error).__name__,
                    },
                )
                return

            self._json(200, response)

    return _BoundedHTTPServer((host, port), Handler)
