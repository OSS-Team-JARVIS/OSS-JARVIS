# 🔍 자율 웹 서칭 파트 — 기술 스택 리서치 보고서

> **작성**: 심규민 (자율 웹 서칭 및 리서치 파트)
> **대상**: 팀JARVIS 전체 (특히 김민석 팀원 — 요약 보고서 파트)
> **목적**: 크롤링 엔진의 기술 선택 근거 공유 및 인터페이스 합의
> **조사 시점**: 2026-08 기준 최신 정보

---

## 0. 한 줄 요약

**네이버 Open API + Serper.dev로 검색하고, curl_cffi로 안전하게 페이지를 받아, trafilatura로 본문만 추출해서 JSON으로 넘겨준다.**

---

## 1. 담당 파트의 위치

```
유저 자연어 명령 ("최신 AI 트렌드 조사해줘")
        ↓
[에이전트 브레인] — 관심사 분석 → 검색 키워드 결정
        ↓
★ [심규민: 검색·크롤링 엔진] ★
   ① 키워드로 구글/네이버 검색 자동 수행
   ② 결과 링크 타고 진입
   ③ 본문 텍스트를 안전하게 추출
        ↓
[김민석: 요약 보고서] — 원본 텍스트 → LLM → 보고서 파일
```

우리 파트는 **"판단"이 아니라 "실행 계층"**: 키워드를 받으면 신뢰성 있게 검색→수집→정제 텍스트를 반환하는 도구(엔진).

---

## 2. 조사 결과 ① — 검색 엔진 접근 방법

### ⚠️ 핵심 발견: Google 공식 API는 사용 불가
Google Custom Search JSON API는 **2025년 신규 가입이 폐쇄**되었고, **2027년 1월 1일 서비스 종료가 확정**됐습니다. 새 프로젝트는 선택지에서 제외.

### 비교표 (2026-08 기준)

| 방법 | 비용 | 한도 | 판정 |
|---|---|---|---|
| **네이버 Open API (웹문서 검색)** | 무료 | **25,000회/일**, 요청당 최대 100건 | ✅ **메인 1순위.** 국내 검색 정확도 최고, 개발자센터 등록만 하면 즉시 사용 |
| **Serper.dev (구글 SERP)** | 2,500회 무료 체험, 이후 $0.30~1.00/1,000건 | 응답 <1초 | ✅ **메인 2순위.** 실제 구글 검색 결과를 JSON으로 반환 |
| Tavily | 1,000회/월 무료 | LLM 최적화 응답 + 본문 추출 내장, 공식 MCP 서버 존재 | ✅ 대안. MCP 생태계 참고 자료로도 가치 |
| DDGS (`pip install ddgs`) | 무료 | **202 Ratelimit 소프트블록 잦음** | ⚠️ 폴백 전용. 주의: 구 `duckduckgo-search`는 2025년 중반 `ddgs`로 이름 변경됨 |
| Playwright 등 직접 SERP 스크래핑 | 무료 | 구글은 CAPTCHA 즉시 차단, 유지보수 비용 과다 | ❌ 비추천 |

> 💡 참고: DDGS의 202 Ratelimit은 "너무 빠르다"는 소프트 경고로, 집 IP(레지덴셜)에서 랜덤 딜레이를 두면 프록시보다 오히려 잘 통과합니다.

---

## 3. 조사 결과 ② — 본문 추출 라이브러리

광고·메뉴·사이드바 등 노이즈를 제거하고 **본문 텍스트만** 뽑는 단계. 여러 벤치마크(ScrapingHub Article Extraction Benchmark, SIGIR 2023/2025 논문) 종합:

| 라이브러리 | F1 점수 | 특징 |
|---|---|---|
| **trafilatura** ⭐ | **0.924 ~ 0.958 (전체 1위)** | 내장 폴백 체인(readability+jusText), Markdown 출력 가능 → LLM 입력에 최적. Apache 2.0 |
| newspaper4k | 0.949 | 노이즈 누수 0%, 작가/날짜 메타데이터 추출. ⚠️ 구버전 newspaper3k는 유지보수 중단 |
| readability-lxml | 0.922 | 출력이 HTML이라 후처리 필요 |
| jusText | 0.804 | 언어별 stoplist 내장 — 한국어 처리 보조 수단으로 가치 |

