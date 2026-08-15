"""LLM 서비스 프로바이더를 추상화하고 구현하는 모듈입니다.

다양한 LLM API(Ollama, Claude, Gemini 등)로의 쉬운 교체를 위해
인터페이스 역할을 하는 BaseProvider 추상 클래스를 정의하고,
로컬 Ollama 연동을 위한 OllamaProvider를 구현합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import httpx
import ollama


# ==========================================
# 커스텀 예외 정의
# ==========================================

class OllamaProviderError(Exception):
    """Ollama 프로바이더 처리 과정에서 발생하는 기본 예외 클래스입니다."""
    pass


class OllamaConnectionError(OllamaProviderError):
    """Ollama 서버 연결에 실패했을 때 발생하는 예외입니다."""
    pass


class ModelNotFoundError(OllamaProviderError):
    """Ollama 서버에 요청한 모델이 존재하지 않을 때 발생하는 예외입니다."""
    pass


class OllamaTimeoutError(OllamaProviderError):
    """Ollama 서버의 요청 응답 대기 시간이 초과되었을 때 발생하는 예외입니다."""
    pass


# ==========================================
# 프로바이더 추상 클래스 및 구현 클래스
# ==========================================

class BaseProvider(ABC):
    """LLM 프로바이더들의 기반이 되는 추상 클래스입니다."""

    @abstractmethod
    def summarize(self, prompt: str) -> str:
        """주어진 프롬프트를 사용하여 텍스트 요약을 생성합니다.

        Args:
            prompt: LLM에 전달할 프롬프트 문자열

        Returns:
            LLM이 생성한 한국어 요약 결과물
        """
        pass


class OllamaProvider(BaseProvider):
    """로컬 Ollama 서비스를 사용하여 LLM 요청을 처리하는 프로바이더 클래스입니다."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        temperature: float = 0.2,
        max_context: int = 4096,
        timeout_seconds: float = 300.0
    ) -> None:
        """OllamaProvider의 생성자입니다.

        Args:
            model: Ollama 모델 이름
            temperature: 텍스트 생성의 다양성 조절 값
            max_context: 최대 컨텍스트 윈도우 크기(num_ctx)
            timeout_seconds: API 호출 타임아웃 제한 시간(초)
        """
        self.model = model
        self.temperature = temperature
        self.max_context = max_context
        self.timeout_seconds = timeout_seconds
        # ollama.Client 객체 생성 시 timeout 매개변수를 직접 httpx.Timeout 객체 혹은 float로 설정합니다.
        self.client = ollama.Client(timeout=timeout_seconds)

    def summarize(self, prompt: str) -> str:
        """Ollama API를 호출하여 요약을 수행합니다.

        Args:
            prompt: LLM에 보낼 프롬프트 문자열

        Returns:
            생성된 요약 텍스트

        Raises:
            OllamaConnectionError: 서버 포트 미개방 등 연결 에러
            ModelNotFoundError: 로컬에 모델 다운로드 안 됨
            OllamaTimeoutError: 타임아웃 초과
            OllamaProviderError: 기타 API 오류
        """
        options: Dict[str, Any] = {
            "temperature": self.temperature,
            "num_ctx": self.max_context
        }

        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                options=options
            )
            return str(response.get("response", ""))
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaConnectionError(
                f"Ollama 서버에 연결할 수 없습니다. "
                f"서버 활성화 여부나 주소를 확인하세요. 에러: {e}"
            )
        except (httpx.TimeoutException, httpx.ReadTimeout) as e:
            raise OllamaTimeoutError(
                f"Ollama 서버 요청 시간이 초과되었습니다 ({self.timeout_seconds}초). "
                f"에러: {e}"
            )
        except ollama.ResponseError as e:
            # 404 status code는 통상 모델이 존재하지 않을 때 나타납니다.
            if e.status_code == 404:
                raise ModelNotFoundError(
                    f"요청한 Ollama 모델 '{self.model}'을 찾을 수 없습니다. "
                    f"'ollama pull {self.model}'로 모델을 다운로드하세요. 에러: {e}"
                )
            raise OllamaProviderError(f"Ollama API 응답 중 오류가 발생했습니다: {e}")
        except Exception as e:
            raise OllamaProviderError(f"예기치 못한 Ollama 연동 오류가 발생했습니다: {e}")


