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
        timeout_seconds: float = 60.0
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
