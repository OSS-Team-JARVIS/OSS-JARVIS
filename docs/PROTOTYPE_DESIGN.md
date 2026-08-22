# 🏗️ 웹 서칭·크롤링 엔진 프로토타입 설계서

> **작성**: 심규민 | **상태**: 설계 확정 전 (팀 리뷰 대기)
> **선행 문서**: [TEAM_RESEARCH_REPORT.md](./TEAM_RESEARCH_REPORT.md)
> **언어/런타임**: Python 3.11+ / 비동기(asyncio) 기반

---

## 1. 설계 목표와 제약

| 목표 | 측정 기준 |
|---|---|
| 키워드 → 정제된 본문 JSON 반환 | 에러율 < 5% (정상 사이트 기준) |
| 안전한 크롤링 | robots.txt 준수, 도메인당 순차 요청, 사용자 IP 차단 0건 |
| MCP 도구화 | `web_search` / `crawl` 두 도구로 상위 에이전트가 호출 |
| 폴백 체인 | 검색 프로바이더 1개 실패해도 결과 반환 |

**제약**: 데스크톱 앱(사용자 집 IP), 과제 기간 내 완성 → 과도한 안티봇 공세(구글 직접 스크래핑 등)는 배제.

---

## 2. 디렉터리 구조

```
OSS/
├── docs/
│   ├── TEAM_RESEARCH_REPORT.md      # 팀 공유 리서치 보고서
│   └── PROTOTYPE_DESIGN.md          # 본 문서
├── src/
│   └── jarvis_crawler/
│       ├── __init__.py
│       ├── types.py                 # ★ 데이터 계약 (모든 모듈이 공유)
│       ├── config.py                # API 키/딜레이/상한 설정 로딩
│       ├── search/
│       │   ├── __init__.py
│       │   ├── base.py              # SearchProvider 추상 클래스
│       │   ├── naver.py             # 네이버 Open API (메인)
│       │   ├── serper.py            # Serper.dev (글로벌 메인)
│       │   └── ddgs_provider.py     # DDGS (폴백)
│       ├── crawl/
│       │   ├── __init__.py
│       │   ├── robots.py            # robots.txt 파싱/판정
│       │   ├── fetcher.py           # curl_cffi HTTP 페처 + politeness
│       │   └── extractor.py         # trafilatura 본문 추출 (+newspaper4k 폴백)
│       ├── pipeline.py              # 오케스트레이터: search→dedup→fetch→extract
│       ├── cli.py                   # 개발/데모용 CLI 진입점
│       └── mcp_server.py            # MCP 서버 노출 (web_search/crawl 도구)
├── tests/
│   ├── test_extractor.py            # 로컬 HTML fixture 기반 (네트워크 불필요)
│   ├── test_pipeline.py
│   └── fixtures/                    # 테스트용 저장된 HTML 샘플
├── pyproject.toml
└── README.md
```

---

## 3. 데이터 계약 (`types.py`) — 김민석 파트와 공유하는 핵심

```python
@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str          # 검색엔진이 주는 요약문
    rank: int             # 검색 결과 내 순위 (1-based)
    provider: str         # "naver" | "serper" | "ddgs"

@dataclass(frozen=True)
class CrawledPage:
    url: str
    final_url: str        # 리다이렉트 최종 URL
    status: int           # HTTP 상태 코드 (200)
    title: str
    content: str          # ★ 본문 텍스트 (trafilatura 출력, UTF-8)
    content_length: int
    fetched_at: str       # ISO 8601
    extractor: str        # "trafilatura" | "newspaper4k"
    error: str | None     # 성공 시 None

# 파이프라인 최종 산출물 — 김민석 파트에 이 JSON을 전달
@dataclass(frozen=True)
class ResearchBundle:
    query: str
    results: list[CrawledPage]
    failed_urls: list[FailedFetch]   # 실패 건은 버리지 않고 기록
```

> **설계 원칙**: frozen dataclass = 생성 후 불변. 모듈 간 데이터 흐름을 타입으로 강제.

---

## 4. 모듈 인터페이스 명세

### 4.1 검색 계층 — `SearchProvider` 추상 클래스

```python
class SearchProvider(ABC):
    name: str                      # "naver" | "serper" | "ddgs"

    @abstractmethod
    async def search(self, query: str, count: int = 10) -> list[SearchResult]:
        """키워드로 검색해 URL 목록 반환. 실패 시 SearchProviderError 발생."""

class SearchChain:                 # 폴백 오케스트레이터
    def __init__(self, providers: list[SearchProvider]): ...
    async def search(self, query: str, count: int) -> list[SearchResult]:
        # providers 순서대로 시도 → 첫 성공에서 반환, 전부 실패 시 집계 에러
```

- **NaverProvider**: X-Naver-Client-Id/Secret 헤더. `display=100`, 초당 호출 제한 준수
- **SerperProvider**: `https://google.serper.dev/search` POST, JSON 응답의 organic 파싱
- **DDGSProvider**: 동기 라이브러리 → `asyncio.to_thread` 래핑, Ratelimit 예외 시 백오프

### 4.2 크롤링 계층

