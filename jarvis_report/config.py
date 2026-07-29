"""AI 요약 보고서 생성 모듈의 설정을 관리하는 모듈입니다.

이 모듈은 LLM 모델명, 하이퍼파라미터, 파일 저장 경로 등
시스템 전반에 걸쳐 사용되는 설정값들을 상수로 정의합니다.
"""

import os
from typing import Final

# LLM 설정
MODEL: Final[str] = "qwen2.5:3b"
TEMPERATURE: Final[float] = 0.2
MAX_CONTEXT: Final[int] = 4096

# 문서 분할(청킹) 설정
CHUNK_SIZE: Final[int] = 1000
OVERLAP: Final[int] = 200

# 검증 및 재시도 설정
MAX_RETRIES: Final[int] = 2

# 디렉토리 경로 설정
BASE_DIR: Final[str] = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR: Final[str] = os.path.join(BASE_DIR, "reports")
LOG_DIR: Final[str] = os.path.join(BASE_DIR, "logs")
