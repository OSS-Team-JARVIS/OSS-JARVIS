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

        Args:
            text: 검증할 최종 AI 응답 텍스트

        Returns:
            필수 서식이 정상적으로 만족되면 True, 누락된 항목이 있으면 False
        """
        if not text:
            return False

        # 제목 헤더(# 제목)가 단독 줄로 적어도 하나 존재하고 있는지 검증
        # 공백 문자(\s+) 고려하여 정규식 검사
        has_title = False
        for line in text.split("\n"):
            stripped = line.strip()
            # '#'으로 시작하고 바로 뒤가 '##'가 아닌 마크다운 제목(# ) 매칭
            if stripped.startswith("#") and not stripped.startswith("##"):
                has_title = True
                break

        # 필수 헤더들의 포함 여부 확인
        # 줄바꿈 및 다중 스페이스 변동을 최소화하기 위해 공백을 정규화한 후 포함 검사
        normalized_text = re.sub(r"\s+", " ", text)
        has_headers = all(
            re.sub(r"\s+", " ", req) in normalized_text
            for req in self.required_headers
        )

        return has_title and has_headers

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
