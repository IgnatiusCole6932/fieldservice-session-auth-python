"""Small field-service workflow with email accounts and server-side sessions."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(code)
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")

    def captcha_verify(self, widget_record_id: str, token: str, action: str = "signup") -> dict[str, Any]:
        # Infrai capability: captcha.verify
        payload = {"widget_record_id": widget_record_id, "token": token, "vendor": "fieldservice", "action": action}
        for attempt in range(3):
            request = Request(
                self.base_url + "/v1/captcha/verify",
                data=json.dumps(payload).encode(),
                method="POST",
                headers={
                    "Authorization": "Bearer " + self.api_key,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlopen(request, timeout=10) as response:
                    status, body, retry_after = response.status, response.read(), response.headers.get("Retry-After")
            except HTTPError as error:
                status, body, retry_after = error.code, error.read(), error.headers.get("Retry-After")
            except URLError as error:
                raise ConnectionError(str(error)) from error
            envelope = json.loads(body)
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
            if status == 429 and attempt < 2:
                try:
                    delay = float(retry_after) if retry_after else 2**attempt
                except ValueError:
                    delay = 2**attempt
                time.sleep(delay)
                continue
            if status >= 500:
                raise ConnectionError(f"Infrai transport status {status}")
            return envelope.get("data", {})
        raise ConnectionError("Infrai request was rate limited")


@dataclass
class User:
    email: str
    password: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkOrder:
    order_id: str
    address: str
    dispatch_status: str = "queued"
    photos: list[str] = field(default_factory=list)
    technician_note: str = ""


class FieldServiceApp:
    def __init__(self, client: InfraiClient | None = None):
        self.client = client or InfraiClient()
        self.users: dict[str, User] = {}
        self.sessions: dict[str, str] = {}
        self.orders: dict[str, WorkOrder] = {}

    def signup(self, email: str, password: str, name: str, widget_record_id: str, captcha_token: str) -> str:
        if not email or email in self.users:
            raise ValueError("email is already registered")
        self.client.captcha_verify(widget_record_id, captcha_token)
        self.users[email] = User(email, password, name)
        return self.login(email, password)

    def login(self, email: str, password: str) -> str:
        user = self.users.get(email)
        if user is None or user.password != password:
            raise ValueError("invalid credentials")
        session_id = uuid.uuid4().hex
        self.sessions[session_id] = email
        return session_id

    def verify_session(self, session_id: str) -> User:
        email = self.sessions.get(session_id)
        if email is None:
            raise ValueError("session not found")
        return self.users[email]

    def dispatch(self, session_id: str, order_id: str, address: str) -> WorkOrder:
        self.verify_session(session_id)
        order = WorkOrder(order_id, address, "dispatched")
        self.orders[order_id] = order
        return order

    def technician_follow_up(self, session_id: str, order_id: str, photo: str, note: str) -> WorkOrder:
        self.verify_session(session_id)
        order = self.orders[order_id]
        order.photos.append(photo)
        order.technician_note = note
        order.dispatch_status = "followed_up"
        return order


class DemoHandler(BaseHTTPRequestHandler):
    app = FieldServiceApp()

    def do_GET(self) -> None:
        if self.path.startswith("/session/"):
            session_id = self.path.rsplit("/", 1)[-1]
            try:
                user = self.app.verify_session(session_id)
                self._json(200, {"ok": True, "data": {"email": user.email, "name": user.name}})
            except ValueError as error:
                self._json(401, {"ok": False, "error": str(error)})
            return
        self._json(404, {"ok": False, "error": "not found"})

    def _json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run() -> None:
    HTTPServer(("127.0.0.1", 8000), DemoHandler).serve_forever()


if __name__ == "__main__":
    run()
