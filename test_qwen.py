import subprocess
import ollama

result = subprocess.run(
    ["python", "없는파일.py"],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    error_log = result.stderr

    prompt = f"""
명령어 실행 중 오류가 발생했습니다.

에러 로그:
{error_log}

이 오류의 원인과 해결 방법을 알려주세요.
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

    print("에러 로그:")
    print(error_log)

    print("\nQwen의 분석:")
    print(response["message"]["content"])