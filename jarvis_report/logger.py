"""애플리케이션 로그 기록을 위한 모듈입니다.

실행 시간, 모델명, 처리 시간, 예외 상황 등 주요 실행 지표들을
설정된 로그 디렉토리 아래의 텍스트 파일에 포맷팅하여 기록합니다.
"""

from datetime import datetime
import logging
import os
from typing import Optional
from jarvis_report.config import LOG_DIR

# 로그 디렉토리 생성
os.makedirs(LOG_DIR, exist_ok=True)

# 기본 로깅 설정
LOG_FILE_PATH = os.path.join(LOG_DIR, "jarvis_report.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("jarvis_report")


def log_execution(
    start_time: datetime,
    end_time: datetime,
    model_name: str,
    duration: float,
    error: Optional[str] = None
) -> None:
    """모듈 실행 완료 시 수행 관련 통계 정보를 로그 파일에 기록합니다.

    Args:
        start_time: 모듈 실행이 시작된 datetime
        end_time: 모듈 실행이 완료된 datetime
        model_name: 요약에 사용된 LLM 모델 이름
        duration: 총 소요 시간 (초 단위)
        error: 발생한 에러의 내용 문자열 (에러가 없을 경우 None)
    """
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

    log_msg = (
        f"실행 분석 통계 | "
        f"시작 시간: {start_str} | "
        f"종료 시간: {end_str} | "
        f"모델명: {model_name} | "
        f"처리 시간: {duration:.2f}초"
    )

    if error:
        logger.error(f"{log_msg} | 오류 내용: {error}")
    else:
        logger.info(f"{log_msg} | 상태: 정상 완료")
