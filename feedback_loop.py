import subprocess
import ollama
import sys

file_name = "buggy.py"
max_attempts = 3

for attempt in range(1, max_attempts + 1):
    print(f"\n===== {attempt}번째 실행 =====")

    result = subprocess.run(
        [sys.executable, file_name],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("실행 성공!")
        print(result.stdout)
        break

    error_log = result.stderr

    print("에러 발생!")
    print(error_log)

    with open(file_name, "r", encoding="utf-8") as f:
        current_code = f.read()

    prompt = f"""
너는 Python 코드 오류 수정 전문가다.

현재 Python 코드:
{current_code}

발생한 오류:
{error_log}

반드시 지켜야 할 규칙:
1. 오류의 원인을 정확히 분석한다.
2. 오류를 수정한 전체 Python 코드를 작성한다.
3. 현재 코드의 정상적인 부분은 그대로 유지한다.
4. 존재하지 않는 변수를 새로 만들거나 다른 이름으로 바꾸지 않는다.
5. 설명하지 않는다.
6. 마크다운을 사용하지 않는다.
7. ``` 기호를 절대 사용하지 않는다.
8. Python 코드만 출력한다.
9. 수정된 코드는 바로 실행할 수 있어야 한다.

수정된 전체 Python 코드만 출력해라.
"""

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    fixed_code = response["message"]["content"]
    print("===QWEN이 보낸 원본===")
    print(repr(fixed_code))

    # Qwen이 붙인 마크다운 코드 표시 제거
    fixed_code = fixed_code.replace("```python", "")
    fixed_code = fixed_code.replace("```", "")
    fixed_code = fixed_code.strip()

    print("AI가 수정한 코드:")
    print(fixed_code)

    with open(file_name, "w", encoding="utf-8") as f:
        f.write(fixed_code)

    print("AI가 코드를 수정했습니다.")

else:
    print("\n3번 시도했지만 실행에 성공하지 못했습니다.")