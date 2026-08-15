import unittest
from pathlib import Path


class FrontendDeleteConfirmationTests(unittest.TestCase):
    def test_delete_flow_requires_confirmation_before_request(self):
        html_path = Path(__file__).resolve().parents[1] / ".." / "test.html"
        html_text = html_path.read_text(encoding="utf-8")

        self.assertIn("let deleteConfirmationApproved = false;", html_text)
        self.assertIn("if (action === 'delete' && !deleteConfirmationApproved)", html_text)
        self.assertIn("deleteConfirmationApproved = true;", html_text)
