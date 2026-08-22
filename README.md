# OSS-JARVIS

Team JARVIS의 자율 웹 서칭·크롤링 엔진입니다. 검색 키워드 하나로
네이버·Serper·DuckDuckGo를 순서대로 폴백 검색하고, 상위 URL을
robots.txt를 존중하며 수집해 본문만 추출합니다.

## 주요 기능
- 다중 검색 엔진 폴백 체인(naver → serper → ddgs)
- curl_cffi 기반 페이지 페치(TLS impersonation)와 robots.txt 게이트
- trafilatura/newspaper4k 본문 추출, 실패는 FailedFetch로 감사 가능
- 결과 JSON 리서치 리포트(CLI)와 MCP 도구 노출(web_search·crawl)

## 설치
Python 3.13+ 와 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync
```

## 환경변수(모두 선택 사항)

| 변수 | 용도 |
|---|---|
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 개발자센터 검색 API |
| `SERPER_API_KEY` | Serper.dev API |

자격 증명이 없는 엔진은 체인에서 자동으로 건너뛰며,
DuckDuckGo(ddgs)는 키 없이 항상 마지막 폴백으로 동작합니다.

## CLI 사용

```bash
# "AI 트렌드"로 검색→크롤링 후 research_<타임스탬프>.json 생성
uv run python -m jarvis_crawler "AI 트렌드"

# 옵션 조정: 결과 5건, 최대 3페이지, 페이지당 4000자, 출력 경로 지정
uv run python -m jarvis_crawler "AI 트렌드" --count 5 --max-pages 3 --max-chars 4000 -o out.json
```

모든 검색 엔진이 실패하면 사유를 stderr에 남기고 종료 코드 1로 끝납니다.

## MCP 서버(MCP 클라이언트 연동)

```bash
uv run python -m jarvis_crawler.mcp_server
```

Claude Desktop 설정 예시(`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jarvis-crawler": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "<프로젝트 경로>",
        "python",
        "-m",
        "jarvis_crawler.mcp_server"
      ]
    }
  }
}
```

제공 도구:
- `web_search(query, engine?, count=10)` — 검색 결과 JSON 배열. engine은 naver|serper|ddgs(미지정 시 폴백 체인).
- `crawl(urls, max_chars=10000)` — URL 목록 직접 수집. 본문 페이지와 실패 목록 JSON 반환.

## 테스트

```bash
uv run pytest tests/test_types.py tests/test_extractor.py tests/test_fetcher.py tests/test_robots.py tests/test_search_providers.py tests/test_pipeline.py tests/test_mcp_server.py
```

> 저장소 루트의 레거시 데모 앱 테스트(`test_os_controller.py` 등)는 현재 정비 대상이라 위 스코프 실행을 권장합니다.
