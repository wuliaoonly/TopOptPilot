"""Short-lived, single-use WebSocket tickets for local desktop streams."""

from __future__ import annotations

import secrets
import threading
import time


class WebSocketTicketBroker:
    def __init__(self, ttl_seconds: int = 20):
        self.ttl_seconds = ttl_seconds
        self._records: dict[str, tuple[str, str, float]] = {}
        self._lock = threading.Lock()

    def issue(self, owner_type: str, owner_id: str) -> dict[str, object]:
        ticket = secrets.token_urlsafe(32)
        with self._lock:
            now = time.monotonic()
            self._records = {
                key: value for key, value in self._records.items() if value[2] > now
            }
            self._records[ticket] = (owner_type, owner_id, now + self.ttl_seconds)
        return {"ticket": ticket, "expiresIn": self.ttl_seconds}

    def consume(self, ticket: str, owner_type: str, owner_id: str) -> bool:
        with self._lock:
            record = self._records.pop(ticket, None)
        return bool(
            record
            and record[0] == owner_type
            and record[1] == owner_id
            and record[2] > time.monotonic()
        )


broker = WebSocketTicketBroker()

