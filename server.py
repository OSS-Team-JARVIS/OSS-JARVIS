import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.os_controller import OSController


def resolve_delete_targets(payload: dict, controller: OSController, search_query: str):
    selected_files = payload.get("selectedFiles") or []
    if selected_files:
        return [str(path) for path in selected_files]

    return [str(path) for path in controller.search_files(search_query or "")]


def find_html_file() -> Path:
    candidates = [
        ROOT / "test.html",
        ROOT / "html" / "test.html",
        ROOT.parent / "test.html",
        ROOT.parent / "html" / "test.html",
        Path("C:/Users/peron/OneDrive/Desktop/OSS-JARVIS/test.html"),
        Path("C:/Users/peron/OneDrive/Desktop/OSS-JARVIS/html/test.html"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("test.html 파일을 찾을 수 없습니다.")


HTML_FILE = find_html_file()


def resolve_folder_path(folder_path: str) -> Path:
    raw_path = folder_path.strip()
    if not raw_path:
        raise ValueError("폴더 경로를 입력하세요.")

    candidate = Path(raw_path).expanduser()
    candidates = [candidate]

    if not candidate.is_absolute():
        candidates.append(ROOT / candidate)
        candidates.append(ROOT.parent / candidate)

    for path in candidates:
        try_path = path.resolve()
        if try_path.exists() and try_path.is_dir():
            if not os.access(try_path, os.R_OK | os.X_OK):
                raise PermissionError("경로를 찾을 수 없거나 접근 권한이 없습니다.")
            return try_path

    if candidate.is_absolute():
        raise FileNotFoundError("경로를 찾을 수 없거나 접근 권한이 없습니다.")

    raise FileNotFoundError("경로를 찾을 수 없거나 접근 권한이 없습니다.")


class OsControllerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/test.html"):
            self._serve_html(HTML_FILE)
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/os-controller":
            self._send_json(404, {"error": "Not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")

        try:
            payload = json.loads(body or "{}")
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"잘못된 JSON 형식입니다: {exc}"})
            return

        action = payload.get("action", "search")
        folder_path = payload.get("folderPath", "").strip()
        search_query = payload.get("searchQuery", "").strip()

        print(f"[API] action={action} folder_path={folder_path} keyword={search_query}")

        if not folder_path:
            self._send_json(400, {"error": "폴더 경로를 입력하세요."})
            return

        try:
            resolved_folder_path = resolve_folder_path(folder_path)
            controller = OSController(resolved_folder_path)

            if action == "search":
                results = controller.search_files(search_query or "")
                files = [str(path) for path in results]
                self._send_json(200, {
                    "files": files,
                    "message": f"{len(files)}개의 파일을 찾았습니다."
                })
            elif action == "classify":
                result = controller.classify_files_by_extension()
                self._send_json(200, {
                    "message": f"{len(result)}개 폴더로 파일 정리가 완료되었습니다."
                })
            elif action == "delete":
                targets = resolve_delete_targets(payload, controller, search_query)
                deleted = []
                skipped = []
                for target in targets:
                    try:
                        controller.delete_item(target)
                        deleted.append(str(target))
                    except Exception as exc:
                        skipped.append(str(exc))
                message = f"{len(deleted)}개의 파일을 삭제했습니다."
                if skipped:
                    detail = "; ".join(skipped[:3])
                    message += f" ({len(skipped)}개는 건너뛰었습니다: {detail})"
                self._send_json(200, {
                    "deleted": deleted,
                    "skipped": skipped,
                    "message": message
                })
            else:
                self._send_json(400, {"error": "지원하지 않는 액션입니다."})
        except Exception as exc:
            message = str(exc) if str(exc) else "경로를 찾을 수 없거나 접근 권한이 없습니다."
            if "경로를 찾을 수 없거나 접근 권한이 없습니다." in message:
                self._send_json(400, {"error": message})
            else:
                self._send_json(400, {"error": message})

    def _serve_html(self, file_path: Path) -> None:
        content = file_path.read_text(encoding="utf-8")
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), OsControllerHandler)
    print("서버 실행 중: http://127.0.0.1:8000")
    server.serve_forever()
