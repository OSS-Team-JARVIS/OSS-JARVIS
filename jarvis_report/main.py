"""AI 요약 보고서 생성 모듈의 메인 실행 모듈입니다.

원본 데이터를 읽고 전처리한 뒤, Map-Reduce 방식으로 문서를 요약합니다.
이후 마크다운 구조 검증을 통과한 최종 결과물을 다양한 형식으로 저장하고 기록합니다.
"""

from datetime import datetime
import os
import sys
from typing import List, Optional

# 모듈 경로 문제 방지를 위해 상위 디렉토리 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_report import config
from jarvis_report.chunk_processor import ChunkProcessor
from jarvis_report.logger import log_execution, logger
from jarvis_report.preprocess import TextPreprocessor
from jarvis_report.prompt_builder import PromptBuilder
from jarvis_report.providers import BaseProvider, OllamaProvider, MockProvider, OllamaProviderError
from jarvis_report.report_writer import ReportWriter
from jarvis_report.validator import ReportValidator


def load_raw_data(filepath: str) -> str:
    """텍스트 파일로부터 원본 데이터를 로드합니다.

    Args:
        filepath: 로드할 파일의 경로

    Returns:
        파일의 문자열 내용
    """
    print("원본 데이터 읽는 중...")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"원본 데이터 파일이 없습니다: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def map_summarize_chunks(
    chunks: List[str],
    provider: BaseProvider,
    prompt_builder: PromptBuilder
) -> str:
    """각 청크를 개별 요약하여 하나의 텍스트로 합칩니다 (Map 단계).

    Args:
        chunks: 분할된 텍스트 청크 리스트
        provider: 요약을 수행할 LLM 프로바이더
        prompt_builder: 프롬프트 생성 빌더

    Returns:
        개별 요약들을 합친 문자열
    """
    print(f"LLM 요약 중... (총 {len(chunks)}개 청크)")
    summarized_chunks: List[str] = []

    for idx, chunk in enumerate(chunks, 1):
        print(f" - 청크 요약 진행 중 ({idx}/{len(chunks)})...")
        prompt = prompt_builder.build("summary", chunk)
        summary = provider.summarize(prompt)
        summarized_chunks.append(summary)

    return "\n\n".join(summarized_chunks)


def generate_final_report(
    merged_text: str,
    provider: BaseProvider,
    prompt_builder: PromptBuilder,
    validator: ReportValidator
) -> str:
    """종합 요약문을 검증이 포함된 최종 보고서 형식으로 작성합니다 (Reduce 단계).

    Args:
        merged_text: 개별 요약이 합쳐진 중간 결과물
        provider: 요약을 수행할 LLM 프로바이더
        prompt_builder: 프롬프트 생성 빌더
        validator: 마크다운 헤더 구조 검증기

    Returns:
        최종 검증 완료된 보고서 문자열
    """
    print("최종 보고서 생성 중...")

    # 콜백 함수 정의: 검증 실패 시 재호출할 생성 함수
    def build_report_callback() -> str:
        prompt = prompt_builder.build("report", merged_text)
        return provider.summarize(prompt)

    # 최초 보고서 생성
    initial_report = build_report_callback()

    # 구조적 무결성 검증 및 실패 시 콜백 재생성 실행
    final_report = validator.validate_and_retry(
        initial_report,
        build_report_callback,
        max_retries=config.MAX_RETRIES
    )

    return final_report


def run_pipeline(project_name: str, raw_data_path: str, use_mock: bool = False) -> None:
    """전체 AI 보고서 생성 파이프라인을 구동합니다.

    Args:
        project_name: 파일명 및 로그 식별에 사용될 프로젝트 이름
        raw_data_path: 분석 대상 원본 텍스트 파일 경로
        use_mock: Ollama 대신 가상 Mock LLM을 사용하여 시뮬레이션할지 여부
    """
    start_time = datetime.now()
    error_msg: Optional[str] = None
    model_label = "Mock-LLM-Qwen" if use_mock else config.MODEL

    try:
        # 객체 초기화
        preprocessor = TextPreprocessor()
        chunk_processor = ChunkProcessor(config.CHUNK_SIZE, config.OVERLAP)
        prompt_builder = PromptBuilder()

        # 프로바이더 선택 분기
        if use_mock:
            print("[System] Ollama 서버를 사용하지 않고 모의(Mock) LLM 모드로 실행합니다.")
            provider: BaseProvider = MockProvider()
        else:
            provider = OllamaProvider(
                model=config.MODEL,
                temperature=config.TEMPERATURE,
                max_context=config.MAX_CONTEXT
            )

        validator = ReportValidator()
        writer = ReportWriter(config.REPORT_DIR)

        # 1~4 단계 실행
        raw_text = load_raw_data(raw_data_path)
        print("전처리 중...")
        clean_text = preprocessor.preprocess(raw_text)

        print("Chunk 생성 중...")
        chunks = chunk_processor.split_text(clean_text)

        # Map-Reduce 요약
        merged_summaries = map_summarize_chunks(chunks, provider, prompt_builder)
        final_report = generate_final_report(
            merged_summaries, provider, prompt_builder, validator
        )

        # 5단계 저장
        writer.write_reports(project_name, final_report)
        print("저장 완료")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"파이프라인 실행 중 오류 발생: {e}")
        raise e
    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        log_execution(start_time, end_time, model_label, duration, error_msg)


def main() -> None:
    """메인 엔트리포인트 함수입니다."""
    project_name = "JARVIS_AI_Report"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_data_path = os.path.join(base_dir, "raw_data.txt")

    # raw_data.txt가 없으면 테스트용 샘플 텍스트 자동 생성
    if not os.path.exists(raw_data_path):
        with open(raw_data_path, "w", encoding="utf-8") as f:
            f.write("이것은 AI 요약 보고서 테스트를 위한 샘플 텍스트입니다. "
                    "기본 텍스트를 구성하고 모듈 작동을 확인합니다.")

    # --mock 명령 인자 감지
    use_mock = "--mock" in sys.argv

    try:
        run_pipeline(project_name, raw_data_path, use_mock=use_mock)
    except Exception as e:
        print(f"\n[오류] 프로그램 실행이 실패했습니다. 세부 정보: {e}")
        sys.exit(1)



if __name__ == "__main__":
    main()
