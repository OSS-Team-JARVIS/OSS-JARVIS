# OSS-JARVIS

OSS-JARVIS는 검색·크롤링부터 로컬 파일 작업, AI 피드백, Markdown 보고서까지
연결하는 4단계 통합 파이프라인입니다.

## 파이프라인 구조

```text
검색 쿼리
  -> 1. 스마트 웹 크롤링(jarvis_crawler)
  -> 2. 로컬 OS 제어(OSController)
  -> 3. AI 피드백 루프(feedback_loop)
  -> 4. 요약 보고서 생성(jarvis_report)
```

- `jarvis_crawler`: Naver, Serper, DDGS 검색 폴백, robots.txt 확인, 페이지 수집 및 본문 추출
- `OSController`: 경로·권한 확인, 파일 검색·분류·삭제
- `feedback_loop.py`: 전달받은 코드와 오류 로그를 분석하는 선택적 피드백 루프
- `jarvis_report`: 원문 전처리, 청킹, 요약, Markdown 저장
- `server.py`: 웹 UI와 API를 제공하며 `POST /api/run-all`로 전체 흐름을 실행
- `static/index.html`: 검색어·경로 입력, 상태 타임라인, 보고서 결과 표시

## 설치

Python 3.13 이상을 권장합니다. `uv`를 사용하는 경우:

```powershell
uv sync
```

일반 Python 환경에서는 프로젝트 의존성을 설치합니다:

```powershell
py -3 -m pip install -e .
```

보고서의 실제 Ollama 모드를 사용할 때는 추가로 설치합니다:

```powershell
py -3 -m pip install -r jarvis_report/requirements.txt
```

테스트 도구:

```powershell
py -3 -m pip install pytest pytest-asyncio
```

## 오프라인 1초 시연

서버를 실행합니다:

```powershell
py -3 server.py
```

다른 PowerShell 창에서 Mock 크롤링 결과를 즉시 확인합니다:

```powershell
py -3 -c "import server; print(server._run_crawler('offline demo', 1, 1, 1000, use_mock=True))"
```

외부 네트워크와 검색 API 키 없이 전체 API를 테스트하려면 다음 요청을 사용합니다:

```powershell
$body = @{
  query = "offline demo"
  count = 1
  maxPages = 1
  maxChars = 1000
  rawDataDir = "$PWD"
  folderPath = "$PWD"
  osAction = "search"
  searchQuery = "README"
  useMockCrawler = $true
  useMockFeedback = $true
  runFeedback = $true
  useMock = $true
  projectName = "JARVIS_Offline_Demo"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/run-all" -Method POST `
  -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 10
```

빈 크롤링 결과는 UTF-8로 `[Notice] Crawled data is empty.`를 저장하므로
보고서 입력 파일이 비어 파싱되는 문제를 방지합니다.

## 브라우저 사용법

브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000)을 엽니다.

첫 실행은 다음처럼 Mock 모드를 사용합니다:

- 명령/질의: `AI agent trends`
- 로컬 경로: 프로젝트 폴더 경로
- 크롤링 원문 저장 폴더: 프로젝트 폴더 경로 또는 빈칸
- OS 액션: `search`
- OS 검색어: `README`
- 크롤러 Mock: `true`
- 피드백 Mock: `true`
- 보고서 Mock: `true`

`경로 검증` 후 `통합 워크플로우 실행`을 누르면 크롤링, OS 파일 작업,
AI 피드백, 보고서 생성 상태와 최종 Markdown 내용 및 저장 경로가 표시됩니다.

## 실제 검색 및 보고서

실제 검색은 외부 네트워크를 사용합니다. Naver 또는 Serper를 사용하려면
다음 환경 변수를 설정할 수 있습니다:

```text
NAVER_CLIENT_ID
NAVER_CLIENT_SECRET
SERPER_API_KEY
```

실제 Ollama 보고서를 사용하려면 Ollama를 실행하고 모델을 준비합니다:

```powershell
ollama serve
ollama pull qwen2.5:3b
```

## 테스트

```powershell
py -3 -m pytest -q
```

비동기 테스트 모드는 루트 `pytest.ini`에서 `asyncio_mode = auto`로 설정됩니다.
