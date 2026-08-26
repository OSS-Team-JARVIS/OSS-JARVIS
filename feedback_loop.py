"""입력 코드와 오류 로그를 분석하는 AI 피드백 루프입니다.

모듈 import 시 작업을 실행하지 않으며, ``run_feedback``를 호출한 경우에만
전달받은 코드/텍스트를 분석합니다. 파일 수정은 ``apply_fix=True``일 때만
명시적으로 수행합니다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import ollama
except ImportError:  # pragma: no cover - 환경별 선택 의존성
    ollama = None


DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_MAX_ATTEMPTS = 3


def build_feedback_prompt(error_log: str, code_text: str) -> str:
    """오류 로그와 작업 코드를 AI 피드백 입력 형식으로 결합합니다."""
    return f"""너는 Python 코드 오류 수정 전문가다.

현재 Python 코드:
{code_text}

발생한 오류 또는 실행 결과:
{error_log}

수정된 전체 Python 코드만 출력하고, 마크다운 코드 블록은 사용하지 마라.
"""


def analyze_error_log(
    error_log: str,
    code_text: str = "",
    *,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """오류와 코드를 분석해 수정안 또는 분석 오류를 반환합니다."""
    if ollama is None:
        return {"success": False, "error": "ollama 패키지가 설치되어 있지 않습니다."}

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": build_feedback_prompt(error_log, code_text)}],
        )
        fixed_code = str(response["message"]["content"])
        fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()
        return {"success": True, "fixed_code": fixed_code, "model": model}
    except Exception as exc:
        return {"success": False, "error": str(exc), "model": model}


def run_feedback(
    *,
    code_text: str = "",
    error_log: str = "",
    code_path: str | None = None,
    model: str = DEFAULT_MODEL,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    apply_fix: bool = False,
    execute: bool = False,
) -> dict[str, Any]:
    """전달받은 코드/텍스트에 대해 피드백을 수행합니다.

    ``code_path``가 지정되면 코드를 읽을 수 있으며, ``apply_fix``가 참일
    때만 마지막 수정안을 해당 파일에 기록합니다. 실행은 ``execute=True``일
    때만 수행됩니다.
    """
    target_path = Path(code_path).expanduser() if code_path else None
    if target_path is not None:
        if not target_path.exists() or not target_path.is_file():
            return {"success": False, "error": f"코드 파일을 찾을 수 없습니다: {target_path}"}
        code_text = target_path.read_text(encoding="utf-8")

    if not code_text.strip() and not error_log.strip():
        return {"success": False, "error": "code_text 또는 error_log를 입력하세요."}

    attempts = max(1, min(int(max_attempts), 10))
    current_code = code_text
    current_error = error_log
    feedback_attempts: list[dict[str, Any]] = []

    for attempt in range(1, attempts + 1):
        if execute and current_code.strip():
            execution = _execute_code(current_code, target_path.parent if target_path else None)
            current_error = execution["stderr"]
            if execution["success"]:
                return {
                    "success": True,
                    "attempts": attempt,
                    "code": current_code,
                    "execution": execution,
                    "feedback": feedback_attempts,
                }

        analysis = analyze_error_log(current_error, current_code, model=model)
        feedback_attempts.append({"attempt": attempt, "analysis": analysis})
        if not analysis.get("success"):
            return {
                "success": False,
                "attempts": attempt,
                "error": analysis.get("error", "피드백 분석에 실패했습니다."),
                "feedback": feedback_attempts,
            }

        current_code = str(analysis.get("fixed_code", current_code))
        if not execute:
            break

    if apply_fix and target_path is not None:
        target_path.write_text(current_code, encoding="utf-8")

    return {
        "success": True,
        "attempts": len(feedback_attempts),
        "fixed_code": current_code,
        "applied": bool(apply_fix and target_path is not None),
        "feedback": feedback_attempts,
    }


def _execute_code(code_text: str, cwd: Path | None) -> dict[str, Any]:
    """코드 문자열을 별도 프로세스에서 실행합니다."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="jarvis_feedback_") as temp_dir:
        temp_path = Path(temp_dir) / "feedback_target.py"
        temp_path.write_text(code_text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(temp_path)],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=30,
        )
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "return_code": result.returncode,
    }


if __name__ == "__main__":
    print(run_feedback(code_path="buggy.py", execute=True, apply_fix=True))
