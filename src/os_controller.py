import os
import shutil
from pathlib import Path
from typing import Dict, List, Union


def _resolve_target_path(base_path: Path, target: Union[str, os.PathLike]) -> Path:
    """작업 경로가 기반 폴더 안에 있는지 확인하면서 경로를 정규화합니다."""
    candidate = Path(os.fspath(target)).expanduser()
    if not candidate.is_absolute():
        candidate = base_path / candidate

    resolved = candidate.resolve()
    base_resolved = base_path.resolve()

    if resolved != base_resolved and base_resolved not in resolved.parents:
        raise ValueError(f"작업 경로가 허용된 범위를 벗어났습니다: {target}")

    return resolved


def list_folder_contents(folder_path: Union[str, os.PathLike]) -> List[Path]:
    """지정한 폴더 안의 파일 및 하위 폴더 목록을 읽어옵니다."""
    target = Path(os.fspath(folder_path)).expanduser()

    if not os.path.exists(target):
        raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {target}")
    if not os.path.isdir(target):
        raise NotADirectoryError(f"폴더 경로가 아닙니다: {target}")

    return sorted([item for item in target.iterdir()], key=lambda item: item.name)


class OSController:
    """파일을 확장자별 폴더로 분류하여 이동하는 컨트롤러입니다."""

    def __init__(self, folder_path: Union[str, os.PathLike]):
        self.folder_path = Path(os.fspath(folder_path)).expanduser().resolve()

        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"폴더를 찾을 수 없습니다: {self.folder_path}")
        if not os.path.isdir(self.folder_path):
            raise NotADirectoryError(f"폴더 경로가 아닙니다: {self.folder_path}")

    def list_contents(self) -> List[Path]:
        """현재 설정된 폴더의 내용 목록을 반환합니다."""
        return list_folder_contents(self.folder_path)

    def create_folder(self, folder_name: Union[str, os.PathLike]) -> Path:
        """지정한 이름의 새 폴더를 생성합니다. 작업 경로를 벗어나지 않는 경우만 허용합니다."""
        target_path = _resolve_target_path(self.folder_path, folder_name)
        if target_path.exists() and not target_path.is_dir():
            raise FileExistsError(f"이미 파일이 존재합니다: {target_path}")

        target_path.mkdir(parents=True, exist_ok=True)
        return target_path

    def delete_path(self, target: Union[str, os.PathLike], recursive: bool = False) -> None:
        """파일 또는 빈 폴더를 안전하게 삭제합니다. 폴더가 비어 있지 않으면 recursive=True가 필요합니다."""
        target_path = _resolve_target_path(self.folder_path, target)

        if not target_path.exists():
            raise FileNotFoundError(f"삭제 대상이 존재하지 않습니다: {target_path}")

        if target_path.is_dir() and any(target_path.iterdir()):
            if not recursive:
                raise OSError(f"폴더가 비어 있지 않아 삭제할 수 없습니다: {target_path}")
            shutil.rmtree(target_path)
        else:
            if target_path.is_dir():
                target_path.rmdir()
            else:
                target_path.unlink()

    def classify_files_by_extension(self, create_folders: bool = True) -> Dict[str, List[Path]]:
        """확장자별로 파일을 폴더로 나누어 이동합니다."""
        moved_files: Dict[str, List[Path]] = {}

        for item in self.folder_path.iterdir():
            if not item.is_file():
                continue

            extension = item.suffix.lower() if item.suffix else "no_extension"
            folder_name = extension[1:] if extension.startswith(".") else extension
            destination_dir = self.folder_path / folder_name

            if create_folders:
                os.makedirs(destination_dir, exist_ok=True)

            destination_path = destination_dir / item.name
            if destination_path.exists():
                stem = item.stem
                suffix = item.suffix
                counter = 1
                while destination_path.exists():
                    destination_path = destination_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(item), str(destination_path))
            moved_files.setdefault(folder_name, []).append(destination_path)

        return moved_files


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent / "temp_test_folder"
    base_dir.mkdir(exist_ok=True)

    for name in ["notes.txt", "photo.jpg", "script.py", "archive.tar.gz", "README"]:
        file_path = base_dir / name
        file_path.write_text("sample", encoding="utf-8")

    controller = OSController(base_dir)
    print("초기 폴더 내용:")
    for item in controller.list_contents():
        print(f"- {item.name}")

    result = controller.classify_files_by_extension()
    print("\n분류 결과:")
    for folder_name, files in result.items():
        print(f"[{folder_name}]")
        for file_path in files:
            print(f"  - {file_path.name}")

    print("\n정리 후 폴더 내용:")
    for item in controller.list_contents():
        print(f"- {item.name}")

    print(f"\n성공: {len(result)}개 폴더로 파일 정리가 완료되었습니다.")
