"""Loopback-only authenticated HTTP gateway for the Pi extension."""

from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from topoptpilot.schemas import ToolRequest


class ToolGateway:
    def __init__(self, service):
        self.service = service
        self.token = secrets.token_urlsafe(32)
        self._capabilities: dict[str, dict] = {}
        self._capability_lock = threading.RLock()
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                if self.path != "/tool":
                    return self._reply(403, {"ok": False, "error": "forbidden"})
                try:
                    size = min(int(self.headers.get("content-length", "0")), 1_000_000)
                    request = ToolRequest.model_validate_json(self.rfile.read(size))
                    capability = gateway._consume_or_get(self.headers.get("x-topopt-token", ""))
                    if not capability:
                        return self._reply(403, {"ok": False, "error": "forbidden"})
                    if request.research_id != capability["research_id"] or request.tool not in capability["allowed_tools"]:
                        return self._reply(403, {"ok": False, "error": "capability_denied"})
                    # The caller never chooses its scope or role.  Both are
                    # bound to the token issued for this Pi process.
                    result = gateway.service.tools.invoke(capability["research_id"], request.tool,
                                                          request.arguments, source="PI_AGENT",
                                                          role=capability["role"])
                    self._reply(200, {"ok": True, "result": result})
                except Exception as exc:
                    self._reply(400, {"ok": False, "error": str(exc)})

            def _reply(self, code, value):
                body = json.dumps(value, default=str).encode("utf-8")
                self.send_response(code)
                self.send_header("content-type", "application/json; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True,
                                       name="topoptpilot-tool-gateway")

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()
        return self

    def issue_capability(self, research_id: str, role: str, allowed_tools: str | tuple[str, ...],
                         *, ttl_seconds: int = 3600) -> str:
        token = secrets.token_urlsafe(32)
        names = tuple(item for item in (allowed_tools.split(",") if isinstance(allowed_tools, str) else allowed_tools) if item)
        with self._capability_lock:
            self._capabilities[token] = {"research_id": research_id, "role": role,
                                         "allowed_tools": frozenset(names), "expires": time.monotonic() + ttl_seconds}
        return token

    def _consume_or_get(self, token: str) -> dict | None:
        # Legacy global token deliberately has no authority once capability
        # issuance is available; it is retained only for diagnostic startup.
        with self._capability_lock:
            value = self._capabilities.get(token)
            if not value or value["expires"] <= time.monotonic():
                self._capabilities.pop(token, None)
                return None
            return value

    def close(self):
        self.server.shutdown()
        self.server.server_close()
