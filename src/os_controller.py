import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Union


PROTECTED_SYSTEM_PATHS = {
    Path("C:/").resolve(),
    Path("C:/Windows").resolve(),
    Path("C:/Program Files").resolve(),
    Path("C:/Program Files (x86)").resolve(),
    Path("C:/ProgramData").resolve(),
    Path("C:/Users").resolve(),
}


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


def _ensure_safe_delete_target(base_path: Path, target: Union[str, os.PathLike]) -> Path:
    """삭제 대상이 작업 디렉터리 내부이고 보호된 시스템 경로가 아닌지 확인합니다."""
    target_path = _resolve_target_path(base_path, target)

    if target_path == base_path:
        raise PermissionError("작업 디렉터리는 삭제할 수 없습니다.")

    for parent in target_path.parents:
        if parent in PROTECTED_SYSTEM_PATHS and parent not in base_path.parents and parent != base_path:
            raise PermissionError(f"삭제가 금지된 보호된 경로입니다: {target_path}")

    return target_path


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

    def read_file(self, file_name: Union[str, os.PathLike], encoding: str = "utf-8") -> str:
        """지정한 텍스트 파일의 내용을 읽어 문자열로 반환합니다."""
        target_path = _resolve_target_path(self.folder_path, file_name)
        if not target_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {target_path}")
        if not target_path.is_file():
            raise IsADirectoryError(f"파일 경로가 아닙니다: {target_path}")
        return target_path.read_text(encoding=encoding)

    def write_file(self, file_name: Union[str, os.PathLike], content: str, encoding: str = "utf-8") -> Path:
        """텍스트 내용을 지정한 파일에 저장하고, 이미 있으면 덮어씁니다."""
        target_path = _resolve_target_path(self.folder_path, file_name)
        target_path.write_text(content, encoding=encoding)
        return target_path

    def create_folder(self, folder_name: Union[str, os.PathLike]) -> Path:
        """지정한 이름의 새 폴더를 생성합니다. 작업 경로를 벗어나지 않는 경우만 허용합니다."""
        target_path = _resolve_target_path(self.folder_path, folder_name)
        if target_path.exists() and not target_path.is_dir():
            raise FileExistsError(f"이미 파일이 존재합니다: {target_path}")

        target_path.mkdir(parents=True, exist_ok=True)
        return target_path

    def delete_item(self, target: Union[str, os.PathLike], recursive: bool = False) -> None:
        """파일 또는 빈 폴더를 안전하게 삭제합니다. 보호된 경로와 작업 디렉터리 밖의 경로는 차단합니다."""
        target_path = _ensure_safe_delete_target(self.folder_path, target)

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

    def delete_path(self, target: Union[str, os.PathLike], recursive: bool = False) -> None:
        """delete_item의 호환용 별칭입니다."""
        self.delete_item(target, recursive=recursive)

    def search_files(self, query: str, extension: str = None, recursive: bool = True) -> List[Path]:
        """지정한 키워드나 확장자로 파일을 검색해 리스트로 반환합니다."""
        if not query and not extension:
            raise ValueError("검색 키워드나 확장자를 하나 이상 지정해야 합니다.")

        results: List[Path] = []
        search_root = self.folder_path

        def walk(current_dir: Path) -> None:
            for item in sorted(current_dir.iterdir(), key=lambda p: p.name):
                if item.is_dir() and recursive:
                    walk(item)
                if not item.is_file():
                    continue

                name_match = True
                if query:
                    name_match = query.lower() in item.name.lower()
                ext_match = True
                if extension:
                    ext_match = item.suffix.lower() == extension.lower() if extension.startswith(".") else item.suffix.lower() == f".{extension.lower()}"

                if name_match and ext_match:
                    results.append(item)

        walk(search_root)
        return results

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
    temp_root = Path(tempfile.mkdtemp(prefix="os_controller_demo_", dir=str(Path.home())))
    base_dir = temp_root / "temp_test_folder"
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

    # 새 기능 동작 확인용 예제
    demo_dir = base_dir / "demo_case"
    demo_dir.mkdir(exist_ok=True)
    sample_file = demo_dir / "sample.txt"
    sample_file.write_text("demo", encoding="utf-8")
    empty_folder = demo_dir / "empty_folder"
    empty_folder.mkdir(exist_ok=True)

    demo_controller = OSController(demo_dir)
    demo_controller.create_folder("new_folder")
    demo_controller.delete_item(sample_file)
    if empty_folder.exists():
        demo_controller.delete_item(empty_folder)

    print("\n새 기능 테스트 결과:")
    for item in demo_controller.list_contents():
        print(f"- {item.name}")

    text_file = demo_dir / "demo.txt"
    demo_controller.write_file(text_file.name, "hello from os_controller\n", encoding="utf-8")
    read_back = demo_controller.read_file(text_file.name, encoding="utf-8")
    print(f"\n파일 읽기/쓰기 테스트:")
    print(f"- 저장된 내용: {read_back.strip()}")

    overwrite_content = "updated content"
    demo_controller.write_file(text_file.name, overwrite_content, encoding="utf-8")
    updated_text = demo_controller.read_file(text_file.name, encoding="utf-8")
    print(f"- 덮어쓴 내용: {updated_text.strip()}")

    search_results = demo_controller.search_files("demo", extension=".txt")
    print(f"\n검색 테스트:")
    for result in search_results:
        print(f"- {result.name}")

    shutil.rmtree(temp_root, ignore_errors=True)
    print(f"\n테스트 완료: {temp_root} 정리됨")
