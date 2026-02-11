import os
import posixpath
import shutil
import tempfile
from typing import Optional, Tuple


def resolve_file_path(path: str, base_file_path: Optional[str]) -> str:
    if os.path.isabs(path):
        return os.path.normpath(path)
    if not base_file_path:
        raise ValueError("Relative file path requires base_file_path in defaults.")
    return os.path.normpath(os.path.join(base_file_path, path))


def normalize_s3_prefix(path: str) -> str:
    path = path.strip().lstrip("/")
    if path and not path.endswith("/"):
        path = f"{path}/"
    return path


def split_rel_name(rel_name: str) -> Tuple[str, str]:
    dir_part, name_part = posixpath.split(rel_name)
    return dir_part, name_part


def join_rel_path(dir_part: str, name_part: str) -> str:
    if not dir_part:
        return name_part
    return posixpath.join(dir_part, name_part)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def stage_copy_to_temp(src_path: str, tmp_dir: str) -> str:
    fd, tmp_path = tempfile.mkstemp(prefix="stage_", dir=tmp_dir)
    os.close(fd)
    shutil.copyfile(src_path, tmp_path)
    return tmp_path


def atomic_write_from_temp(temp_path: str, dest_path: str) -> None:
    dest_dir = os.path.dirname(dest_path)
    ensure_dir(dest_dir)
    fd, tmp_dest = tempfile.mkstemp(prefix="write_", dir=dest_dir)
    os.close(fd)
    try:
        shutil.copyfile(temp_path, tmp_dest)
        os.replace(tmp_dest, dest_path)
    finally:
        if os.path.exists(tmp_dest):
            os.remove(tmp_dest)
