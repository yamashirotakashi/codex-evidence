"""Queue operations: _append_jsonl_record, _exclusive_lock."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import contextlib


def _append_jsonl_record(queue_path: Path, event: object) -> None:
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    record = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    with _exclusive_lock(queue_path.with_suffix(queue_path.suffix + ".lock")):
        with queue_path.open("ab") as stream:
            stream.write(record)


@contextlib.contextmanager
def _exclusive_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("xb") as new_lock:
            new_lock.write(b"\0")
    except (FileExistsError, PermissionError):
        pass
    with lock_path.open("r+b") as lock_file:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
