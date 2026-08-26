import unittest

import feedback_loop


class FeedbackLoopTests(unittest.TestCase):
    def test_build_feedback_prompt_includes_log_and_code(self):
        prompt = feedback_loop.build_feedback_prompt("traceback here", "print('hello')")

        self.assertIn("traceback here", prompt)
        self.assertIn("print('hello')", prompt)

    def test_analyze_error_log_falls_back_without_ollama(self):
        original_ollama = feedback_loop.ollama
        feedback_loop.ollama = None
        try:
            result = feedback_loop.analyze_error_log("traceback")
        finally:
            feedback_loop.ollama = original_ollama

        self.assertFalse(result["success"])
        self.assertIn("ollama 패키지가 설치되어 있지 않습니다.", result["error"])