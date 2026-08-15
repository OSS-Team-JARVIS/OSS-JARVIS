"""텍스트 전처리를 위한 모듈입니다.

수집한 원본 데이터에서 불필요한 태그, 특수문자, URL 등을 제거하여
LLM이 원활하게 이해할 수 있는 텍스트 형태로 변환합니다.
"""

import re


class TextPreprocessor:
    """텍스트 데이터를 정제하고 전처리하는 클래스입니다."""

    def __init__(self) -> None:
        """TextPreprocessor의 생성자입니다."""
        pass

    def remove_html_tags(self, text: str) -> str:
        """텍스트에서 HTML 태그를 제거합니다.

        Args:
            text: HTML 태그를 포함한 원본 문자열

        Returns:
            HTML 태그가 제거된 문자열
        """
        html_pattern = re.compile(r"<[^>]*>")
        return html_pattern.sub("", text)

    def remove_urls(self, text: str) -> str:
        """텍스트에서 HTTP, HTTPS 및 WWW URL 링크를 제거합니다.

        Args:
            text: URL이 포함된 원본 문자열

        Returns:
            URL이 제거된 문자열
        """
        url_pattern = re.compile(r"https?://\S+|www\.\S+")
        return url_pattern.sub("", text)

    def clean_special_characters(self, text: str) -> str:
        """가독성을 해치는 불필요한 특수문자를 정리합니다.

        기본적인 문장부호(.,!?@#%&()-_=+)와 한글, 영문, 숫자는 보존합니다.

        Args:
            text: 원본 문자열

        Returns:
            특수문자가 정리된 문자열
        """
        # 불필요한 제어 문자나 비정상적인 특수 기호 제거
        clean_pattern = re.compile(r"[^\w\s.,!?'\"\-@#%&()\[\]\{\}]")
        return clean_pattern.sub("", text)

    def remove_duplicate_whitespaces(self, text: str) -> str:
        """중복된 공백과 연속된 줄바꿈을 단일 공백 및 단일 줄바꿈으로 축소합니다.

        Args:
            text: 원본 문자열

        Returns:
            중복 공백 및 연속 줄바꿈이 제거된 문자열
        """
        # 연속된 줄바꿈을 최대 단일 줄바꿈으로 변경
        text = re.sub(r"\n+", "\n", text)
        # 연속된 탭과 공백을 단일 공백으로 변경
        text = re.sub(r"[ \t]+", " ", text)
        return text

    def preprocess(self, text: str) -> str:
        """모든 전처리 단계를 순차적으로 실행합니다.

        Args:
            text: 원본 데이터 텍스트

        Returns:
            전처리가 완료된 정제 텍스트
        """
        if not text:
            return ""

        text = self.remove_html_tags(text)
        text = self.remove_urls(text)
        text = self.clean_special_characters(text)
        text = self.remove_duplicate_whitespaces(text)
        return text.strip()
