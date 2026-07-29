"""생성된 보고서의 구조적 적합성을 검증하는 모듈입니다.

AI가 출력한 최종 텍스트가 요구된 Markdown 규격을 엄격하게 준수하는지 확인하고,
형식이 맞지 않을 경우 재지정된 콜백을 실행하여 재발행을 시도합니다.
"""

import re
from typing import Callable, List


class ReportValidator:
    """최종 요약 보고서의 마크다운 서식 및 헤더를 검증하는 클래스입니다."""

    def __init__(self) -> None:
        """ReportValidator의 생성자입니다."""
        # 필수 요구 헤더 목록 (정규식 또는 문자열 검사용)
        self.required_headers: List[str] = [
            "## 1. 개요",
            "## 2. 핵심 내용",
            "## 3. 주요 기능 및 기술",
            "## 4. 개발 범위 및 실행 환경",
            "## 5. 성과 계획 및 기대 효과"
        ]

    def validate(self, text: str) -> bool:
        """문서 내에 필수 마크다운 헤더가 포함되어 있는지 검증합니다.

        로컬 LLM의 창작 변동성을 고려하여, 헤더의 번호와 핵심 키워드가 
        해당 헤더 라인에 유연하게 포함되어 있으면 검증 통과로 처리합니다.

        Args:
            text: 검증할 최종 AI 응답 텍스트

        Returns:
            필수 서식이 정상적으로 만족되면 True, 누락된 항목이 있으면 False
        """
        if not text:
            return False

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1. `# 제목` 검증
        has_title = any(line.startswith("#") and not line.startswith("##") for line in lines)

        # 2. 각 문항별 필수 헤더 존재 여부 유연 매칭
        # 예: '## 1. 개요 및 목적' 또는 '## 1. 개요' 모두 통과
        has_h1 = any(line.startswith("##") and "1" in line and "개요" in line for line in lines)
        has_h2 = any(line.startswith("##") and "2" in line and ("핵심" in line or "내용" in line) for line in lines)
        has_h3 = any(line.startswith("##") and "3" in line and ("기능" in line or "기술" in line) for line in lines)
        has_h4 = any(line.startswith("##") and "4" in line and ("범위" in line or "환경" in line) for line in lines)
        has_h5 = any(line.startswith("##") and "5" in line and ("성과" in line or "효과" in line or "기대" in line) for line in lines)

        # 모든 필수 요소 검증 충족 여부 반환
        return has_title and has_h1 and has_h2 and has_h3 and has_h4 and has_h5

    def validate_and_retry(
        self,
        initial_text: str,
        generate_callback: Callable[[], str],
        max_retries: int = 2
    ) -> str:
        """응답을 검증하고, 검증 실패 시 재시도 콜백을 통해 재생성을 요청합니다.

        Args:
            initial_text: 최초로 생성된 보고서 텍스트
            generate_callback: 검증 실패 시 다시 LLM을 호출하여 텍스트를 반환하는 콜백 함수
            max_retries: 최대 재시도 횟수 (기본 2회)

        Returns:
            최종적으로 검증에 성공했거나 최대 재시도를 초과한 결과 문자열
        """
        current_text = initial_text
        retries = 0

        while not self.validate(current_text) and retries < max_retries:
            retries += 1
            print(
                f"[Validator] 필수 헤더가 누락되어 검증에 실패했습니다. "
                f"재생성을 시도합니다 (시도 {retries}/{max_retries})."
            )
            current_text = generate_callback()

        if not self.validate(current_text):
            print(
                "[Validator] WARNING: 최대 재시도 후에도 "
                "필수 헤더 규격 검증에 실패했습니다. 원본을 유지합니다."
            )
        else:
            if retries > 0:
                print(f"[Validator] 재시도 끝에 보고서 검증에 성공했습니다.")
            else:
                print("[Validator] 보고서 구조 검증에 성공했습니다.")

        return current_text
