"""문서 청킹을 처리하는 모듈입니다.

긴 문서를 LLM의 컨텍스트 한계와 처리 효율성에 맞추어
오버랩(Overlap)을 포함한 적절한 크기의 청크(Chunk)로 분할합니다.
"""

from typing import List


class ChunkProcessor:
    """긴 텍스트를 설정된 크기와 오버랩에 맞추어 여러 청크로 분할하는 클래스입니다."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 200) -> None:
        """ChunkProcessor의 생성자입니다.

        Args:
            chunk_size: 단일 청크의 최대 글자 수
            overlap: 인접 청크 간 겹치는 글자 수
        """
        # 오류 방지를 위한 예외 처리 및 보정
        if chunk_size <= 0:
            raise ValueError("chunk_size는 0보다 커야 합니다.")
        if overlap < 0:
            raise ValueError("overlap은 0 이상이어야 합니다.")
        if overlap >= chunk_size:
            raise ValueError("overlap은 chunk_size보다 작아야 합니다.")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def split_text(self, text: str) -> List[str]:
        """텍스트를 설정된 크기와 오버랩에 맞추어 청크 리스트로 분할합니다.

        Args:
            text: 분할할 원본 문자열

        Returns:
            분할된 텍스트 청크들의 리스트
        """
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        step = self.chunk_size - self.overlap

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            # 만약 현재 위치가 전체 텍스트 끝에 도달했거나 더 이상 진행할 수 없으면 종료
            if end >= len(text):
                break
            start += step

        return chunks
