import unittest
from pathlib import Path


class FrontendDeleteConfirmationTests(unittest.TestCase):
    def test_delete_flow_requires_confirmation_before_request(self):
        project_root = Path(__file__).resolve().parents[1]
        html_candidates = [
            project_root / "static" / "index.html",
            project_root / "index.html",
        ]
        html_path = next((path for path in html_candidates if path.is_file()), None)
        self.assertIsNotNone(html_path, "static/index.html 또는 index.html을 찾을 수 없습니다.")
        html_text = html_path.read_text(encoding="utf-8")

        self.assertIn("let deleteConfirmationApproved = false;", html_text)
        self.assertIn("if (action === 'delete' && !deleteConfirmationApproved)", html_text)
        self.assertIn("deleteConfirmationApproved = true;", html_text)
