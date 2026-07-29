"""LLM 프롬프트를 생성하기 위한 모듈입니다.

사용자의 비즈니스 시나리오(요약, 보고서, 회의록, 연구 조사)에 맞춘
시스템 및 사용자 프롬프트 템플릿을 생성하고 바인딩합니다.
"""

from typing import Dict


class PromptBuilder:
    """Task 유형별 LLM 프롬프트를 구성하는 클래스입니다."""

    def __init__(self) -> None:
        """PromptBuilder의 생성자입니다."""
        pass

    def _get_summary_prompt(self, text: str) -> str:
        """단순 요약 Task를 위한 프롬프트를 생성합니다."""
        return (
            "당신은 정보 요약 전문가입니다. 아래 지시사항을 철저히 준수하세요.\n\n"
            "[지시사항]\n"
            "1. 주어진 [텍스트]의 핵심 내용을 명확하고 간결하게 요약하세요.\n"
            "2. 반드시 한국어로만 작성하세요.\n"
            "3. 마크다운(Markdown) 형식으로 작성하세요.\n"
            "4. 원문에 없는 내용은 절대 지어내거나 추정하여 작성하지 마세요.\n\n"
            f"[텍스트]\n{text}\n\n"
            "[결과]"
        )

    def _get_report_prompt(self, text: str) -> str:
        """종합 보고서 Task를 위한 프롬프트를 생성합니다.

        반드시 지정된 검증용 마크다운 헤더 구조를 지키도록 지시합니다.
        """
        return (
            "당신은 전문 백엔드 및 LLM 애플리케이션 분석 보고서 작성가입니다.\n"
            "아래 지시사항과 지정된 마크다운 목차 구조를 정확히 지켜 종합 보고서를 작성하세요.\n\n"
            "[지시사항]\n"
            "1. 주어진 [텍스트]를 심층 분석하여 완성도 높은 보고서를 작성하세요.\n"
            "2. 반드시 한국어로만 작성하세요.\n"
            "3. 원문에 없는 정보는 절대 생성하지 마세요.\n"
            "4. 반드시 결과는 다음의 마크다운 헤더 구조를 포함하여 구조화해야 합니다. 누락되면 안 됩니다.\n\n"
            "--- 구조 필수 형식 ---\n"
            "# [제목 작성]\n"
            "## 1. 개요\n"
            "## 2. 핵심 내용\n"
            "## 3. 주요 기능 및 기술\n"
            "## 4. 개발 범위 및 실행 환경\n"
            "## 5. 성과 계획 및 기대 효과\n"
            "-------------------------\n\n"
            f"[텍스트]\n{text}\n\n"
            "[보고서]"
        )

    def _get_meeting_prompt(self, text: str) -> str:
        """회의록 정리 Task를 위한 프롬프트를 생성합니다."""
        return (
            "당신은 회의록 정리 비서입니다. 아래 지시사항을 준수하세요.\n\n"
            "[지시사항]\n"
            "1. 주어진 회의록 [텍스트]에서 논의 주제, 결정 사항, 향후 행동 지침(Action Item)을 추출하세요.\n"
            "2. 반드시 한국어로만 작성하세요.\n"
            "3. 마크다운(Markdown) 형식으로 가독성 있게 정리하세요.\n"
            "4. 원문에 언급되지 않은 허구의 결정 사항이나 회의 인원을 생성하지 마세요.\n\n"
            f"[텍스트]\n{text}\n\n"
            "[회의록 정리]"
        )

    def _get_research_prompt(self, text: str) -> str:
        """연구 조사 Task를 위한 프롬프트를 생성합니다."""
        return (
            "당신은 IT 기술 및 시장 연구원입니다. 아래 지시사항을 준수하세요.\n\n"
            "[지시사항]\n"
            "1. 주어진 [텍스트]를 바탕으로 핵심 연구 이슈, 트렌드, 시사점을 도출하세요.\n"
            "2. 반드시 한국어로만 작성하세요.\n"
            "3. 마크다운(Markdown) 형식으로 체계화하여 기술하세요.\n"
            "4. 사실 관계는 반드시 원문에 제공된 데이터에만 기반해야 합니다.\n\n"
            f"[텍스트]\n{text}\n\n"
            "[연구 보고서]"
        )

    def build(self, task: str, text: str) -> str:
        """지정된 Task와 입력 텍스트를 조합하여 최종 프롬프트를 작성합니다.

        Args:
            task: summary, report, meeting, research 중 하나
            text: 프롬프트에 삽입될 데이터 텍스트

        Returns:
            완성된 프롬프트 문자열
        """
        task_handlers = {
            "summary": self._get_summary_prompt,
            "report": self._get_report_prompt,
            "meeting": self._get_meeting_prompt,
            "research": self._get_research_prompt,
        }

        handler = task_handlers.get(task.lower())
        if not handler:
            raise ValueError(
                f"지원하지 않는 Task 유형입니다: {task}. "
                "summary, report, meeting, research 중 하나를 선택하세요."
            )

        return handler(text)
