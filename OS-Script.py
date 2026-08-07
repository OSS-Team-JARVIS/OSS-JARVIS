import os
import re
import shlex
import subprocess
from typing import Optional


DEFAULT_TIMEOUT = 30

BLOCKED_PATTERNS = [
    # 파일 시스템 파괴
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\*",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
    r">\s*/dev/sd",
    r"chmod\s+-R\s+777\s+/",

    # 권한 상승 / 시스템 제어
    r"sudo\s+",
    r"shutdown",
    r"reboot",
    r"useradd",
    r"passwd",
    r"crontab\s+-[re]",

    r"curl[^|]*\|\s*(ba)?sh",
    r"wget[^|]*\|\s*(ba)?sh",

    r"nc\s+-e",
    r"bash\s+-i\s*>&",
    r"/dev/tcp/",

    # 민감 정보 접근
    r"cat\s+.*\.ssh/",
    r"cat\s+.*\.aws/credentials",
    r"cat\s+.*\.env",

    r"git\s+push\s+.*(-f|--force)",
    r"git\s+reset\s+--hard",

    r"history\s+-c",
    r">\s*~?/?\.bash_history",

    r":\(\)\{.*:\|:.*\};:",
]


def run_command(command: str, timeout: int = DEFAULT_TIMEOUT, cwd: Optional[str] = None) -> dict:
    command = command.strip()
    if not command:
        return {"success": False, "stdout": "", "stderr": "빈 명령어입니다.", "return_code": -1}

    blocked = _find_blocked_pattern(command)
    if blocked:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"차단된 명령어입니다: {blocked}",
            "return_code": -1,
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"{timeout}초 안에 종료되지 않아 강제 중단되었습니다.",
            "return_code": -1,
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": f"실행 중 오류: {e}", "return_code": -1}


def _find_blocked_pattern(command: str) -> Optional[str]:
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command):
            return pattern
    return None


class TerminalSession:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        if not os.path.isdir(self.root_dir):
            raise ValueError(f"루트 폴더가 존재하지 않습니다: {self.root_dir}")

        self.current_dir = self.root_dir
        self.history: list[str] = []

    def run(self, command: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
        command = command.strip()
        if not command:
            return self._result(False, "", "빈 명령어입니다.")

        blocked = _find_blocked_pattern(command)
        if blocked:
            return self._result(False, "", f"차단된 명령어입니다: {blocked}")

        if command == "cd" or command.startswith("cd "):
            return self._change_directory(command)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.current_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            self.history.append(command)
            return self._result(result.returncode == 0, result.stdout, result.stderr)

        except subprocess.TimeoutExpired:
            return self._result(False, "", f"{timeout}초 초과로 강제 종료되었습니다.")
        except Exception as e:
            return self._result(False, "", f"실행 중 오류: {e}")

    def _change_directory(self, command: str) -> dict:
        parts = shlex.split(command)
        target = parts[1] if len(parts) > 1 else self.root_dir

        new_dir = os.path.abspath(os.path.join(self.current_dir, target))

        if not self._is_inside_root(new_dir):
            return self._result(False, "", "허용된 작업 폴더를 벗어날 수 없습니다.")

        if not os.path.isdir(new_dir):
            return self._result(False, "", f"폴더가 존재하지 않습니다: {new_dir}")

        self.current_dir = new_dir
        self.history.append(command)
        return self._result(True, f"이동됨: {self.current_dir}", "")

    def _is_inside_root(self, path: str) -> bool:
        try:
            return os.path.commonpath([self.root_dir, path]) == self.root_dir
        except ValueError:
            return False

    def _result(self, success: bool, stdout: str, stderr: str) -> dict:
        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "current_dir": self.current_dir,
        }


if __name__ == "__main__":
    # 1단계: 단발성 실행 예시
    print(run_command("echo hello"))

    # 2단계: 세션 유지 실행 예시
    session = TerminalSession(root_dir=os.getcwd())
    print(session.run("cd .."))       # 루트 밖 이동 -> 차단
    print(session.run("echo world"))  # 현재 폴더에서 정상 실행
    print(session.run("rm -rf /"))    # 위험 명령어 -> 차단
    print("실행 기록:", session.history)