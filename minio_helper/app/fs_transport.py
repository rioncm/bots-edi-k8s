import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FileItem:
    path: str
    name: str
    mtime: float


def list_files(path: str) -> List[FileItem]:
    items: List[FileItem] = []
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Source directory does not exist: {path}")
    with os.scandir(path) as entries:
        for entry in entries:
            if not entry.is_file():
                continue
            stat = entry.stat()
            items.append(FileItem(path=entry.path, name=entry.name, mtime=stat.st_mtime))
    return items


def delete_file(path: str) -> None:
    os.remove(path)
