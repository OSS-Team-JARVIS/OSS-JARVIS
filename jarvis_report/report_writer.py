"""최종 보고서를 파일로 작성하는 모듈입니다.

생성된 요약 보고서를 Markdown 형식으로 저장하고,
Pandoc 프로그램을 사용하여 PDF 및 DOCX 파일로 변환하여 저장합니다.
"""

from datetime import datetime
import os
import subprocess
from typing import Optional


class ReportWriter:
    """Markdown, PDF, DOCX 형식의 보고서를 파일로 생성 및 저장하는 클래스입니다."""

    def __init__(self, report_dir: str = "reports") -> None:
        """ReportWriter의 생성자입니다.

        설정된 보고서 디렉토리가 없으면 자동으로 생성합니다.

        Args:
            report_dir: 보고서가 저장될 경로 디렉토리
        """
        self.report_dir = report_dir
        os.makedirs(self.report_dir, exist_ok=True)

    def is_pandoc_available(self) -> bool:
        """시스템에 Pandoc이 설치되어 실행 가능한지 확인합니다.

        Returns:
            Pandoc이 설치되어 사용 가능하면 True, 그렇지 않으면 False
        """
        try:
            subprocess.run(
                ["pandoc", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def write_markdown(self, filepath: str, content: str) -> None:
        """문자열 컨텐츠를 마크다운 파일로 저장합니다.

        Args:
            filepath: 마크다운 파일 전체 경로
            content: 저장할 마크다운 문자열
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def convert_with_pandoc(self, input_path: str, output_path: str) -> bool:
        """Pandoc을 활용하여 파일 형식을 변환합니다.

        Args:
            input_path: 입력 마크다운 파일 경로
            output_path: 변환될 파일의 출력 경로

        Returns:
            변환 성공 시 True, 실패 시 False
        """
        try:
            subprocess.run(
                ["pandoc", input_path, "-o", output_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            # PDF의 경우, xelatex, weasyprint 등의 PDF 엔진이 없으면 에러가 납니다.
            err_msg = e.stderr.decode("utf-8", errors="ignore")
            print(f"[ReportWriter] Pandoc 변환 중 에러 발생: {err_msg.strip()}")
            return False
        except Exception as e:
            print(f"[ReportWriter] 파일 변환 에러: {e}")
            return False

    def write_reports(self, project_name: str, content: str) -> dict[str, str]:
        """보고서 파일들을 일괄 저장합니다 (MD, PDF, DOCX).

        Pandoc이 설치되어 있지 않거나 변환 엔진이 없으면 PDF/DOCX 변환은 건너뜁니다.

        Args:
            project_name: 파일명 접두어로 사용될 프로젝트명
            content: 보고서 내용 문자열
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_base = f"{project_name}_{timestamp}"

        md_path = os.path.join(self.report_dir, f"{filename_base}.md")
        pdf_path = os.path.join(self.report_dir, f"{filename_base}.pdf")
        docx_path = os.path.join(self.report_dir, f"{filename_base}.docx")

        # 1. 마크다운 저장 (기본)
        self.write_markdown(md_path, content)
        print(f"[ReportWriter] Markdown 보고서 저장 성공: {md_path}")

        # 2. Pandoc 가용성 검증 후 PDF/DOCX 저장 시도
        if not self.is_pandoc_available():
            print(
                "[ReportWriter] 시스템에 Pandoc이 설치되어 있지 않아 "
                "PDF/DOCX 보고서 변환은 건너뛰고 Markdown만 저장합니다."
            )
            return {"markdown": md_path}

        # 3. DOCX 변환
        if self.convert_with_pandoc(md_path, docx_path):
            print(f"[ReportWriter] DOCX 보고서 저장 성공: {docx_path}")

        # 4. PDF 변환
        if self.convert_with_pandoc(md_path, pdf_path):
            print(f"[ReportWriter] PDF 보고서 저장 성공: {pdf_path}")
        else:
            print(
                "[ReportWriter] PDF 엔진(pdflatex, weasyprint 등)이 누락되었거나 "
                "설정 오류로 인해 PDF 파일 변환은 실패하였습니다."
            )

        paths = {"markdown": md_path}
        if os.path.exists(docx_path):
            paths["docx"] = docx_path
        if os.path.exists(pdf_path):
            paths["pdf"] = pdf_path
        return paths
