import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
SRC_ROOT = ROOT / "src"
TEXT_ENCODING = "utf-8"
EMPTY_CRAWL_NOTICE = "[Notice] Crawled data is empty."

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from src.os_controller import OSController

_os_script_module_cache = None


class HttpError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def resolve_delete_targets(payload: dict, controller: OSController, search_query: str):
    selected_files = payload.get("selectedFiles") or []
    if selected_files:
        return [str(path) for path in selected_files]

    return [str(path) for path in controller.search_files(search_query or "")]


def find_html_file() -> Path:
    candidates = [
        ROOT / "static" / "index.html",
        ROOT / "index.html",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("index.html 파일을 찾을 수 없습니다.")


def _normalize_path_input(path_value: str) -> Path:
    raw = (path_value or "").strip()
    if not raw:
        raise HttpError(400, "로컬 경로를 입력하세요.")

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def validate_local_path(
    path_value: str,
    *,
    require_directory: bool = False,
    require_file: bool = False,
    must_be_readable: bool = True,
    must_be_writable: bool = False,
) -> Path:
    """요청 경로 검증 미들웨어: 존재 여부(os.path.exists)와 권한을 함께 검사한다."""
    target = _normalize_path_input(path_value)

    if not os.path.exists(target):
        raise HttpError(400, f"경로가 존재하지 않습니다: {target}")

    if require_directory and not os.path.isdir(target):
        raise HttpError(400, f"폴더 경로가 아닙니다: {target}")
    if require_file and not os.path.isfile(target):
        raise HttpError(400, f"파일 경로가 아닙니다: {target}")

    access_mode = 0
    if must_be_readable:
        access_mode |= os.R_OK
    if require_directory:
        access_mode |= os.X_OK
    if must_be_writable:
        access_mode |= os.W_OK

    if access_mode and not os.access(target, access_mode):
        raise HttpError(403, f"경로 접근 권한이 없습니다: {target}")

    return target


def _load_os_script_module():
    global _os_script_module_cache
    if _os_script_module_cache is not None:
        return _os_script_module_cache

    script_path = ROOT / "OS-Script.py"
    if not script_path.exists():
        raise HttpError(500, f"OS 스크립트를 찾을 수 없습니다: {script_path}")

    spec = importlib.util.spec_from_file_location("oss_jarvis_os_script", script_path)
    if spec is None or spec.loader is None:
        raise HttpError(500, "OS 스크립트를 불러올 수 없습니다.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _os_script_module_cache = module
    return module


def _mock_crawl_result(query: str) -> dict[str, Any]:
    """네트워크와 검색 API 키 없이 통합 플로우를 검증할 수 있는 목 데이터입니다."""
    return {
        "query": query,
        "results": [
            {
                "url": "mock://jarvis/local-result",
                "final_url": "mock://jarvis/local-result",
                "status": 200,
                "title": f"Mock crawl result: {query}",
                "content": (
                    f"검색어 '{query}'에 대한 로컬 목 데이터입니다. "
                    "크롤러에서 수집된 본문을 보고서 모듈로 전달하는 통합 테스트용 내용입니다."
                ),
                "content_length": 86,
                "extractor": "mock",
                "fetched_at": "2026-08-26T00:00:00+00:00",
            }
        ],
        "failures": [],
    }


def _run_crawler(
    query: str,
    count: int,
    max_pages: int,
    max_chars: int,
    *,
    use_mock: bool = False,
) -> dict[str, Any]:
    if not query.strip():
        raise HttpError(400, "크롤링 검색어(query)를 입력하세요.")

    if use_mock:
        return _mock_crawl_result(query)

    from jarvis_crawler.pipeline import build_default_pipeline

    async def _inner() -> dict[str, Any]:
        pipeline = build_default_pipeline(max_pages=max_pages, max_chars=max_chars)
        bundle = await pipeline.run(query, count=count)
        return json.loads(bundle.to_json())

    try:
        return asyncio.run(_inner())
    except Exception as exc:
        raise HttpError(
            502,
            "크롤링에 실패했습니다. 검색 API 키, 네트워크, robots.txt 또는 fetcher 오류를 확인하세요. "
            f"상세: {exc}",
        ) from exc


def _run_os_controller(
    folder_path: str,
    action: str,
    search_query: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    resolved_folder_path = validate_local_path(
        folder_path,
        require_directory=True,
        must_be_readable=True,
    )
    controller = OSController(resolved_folder_path)

    if action == "search":
        results = controller.search_files(search_query or "")
        files = [str(path) for path in results]
        return {
            "files": files,
            "message": f"{len(files)}개의 파일을 찾았습니다.",
        }

    if action == "classify":
        result = controller.classify_files_by_extension()
        return {
            "folders": {name: [str(path) for path in paths] for name, paths in result.items()},
            "message": f"{len(result)}개 폴더로 파일 정리가 완료되었습니다.",
        }

    if action == "delete":
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
            message += f" ({len(skipped)}개는 건너뜀)"
        return {
            "deleted": deleted,
            "skipped": skipped,
            "message": message,
        }

    raise HttpError(400, "지원하지 않는 OS 제어 액션입니다. (search/classify/delete)")


def _run_os_script_command(command: str, timeout: int, cwd: str | None) -> dict[str, Any]:
    if not command.strip():
        raise HttpError(400, "실행할 command를 입력하세요.")

    run_cwd = ROOT
    if cwd:
        run_cwd = validate_local_path(cwd, require_directory=True, must_be_readable=True)

    os_script = _load_os_script_module()
    result = os_script.run_command(command=command, timeout=timeout, cwd=str(run_cwd))
    return result


def _run_feedback_loop(timeout: int) -> dict[str, Any]:
    script_path = ROOT / "feedback_loop.py"
    if not script_path.exists():
        raise HttpError(500, f"피드백 루프 스크립트를 찾을 수 없습니다: {script_path}")

    try:
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HttpError(504, f"피드백 루프가 {timeout}초 내 완료되지 않았습니다.") from exc

    return {
        "success": completed.returncode == 0,
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_report_pipeline(project_name: str, raw_data_path: str | None, use_mock: bool) -> dict[str, Any]:
    from jarvis_report.main import run_pipeline

    effective_project_name = (project_name or "JARVIS_AI_Report").strip() or "JARVIS_AI_Report"
    if raw_data_path:
        resolved_data_file = validate_local_path(
            raw_data_path,
            require_file=True,
            must_be_readable=True,
        )
    else:
        resolved_data_file = ROOT / "jarvis_report" / "raw_data.txt"
        validate_local_path(str(resolved_data_file), require_file=True, must_be_readable=True)

    report_paths = run_pipeline(
        project_name=effective_project_name,
        raw_data_path=str(resolved_data_file),
        use_mock=use_mock,
    )
    return {
        "success": True,
        "message": "보고서 생성이 완료되었습니다.",
        "project_name": effective_project_name,
        "raw_data_path": str(resolved_data_file),
        "use_mock": use_mock,
        "report_paths": report_paths,
    }


def _save_crawl_result(crawl_result: dict[str, Any], requested_path: str | None) -> Path:
    """크롤링 결과를 보고서 입력용 UTF-8 텍스트 파일로 저장합니다."""
    if requested_path:
        target = _normalize_path_input(requested_path)
        parent = target.parent
        if not os.path.exists(parent):
            parent.mkdir(parents=True, exist_ok=True)
        validate_local_path(
            str(parent),
            require_directory=True,
            must_be_readable=True,
            must_be_writable=True,
        )
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="jarvis_run_", dir=str(ROOT)))
        target = temp_dir / "raw_data.txt"

    pages = crawl_result.get("results", [])
    failures = crawl_result.get("failures", [])
    sections = []
    for page in pages:
        sections.append(
            "\n".join(
                [
                    f"Source URL: {page.get('url', '')}",
                    f"Title: {page.get('title', '')}",
                    "Content:",
                    str(page.get("content", "")),
                ]
            )
        )
    if failures:
        sections.append(
            "Crawl failures:\n" + "\n".join(json.dumps(item, ensure_ascii=False) for item in failures)
        )

    crawl_text = "\n\n".join(sections).strip()
    target.write_text(
        crawl_text or EMPTY_CRAWL_NOTICE,
        encoding=TEXT_ENCODING,
    )
    return target.resolve()


def _run_parameterized_feedback(payload: dict[str, Any], crawl_result: dict[str, Any]) -> dict[str, Any]:
    """크롤링 결과 또는 요청받은 코드/오류 텍스트를 피드백 루프에 전달합니다."""
    if bool(payload.get("useMockFeedback", False)):
        return {
            "success": True,
            "mode": "mock",
            "message": "목 피드백 루프가 입력 결과를 검토했습니다.",
            "reviewed_chars": len(json.dumps(crawl_result, ensure_ascii=False)),
        }

    from feedback_loop import run_feedback

    code_text = str(payload.get("codeText", ""))
    error_log = str(payload.get("errorLog", ""))
    if not code_text and not error_log:
        error_log = "크롤링 결과 자동 검토 요청"
        code_text = json.dumps(crawl_result, ensure_ascii=False)

    return run_feedback(
        code_text=code_text,
        error_log=error_log,
        model=str(payload.get("feedbackModel", "qwen2.5:3b")),
        max_attempts=int(payload.get("feedbackAttempts", 1)),
        apply_fix=False,
        execute=False,
    )


class OsControllerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return

        if parsed.path in ("/", "/index.html"):
            self._serve_html(find_html_file())
            return

        if parsed.path.startswith("/static/"):
            requested = unquote(parsed.path[len("/static/"):]).lstrip("/")
            file_path = (ROOT / "static" / requested).resolve()
            static_root = (ROOT / "static").resolve()
            if static_root not in file_path.parents and file_path != static_root:
                self._send_json(403, {"error": "정적 파일 접근이 차단되었습니다."})
                return
            if not file_path.exists() or not file_path.is_file():
                self._send_json(404, {"error": "정적 파일을 찾을 수 없습니다."})
                return
            self._serve_file(file_path)
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json_body()
        if payload is None:
            return

        try:
            if parsed.path == "/api/path/validate":
                self._handle_validate_path(payload)
                return

            if parsed.path == "/api/crawler/run":
                self._handle_crawler_run(payload)
                return

            if parsed.path in ("/api/os-controller", "/api/os-control"):
                self._handle_os_control(payload)
                return

            if parsed.path == "/api/os-script/run":
                self._handle_os_script_run(payload)
                return

            if parsed.path == "/api/feedback-loop/run":
                self._handle_feedback_loop_run(payload)
                return

            if parsed.path == "/api/report/run":
                self._handle_report_run(payload)
                return

            if parsed.path == "/api/workflow/run":
                self._handle_workflow_run(payload)
                return

            if parsed.path == "/api/run-all":
                self._handle_run_all(payload)
                return

            self._send_json(404, {"error": "Not found"})
        except HttpError as exc:
            self._send_json(exc.status_code, {"error": exc.message})
        except Exception as exc:
            self._send_json(500, {"error": str(exc) or "서버 내부 오류"})

    def _read_json_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            return json.loads(body or "{}")
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"잘못된 JSON 형식입니다: {exc}"})
            return None

    def _handle_validate_path(self, payload: dict[str, Any]) -> None:
        path_value = payload.get("path", "")
        require_directory = bool(payload.get("requireDirectory", False))
        require_file = bool(payload.get("requireFile", False))
        writable = bool(payload.get("mustBeWritable", False))
        resolved = validate_local_path(
            path_value,
            require_directory=require_directory,
            require_file=require_file,
            must_be_writable=writable,
        )
        self._send_json(
            200,
            {
                "valid": True,
                "resolvedPath": str(resolved),
                "exists": os.path.exists(resolved),
                "readable": os.access(resolved, os.R_OK),
                "writable": os.access(resolved, os.W_OK),
            },
        )

    def _handle_crawler_run(self, payload: dict[str, Any]) -> None:
        query = str(payload.get("query", ""))
        count = int(payload.get("count", 10))
        max_pages = int(payload.get("maxPages", 8))
        max_chars = int(payload.get("maxChars", 10000))
        use_mock = bool(payload.get("useMockCrawler", False))

        crawl_result = _run_crawler(query, count, max_pages, max_chars, use_mock=use_mock)
        self._send_json(
            200,
            {
                "message": "크롤링이 완료되었습니다.",
                "result": crawl_result,
            },
        )

    def _handle_os_control(self, payload: dict[str, Any]) -> None:
        action = str(payload.get("action", "search"))
        folder_path = str(payload.get("folderPath", "")).strip()
        search_query = str(payload.get("searchQuery", "")).strip()

        if not folder_path:
            raise HttpError(400, "folderPath를 입력하세요.")

        result = _run_os_controller(folder_path, action, search_query, payload)
        self._send_json(200, result)

    def _handle_os_script_run(self, payload: dict[str, Any]) -> None:
        command = str(payload.get("command", ""))
        timeout = int(payload.get("timeout", 30))
        cwd = payload.get("cwd")
        if cwd is not None:
            cwd = str(cwd)
        result = _run_os_script_command(command, timeout, cwd)
        self._send_json(200, result)

    def _handle_feedback_loop_run(self, payload: dict[str, Any]) -> None:
        timeout = int(payload.get("timeout", 180))
        result = _run_feedback_loop(timeout)
        self._send_json(200, result)

    def _handle_report_run(self, payload: dict[str, Any]) -> None:
        project_name = str(payload.get("projectName", "JARVIS_AI_Report"))
        raw_data_path = payload.get("rawDataPath")
        if raw_data_path is not None:
            raw_data_path = str(raw_data_path)
        use_mock = bool(payload.get("useMock", False))

        result = _run_report_pipeline(project_name, raw_data_path, use_mock)
        self._send_json(200, result)

    def _handle_run_all(self, payload: dict[str, Any]) -> None:
        """크롤링 -> 결과 저장/OS 제어 -> 피드백 -> 보고서를 순차 실행합니다."""
        timeline: list[dict[str, str]] = []
        query = str(payload.get("query", "")).strip()
        if not query:
            raise HttpError(400, "run-all 실행에는 query가 필요합니다.")

        crawl_result = _run_crawler(
            query=query,
            count=int(payload.get("count", 10)),
            max_pages=int(payload.get("maxPages", 8)),
            max_chars=int(payload.get("maxChars", 10000)),
            use_mock=bool(payload.get("useMockCrawler", False)),
        )
        timeline.append({"step": "crawl", "status": "done", "detail": "크롤링 완료"})
        requested_raw_path = payload.get("rawDataPath")
        if not requested_raw_path and payload.get("rawDataDir"):
            requested_raw_path = str(Path(str(payload["rawDataDir"])).expanduser() / "raw_data.txt")
        raw_data_path = _save_crawl_result(crawl_result, requested_raw_path)

        os_result = None
        folder_path = str(payload.get("folderPath", "")).strip()
        if folder_path:
            os_result = _run_os_controller(
                folder_path,
                str(payload.get("osAction", "search")),
                str(payload.get("searchQuery", "")).strip(),
                payload,
            )
            timeline.append({"step": "os_control", "status": "done", "detail": "OS 파일 작업 완료"})
        else:
            timeline.append({"step": "os_control", "status": "skipped", "detail": "folderPath 미입력"})

        feedback_result = None
        if bool(payload.get("runFeedback", False)):
            feedback_result = _run_parameterized_feedback(payload, crawl_result)
            timeline.append({"step": "feedback", "status": "done", "detail": "AI 피드백 완료"})
        else:
            timeline.append({"step": "feedback", "status": "skipped", "detail": "선택하지 않음"})

        report_result = _run_report_pipeline(
            project_name=str(payload.get("projectName", "JARVIS_AI_Report")),
            raw_data_path=str(raw_data_path),
            use_mock=bool(payload.get("useMock", False)),
        )
        timeline.append({"step": "report", "status": "done", "detail": "요약 보고서 생성 완료"})
        markdown_path = report_result.get("report_paths", {}).get("markdown")
        markdown_content = ""
        if markdown_path:
            markdown_content = Path(markdown_path).read_text(encoding=TEXT_ENCODING)

        self._send_json(
            200,
            {
                "success": True,
                "message": "단일 통합 파이프라인이 완료되었습니다.",
                "rawDataPath": str(raw_data_path),
                "crawl": crawl_result,
                "osControl": os_result,
                "feedbackLoop": feedback_result,
                "report": report_result,
                "timeline": timeline,
                "reportPaths": report_result.get("report_paths", {}),
                "reportContent": markdown_content,
            },
        )

    def _handle_workflow_run(self, payload: dict[str, Any]) -> None:
        timeline: list[dict[str, Any]] = []

        query = str(payload.get("query", "")).strip()
        if not query:
            raise HttpError(400, "workflow 실행에는 query가 필요합니다.")

        count = int(payload.get("count", 10))
        max_pages = int(payload.get("maxPages", 8))
        max_chars = int(payload.get("maxChars", 10000))

        folder_path = str(payload.get("folderPath", "")).strip()
        os_action = str(payload.get("osAction", "search"))
        search_query = str(payload.get("searchQuery", "")).strip()

        feedback_enabled = bool(payload.get("runFeedbackLoop", True))
        report_enabled = bool(payload.get("runReport", True))

        crawl_result = _run_crawler(query, count, max_pages, max_chars)
        timeline.append({"step": "crawl", "status": "done", "detail": "크롤링 완료"})

        os_result = None
        if folder_path:
            os_result = _run_os_controller(folder_path, os_action, search_query, payload)
            timeline.append({"step": "os_control", "status": "done", "detail": "OS 제어 완료"})
        else:
            timeline.append({"step": "os_control", "status": "skipped", "detail": "folderPath 미입력"})

        feedback_result = None
        if feedback_enabled:
            feedback_result = _run_feedback_loop(int(payload.get("feedbackTimeout", 180)))
            timeline.append({"step": "feedback", "status": "done", "detail": "피드백 루프 완료"})
        else:
            timeline.append({"step": "feedback", "status": "skipped", "detail": "요청에 의해 비활성화"})

        report_result = None
        if report_enabled:
            report_result = _run_report_pipeline(
                project_name=str(payload.get("projectName", "JARVIS_AI_Report")),
                raw_data_path=payload.get("rawDataPath"),
                use_mock=bool(payload.get("useMock", False)),
            )
            timeline.append({"step": "report", "status": "done", "detail": "보고서 생성 완료"})
        else:
            timeline.append({"step": "report", "status": "skipped", "detail": "요청에 의해 비활성화"})

        self._send_json(
            200,
            {
                "message": "통합 워크플로우가 완료되었습니다.",
                "timeline": timeline,
                "crawl": crawl_result,
                "osControl": os_result,
                "feedbackLoop": feedback_result,
                "report": report_result,
            },
        )

    def _serve_html(self, file_path: Path) -> None:
        self._serve_file(file_path, default_content_type="text/html; charset=utf-8")

    def _serve_file(self, file_path: Path, default_content_type: str | None = None) -> None:
        content = file_path.read_bytes()
        self.send_response(200)
        content_type = default_content_type or self._guess_content_type(file_path)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _guess_content_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".html":
            return "text/html; charset=utf-8"
        if suffix == ".css":
            return "text/css; charset=utf-8"
        if suffix == ".js":
            return "application/javascript; charset=utf-8"
        if suffix == ".json":
            return "application/json; charset=utf-8"
        return "application/octet-stream"

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), OsControllerHandler)
    print("서버 실행 중: http://127.0.0.1:8000")
    server.serve_forever()