### ⚠️ 한국어(다국어) 주의사항
SIGIR 2025 연구에 따르면 **모든 본문 추출기는 영어에 최적화**되어 있으며, 비영어권 페이지에서 성능이 떨어집니다. trafilatura가 그나마 가장 안정적이므로:

> **전략: trafilatura 메인 + 실패 시 newspaper4k 폴백**

---

## 4. 조사 결과 ③ — MCP 도구 설계 참조

프로젝트 전체가 MCP 기반이므로, 공식 레퍼런스 구현을 벤치마킹:

| 참조 구현 | 도구 스키마 | 배울 점 |
|---|---|---|
| `modelcontextprotocol/servers` 의 **fetch 서버** | `fetch(url, max_length=5000, start_index)` | 긴 문서를 청크로 나눠 읽히는 패턴, **robots.txt 준수 내장** |
| **brave-search 서버** (brave/brave-search-mcp-server) | `search(query, count≤20, offset≤9)` | 검색 도구의 표준 파라미터 설계 |

→ **제안하는 우리 도구 시그니처**:
```
web_search(query, engine?, count?)   # 검색 실행
crawl(urls[], max_chars?)            # 본문 추출 실행
```

---

## 5. 조사 결과 ④ — "안전하게"의 기술적 정의

PDF 명세의 "안전하게 긁어오기"를 구현 가능한 요구사항으로 분해:

| 위협 | 대응책 |
|---|---|
| **TLS 핑거프린팅 차단** — requests/httpx는 Python/OpenSSL 서명을 가져서 안티봇에 탐지됨 | **curl_cffi** `impersonate="chrome"` — Chrome과 동일한 JA3/TLS 핸드셰이크 재생. MIT 라이선스, async 지원, requests 호환 API |
| IP 차단 | 도메인당 동시 요청 1개 + 수 초 랜덤 딜레이. 429/503 응답의 `Retry-After` 헤더 존중 |
| 재시도 폭주 | tenacity — 지수 백오프(exponential backoff) + 지터(jitter) |
| 크롤링 매너 | robots.txt 파싱(protego), 메타 robots 태그 존중 |
| 한국어 인코딩 지옥 | EUC-KR 등 구형 인코딩 사이트 대응: charset-normalizer |

---

## 6. 제안 아키텍처 (폴백 체인)

```
키워드 입력
   │
   ├─ 네이버 API (국내, 무료 25k/일)      ← 메인
   ├─ Serper.dev (글로벌, 2.5k 무료)      ← 메인
   └─ DDGS                                ← 폴백
   ▼
URL 리스트 (중복 제거)
   ▼
robots.txt 체크 → curl_cffi 순차 페치 (딜레이 포함)
   ▼
trafilatura 본문 추출 (실패 시 newspaper4k)
   ▼
{url, title, content, domain, fetched_at} JSON → 김민석 파트 전달
```

---

## 7. 🤝 김민석 팀원과 협의 필요 사항 (Action Items)

1. **출력 JSON 스키마 합의** — 필드명 / UTF-8 고정
   ```json
   {
     "query": "검색 키워드",
     "results": [
       { "url": "...", "title": "...", "content": "본문 텍스트",
         "domain": "...", "fetched_at": "ISO8601" }
     ]
   }
   ```
2. **페이지당 본문 상한** — LLM 토큰 비용 직결 (예: 페이지당 5,000~10,000자)
3. **실패 페이지 정책** — error 필드로 전달할지 / 조용히 스킵할지

---

## 부록: 주요 출처

- 네이버 개발자 센터 — 검색 API 명세 (25,000회/일): developers.naver.com/docs/serviceapi/search/web/web.md
- Google Custom Search JSON API 종료 공지: developers.google.com/custom-search/v1/overview
- trafilatura 공식 평가 문서: trafilatura.readthedocs.io/en/latest/evaluation.html
- ScrapingHub Article Extraction Benchmark: github.com/scrapinghub/article-extraction-benchmark
- SIGIR 2025 "Multilingual Evaluation of Main Content Extractors"
- curl_cffi (TLS impersonation): github.com/lexiforest/curl_cffi
- MCP 공식 레퍼런스 서버: github.com/modelcontextprotocol/servers