class MockProvider(BaseProvider):
    """Ollama 서버 없이 전체 모듈 동작 및 검증 재시도를 확인하기 위한 테스트용 모의 프로바이더입니다."""

    def __init__(self) -> None:
        """MockProvider의 생성자입니다."""
        self._call_count = 0

    def summarize(self, prompt: str) -> str:
        """호출 횟수 및 프롬프트 내용에 따라 모의 응답을 반환합니다.

        최종 보고서 요청 시 1회차에는 헤더를 누락시키고 2회차에 성공 서식을 돌려주어
        Validator의 검증 실패 후 재생성 콜백 흐름이 도는 것을 눈으로 시뮬레이션할 수 있게 합니다.

        Args:
            prompt: 입력 프롬프트

        Returns:
            사전 정의된 마크다운 텍스트
        """
        self._call_count += 1

        # 청크 요약 (Map) 단계 모의 동작
        if "요약 전문가" in prompt:
            return f"[청크 요약 {self._call_count}] 본 청킹 세그먼트의 요약 텍스트 내용입니다."

        # 최종 요약 보고서 (Reduce) 단계 모의 동작
        if "종합 보고서" in prompt:
            # 최초 요약 보고서 응답 (2, 3번 헤더 누락 시나리오)
            if self._call_count <= 3:
                print("\n[MockProvider] 1차 종합 보고서를 생성합니다. (의도적으로 서식 누락)")
                return (
                    "# Mock JARVIS AI 종합 분석 보고서\n\n"
                    "## 1. 개요\n"
                    "이 보고서는 로컬에 Ollama가 실행 중이지 않을 때 모듈 동작을 테스트하기 위한 용도입니다.\n\n"
                    "## 4. 개발 범위 및 실행 환경\n"
                    "Windows 11, python 3.11, uv 가상환경\n\n"
                    "## 5. 성과 계획 및 기대 효과\n"
                    "보고서 생성 자동화를 통한 리소스 절감 효과를 기대합니다.\n"
                )
            # 재시도 콜백으로 재생성되었을 때의 정상 서식 응답
            else:
                print("\n[MockProvider] 재시도 요청을 수신하여 2차 종합 보고서를 생성합니다. (정상 서식)")
                return (
                    "# Mock JARVIS AI 종합 분석 보고서\n\n"
                    "## 1. 개요\n"
                    "이 보고서는 로컬에 Ollama가 실행 중이지 않을 때 모듈 동작을 테스트하기 위한 용도입니다.\n\n"
                    "## 2. 핵심 내용\n"
                    "Ollama 서버 설치 및 실행 없이도 전체 텍스트 전처리, 청킹, 검증 흐름을 입증하였습니다.\n\n"
                    "## 3. 주요 기능 및 기술\n"
                    "- 텍스트 태그 및 URL 자동 정제\n"
                    "- Map-Reduce 기반 청크 슬라이싱 요약\n"
                    "- 검증 실패 시 자동 재생성 콜백\n\n"
                    "## 4. 개발 범위 및 실행 환경\n"
                    "Windows 11, python 3.11, uv 가상환경\n\n"
                    "## 5. 성과 계획 및 기대 효과\n"
                    "보고서 생성 자동화를 통한 리소스 절감 효과를 기대합니다.\n"
                )

        return "# 제목\n## 1. 개요\n## 2. 핵심 내용\n## 3. 주요 기능 및 기술\n## 4. 개발 범위 및 실행 환경\n## 5. 성과 계획 및 기대 효과"

