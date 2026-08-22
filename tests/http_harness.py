"""로컬 HTTP 테스트 서버 하니스: 외부 네트워크 없이 페처·게이트를 검증한다."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def article_bytes() -> bytes:
    """fixture 한국어 기사 HTML을 바이트로 반환한다."""
    return (FIXTURES / "article_ko.html").read_bytes()


@dataclass(frozen=True)
class FakeResponse:
    """하나의 라우트가 응답할 내용. callable 라우트는 매 요청 새로 계산한다."""

    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0


Route = FakeResponse | Callable[[], FakeResponse]


class _Router(BaseHTTPRequestHandler):
    routes: dict[str, Route]
    request_log: list[tuple[float, float]] | None

    def do_GET(self) -> None:
        route = self.routes.get(self.path)
        if route is None:
            self.send_error(404)
            return
        started = time.perf_counter()
        spec = route() if callable(route) else route
        if spec.delay > 0:
            time.sleep(spec.delay)
        headers = {"Content-Type": "text/html; charset=utf-8", **spec.headers}
        body = spec.body
        self.send_response(spec.status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        if self.request_log is not None:
            self.request_log.append((started, time.perf_counter()))

    def log_message(self, fmt: str, *args: object) -> None:
        """기본 stderr 로그를 끈다(테스트 출력 오염 방지)."""


@contextmanager
def make_server(
    routes: dict[str, Route],
    *,
    request_log: list[tuple[float, float]] | None = None,
) -> Iterator[str]:
    """라우트 테이블로 에페메랄 로컬 서버를 띄우고 base URL을 내어준다."""
    handler = type(
        "BoundRouter",
        (_Router,),
        {"routes": routes, "request_log": request_log},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