```python
class RobotsGate:
    async def allowed(self, url: str) -> bool:
        """robots.txt + meta robots 판정. 도메인별 규칙 캐시."""

class Fetcher:
    """curl_cffi AsyncSession (impersonate='chrome') 래퍼"""
    async def fetch(self, url: str) -> FetchResult:
        # - 도메인별 큐: 같은 도메인엔 동시 요청 1개 + 랜덤 딜레이(1~3초)
        # - 429/503 → Retry-After 존중, tenacity 지수백오프+지터 (최대 3회)
        # - charset-normalizer로 EUC-KR 등 인코딩 정규화

def extract(html: str, url: str) -> ExtractedContent:
    # 1차: trafilatura.extract(output_format="markdown", favor_recall=True)
    # 2차: 빈 결과면 newspaper4k 폴백
    # max_chars 컷 (기본 10,000자 — 김민석과 합의 필요)
```

### 4.3 파이프라인 — 외부에 노출되는 단 하나의 진입점

```python
class ResearchPipeline:
    def __init__(self, chain: SearchChain, fetcher: Fetcher,
                 robots: RobotsGate, max_pages: int = 8): ...

    async def run(self, query: str, count: int = 10) -> ResearchBundle:
        """
        1. chain.search(query) → URL 후보
        2. 중복 제거 (URL 정규화: fragment 제거, 트레일링 슬래시 통일)
        3. 상위 max_pages개에 대해: robots 확인 → fetch → extract
        4. 성공/실패 분류해서 ResearchBundle 반환
        """

async def research(query: str) -> dict:   # 편의 함수 (JSON 직렬화 포함)
```

### 4.4 MCP 노출 — `mcp_server.py`

```python
# FastMCP 기반, 두 개의 도구만 노출:
@mcp.tool()
async def web_search(query: str, engine: str | None = None,
                     count: int = 10) -> str: ...
    # engine=None → 폴백 체인 자동 / "naver"|"serper"|"ddgs" 지정 가능

@mcp.tool()
async def crawl(urls: list[str], max_chars: int = 10000) -> str: ...
    # URL 리스트 직접 크롤링 (검색 없이 특정 페이지 열람)
```

---

## 5. 의존성 (`pyproject.toml`)

```toml
dependencies = [
    "curl_cffi>=0.15",        # TLS impersonation HTTP 클라이언트
    "trafilatura>=2.0",       # 본문 추출 메인
    "newspaper4k>=0.9",       # 본문 추출 폴백
    "lxml-html-clean",        # newspaper4k 의존
    "ddgs>=9",                # 무료 폴백 검색
    "httpx2[http2,brotli,zstd]>=0.5",  # 네이버/Serper JSON API 호출 (페이지 페치는 curl_cffi)
    "tenacity>=9",            # 재시도 백오프
    "protego>=0.4",           # robots.txt 파싱
    "charset-normalizer>=3",  # 인코딩 감지
    "mcp>=1.0",               # MCP 서버 프레임워크 (FastMCP)
    "pydantic>=2",            # 설정 관리
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "ruff", "basedpyright"]
```

---

## 6. 에러 처리 전략

| 상황 | 동작 |
|---|---|
| 검색 프로바이더 전체 실패 | `SearchChainError` + 프로바이더별 사유 반환 |
| robots.txt 차단 | 해당 URL skip, `failed_urls`에 사유="robots_disallowed" 기록 |
| HTTP 403/차단 의심 | 1회 재시도 후 포기, failed_urls에 기록 |
| 본문 추출 실패 (빈 문자열) | newspaper4k 폴백 → 그래도 실패 시 content="" 로 반환하되 error 필드 표기 |
| 타임아웃 | 페치당 20초 |

**원칙: 부분 실패가 전체를 죽이지 않는다.** 실패는 기록하고 계속.

---

## 7. 마일스톤

| 단계 | 산출물 | 검증 방법 |
|---|---|---|
| **M1: 타입+추출기** | types.py, extractor.py + 테스트 | 로컬 HTML fixture로 본문 추출 품질 확인 (네트워크 불필요) |
| **M2: 페처** | fetcher.py, robots.py | 실제 사이트 5~10개 수동 테스트 |
| **M3: 검색 체인** | naver/serper/ddgs + SearchChain | 키워드 입력 → URL 리스트 (API 키 필요) |
| **M4: 파이프라인** | pipeline.py + CLI | `python -m jarvis_crawler "AI 트렌드"` → JSON 파일 출력 |
| **M5: MCP 서버** | mcp_server.py | Claude Desktop 등 MCP 호스트에서 도구 호출 E2E |

M1~M2는 API 키 없이 진행 가능 → **즉시 착수 가능 구간**.
API 키 발급 (네이버 개발자센터, serper.dev)은 M3 전까지 완료 필요.

---

## 8. 열린 질문 (팀 결정 필요)

1. ❓ 페이지당 본문 상한: 5k vs 10k vs 20k 자? (김민석 — LLM 토큰 비교)
2. ❓ 검색 언어 정책: 한국어 질의 → 네이버 우선, 영어 감지 → Serper 우선 자동 스위칭?
3. ❓ 이미지/PDF 처리: v1은 텍스트만? PDF URL은 skip?
4. ❓ 저장 위치: 결과 JSON을 어디에 쓸지 (권유빈 파트의 파일시스템 제어와 연계)
