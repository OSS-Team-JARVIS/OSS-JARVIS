import tempfile
import unittest
from pathlib import Path

import server
from src.os_controller import OSController


class ServerSelectionTests(unittest.TestCase):
    def test_selected_files_are_used_for_delete_targets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            selected = base / "selected.txt"
            selected.write_text("selected", encoding="utf-8")
            other = base / "other.txt"
            other.write_text("other", encoding="utf-8")

            controller = OSController(base)
            payload = {"selectedFiles": [str(selected)]}

            resolved = server.resolve_delete_targets(payload, controller, "")

            self.assertEqual(resolved, [str(selected)])
