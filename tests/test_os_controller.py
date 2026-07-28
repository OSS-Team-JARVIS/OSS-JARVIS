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

    def test_prevents_path_traversal_outside_base(self):
        with self.assertRaises(ValueError):
            self.controller.create_folder("../outside")

        outside_file = self.root.parent / "outside.txt"
        with self.assertRaises(ValueError):
            self.controller.delete_path(outside_file)


if __name__ == "__main__":
    unittest.main()
