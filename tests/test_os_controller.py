import tempfile
import unittest
from pathlib import Path

from src.os_controller import OSController


class OSControllerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.controller = OSController(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_folder_within_base(self):
        created = self.controller.create_folder("safe_folder")

        self.assertTrue(created.exists())
        self.assertTrue(created.is_dir())
        self.assertEqual(created, self.root / "safe_folder")

    def test_delete_file_and_empty_folder_safely(self):
        file_path = self.root / "notes.txt"
        file_path.write_text("hello", encoding="utf-8")
        self.controller.delete_path(file_path)
        self.assertFalse(file_path.exists())

        empty_folder = self.root / "empty_dir"
        empty_folder.mkdir()
        self.controller.delete_path(empty_folder)
        self.assertFalse(empty_folder.exists())

    def test_search_without_query_returns_all_files(self):
        (self.root / "a.txt").write_text("alpha", encoding="utf-8")
        (self.root / "b.md").write_text("beta", encoding="utf-8")

        results = self.controller.search_files("")

        self.assertEqual(len(results), 2)
        self.assertTrue(all(path.exists() for path in results))

    def test_search_ignores_hidden_directories(self):
        visible_file = self.root / "visible.txt"
        visible_file.write_text("visible", encoding="utf-8")

        hidden_dir = self.root / ".git" / "objects"
        hidden_dir.mkdir(parents=True)
        (hidden_dir / "secret.txt").write_text("hidden", encoding="utf-8")

        results = self.controller.search_files("")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], visible_file)

    def test_prevents_path_traversal_outside_base(self):
        with self.assertRaises(ValueError):
            self.controller.create_folder("../outside")

        outside_file = self.root.parent / "outside.txt"
        with self.assertRaises(ValueError):
            self.controller.delete_path(outside_file)


if __name__ == "__main__":
    unittest.main()
