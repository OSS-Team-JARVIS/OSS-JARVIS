# AI 요약 보고서 생성 모듈 (jarvis_report)

본 모듈은 MCP(Model Context Protocol) 기반 자율 제어 에이전트 JARVIS 프로젝트에서 웹 검색 및 크롤링 등을 통해 수집한 데이터를 전처리하고, 로컬 LLM(Ollama Qwen2.5:3B)을 이용하여 핵심을 요약 및 구조화한 최종 보고서(Markdown, PDF, DOCX)를 자동으로 생성하는 모듈입니다.

---

## 🛠 개발 환경

* Python 3.11 이상
* Ollama (모델: `qwen2.5:3b`)
* Windows 환경
* VSCode
* 가상환경 및 패키지 관리: `uv`

---

## 📂 프로젝트 구조

```text
jarvis_report/
    main.py              # 파이프라인 조율 및 실행 엔트리포인트
    config.py            # 전역 상수 및 설정 정보 관리
    preprocess.py        # 원본 텍스트 전처리 (태그, URL, 중복 공백 제거 등)
    chunk_processor.py   # 대용량 문서 청크 분할 및 오버랩 지원
    prompt_builder.py    # 시나리오별(summary, report, meeting, research) 프롬프트 생성
    providers.py         # LLM 프로바이더 추상화 및 Ollama API 연동 (커스텀 예외 포함)
    validator.py         # AI 결과 마크다운 헤더 검증 및 콜백 기반 재시도
    report_writer.py     # MD/PDF/DOCX 일괄 파일 쓰기 (Pandoc 변환 및 Fallback)
    logger.py            # 시작/종료 시각, 모델명, 오류 내역 기록
    requirements.txt     # 파이썬 의존성 패키지 정의
    README.md            # 가이드 문서 (본 파일)
    .gitignore           # 불필요한 빌드/로그/출력 파일 무시 설정
    reports/             # 요약 보고서 저장 경로 (자동 생성)
    raw_data.txt         # 분석 원본 데이터 입력 파일
```

---

## 🚀 가상환경 구축 및 의존성 설치 (Windows 기준)

본 프로젝트는 고속 패키지 관리자인 `uv`를 활용하여 가상환경을 구축합니다.

### 1. `uv` 설치 (미설치된 경우)
```powershell
pip install uv
```

### 2. 가상환경 `.venv` 생성
```powershell
uv venv
```

### 3. 가상환경 활성화
```powershell
.venv\Scripts\activate
```

### 4. 패키지 설치
```powershell
uv pip install -r requirements.txt
```

---

## 🤖 Ollama 연동 설정

본 모듈은 로컬에서 구동되는 Ollama 엔진을 필요로 합니다.

1. **Ollama 다운로드 및 설치**: [Ollama 공식 홈페이지](https://ollama.com)에서 Windows 버전을 설치합니다.
2. **Qwen 2.5 3B 모델 다운로드**: CLI에서 아래 명령어를 실행하여 로컬 모델을 내려받습니다.
   ```powershell
   ollama pull qwen2.5:3b
   ```
3. **Ollama 서비스 기동**: 트레이 아이콘이나 백그라운드에 Ollama 데몬이 상시 구동 중인지 확인합니다.

---

## 📝 Pandoc 설치 가이드 (PDF/DOCX 변환용)

본 모듈은 Markdown 문서를 PDF 및 DOCX 형식으로 일괄 변환하기 위해 `Pandoc`을 사용합니다. Pandoc이 설치되어 있지 않은 환경인 경우, **Markdown 파일만 생성되고 콘솔 경고와 함께 PDF/DOCX 생성 단계는 자동으로 건너뜁니다(Fallback).**

### 1. Pandoc CLI 설치
* **Windows Package Manager(Winget)로 설치**:
  ```powershell
  winget install JohnMacFarlane.Pandoc
  ```
* **수동 설치**: [Pandoc 공식 Github Release](https://github.com/jgm/pandoc/releases)에서 `.msi` 파일을 다운로드하여 설치한 후, 시스템 환경 변수 `PATH`에 등록합니다.

### 2. PDF 변환 엔진 안내 (PDF 출력이 필요한 경우)
Pandoc이 마크다운을 PDF로 인쇄하기 위해서는 시스템에 LaTeX 혹은 HTML 변환 엔진이 설치되어 있어야 합니다.
* 추천 엔진: `WeasyPrint` 또는 `MikTeX`
* `WeasyPrint`를 활용할 경우 Pandoc 명령 시 자동으로 매핑되거나 관련 설정이 필요할 수 있습니다. PDF 생성이 정상 동작하지 않는 환경에서는 HTML 변환 에러가 콘솔에 출력되고 Markdown/DOCX만 최종 저장되도록 안전하게 예외 처리되어 있습니다.

---

## 💻 실행 방법

### 1. Ollama 로컬 LLM 모드 실행 (Ollama 구동 필요)
1. `jarvis_report` 디렉토리 내에 분석하고자 하는 텍스트 자료를 `raw_data.txt` 파일명으로 저장합니다. (기본적으로 파일이 없을 경우 샘플 텍스트가 자동 생성됩니다.)
2. 가상환경을 활성화한 후 메인 스크립트를 기동합니다.
   ```powershell
   python main.py
   ```

### 2. 가상 시뮬레이션 모드 실행 (Ollama 없이 구동 가능)
로컬에 Ollama가 설치되어 있지 않거나 서버를 기동하기 어려운 환경일 때, 전체 모듈(전처리, 청킹, 헤더 누락 감지, 자동 재시도 콜백, 파일 저장 및 로깅)의 정상 동작을 가상으로 즉시 테스트해볼 수 있습니다.
```powershell
python main.py --mock
```
* 이 모드에서는 AI 요약 모델을 가상의 Mock LLM 객체로 대체하여 파이프라인의 연동 구조를 1초 이내에 시뮬레이션합니다.
* 1차 응답 시 의도적으로 필수 목차를 누락시킨 뒤, 검증기가 재생성 콜백을 수행하여 최종 2차에서 검증을 통과해 보고서 파일들을 저장하는 일련의 디버깅 플로우를 직접 터미널 콘솔 로그로 목격하실 수 있습니다.

---

## 💾 결과물 저장 안내

* 생성 완료 후 `reports/` 폴더에 `JARVIS_AI_Report_YYYYMMDD_HHMMSS.md` (및 `docx`) 형태로 보고서가 일괄 저장됩니다.
* 실행 결과 이력은 `logs/jarvis_report.log` 파일에 기록됩니다.

