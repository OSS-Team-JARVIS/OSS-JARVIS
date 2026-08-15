import unittest

from src.pending_state import PendingStateStore


class PendingStateStoreTests(unittest.TestCase):
    def test_add_and_remove_pending_entry(self):
        store = PendingStateStore()

        entry = store.add_entry(
            folder_path="C:/demo",
            search_query="report",
            files=["C:/demo/report.pdf"],
            reason="검토 후 결정",
            created_at="2026-08-07 10:00"
        )

        self.assertEqual(entry["reason"], "검토 후 결정")
        self.assertEqual(len(store.list_entries()), 1)

        removed = store.remove_entry(entry["id"])
        self.assertEqual(removed["id"], entry["id"])
        self.assertEqual(store.list_entries(), [])

    def test_restore_entry_returns_entry_and_removes_it(self):
        store = PendingStateStore()

        entry = store.add_entry(
            folder_path="C:/demo",
            search_query="image",
            files=["C:/demo/photo.jpg"],
            reason="나중에 확인",
            created_at="2026-08-07 10:05"
        )

        restored = store.restore_entry(entry["id"])

        self.assertEqual(restored["id"], entry["id"])
        self.assertEqual(store.list_entries(), [])
