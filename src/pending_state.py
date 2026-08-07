from __future__ import annotations

from typing import Dict, List, Optional


class PendingStateStore:
    def __init__(self) -> None:
        self._entries: List[Dict[str, object]] = []

    def add_entry(self, folder_path: str, search_query: str, files: List[str], reason: str, created_at: str) -> Dict[str, object]:
        entry = {
            "id": str(len(self._entries) + 1),
            "folderPath": folder_path,
            "searchQuery": search_query,
            "files": files,
            "reason": reason,
            "createdAt": created_at,
        }
        self._entries.insert(0, entry)
        return entry

    def list_entries(self) -> List[Dict[str, object]]:
        return list(self._entries)

    def remove_entry(self, entry_id: str) -> Optional[Dict[str, object]]:
        for index, entry in enumerate(self._entries):
            if entry["id"] == entry_id:
                return self._entries.pop(index)
        return None

    def restore_entry(self, entry_id: str) -> Optional[Dict[str, object]]:
        return self.remove_entry(entry_id)
