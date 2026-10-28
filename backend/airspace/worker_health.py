"""Process heartbeat for worker liveness; it does not attest queue progress."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import time
from threading import Event, Thread
from uuid import uuid4

MAX_AGE_SECONDS = 30


def heartbeat_path(runtime: str | Path | None = None, hostname: str | None = None) -> Path:
    host = hostname if hostname is not None else socket.gethostname()
    safe_host = host if re.fullmatch(r"[A-Za-z0-9._-]{1,253}", host) and host not in {".", ".."} else hashlib.sha256(host.encode()).hexdigest()
    return Path(runtime or os.environ.get("AIRSPACE_RUNTIME", "runtime")) / "worker-heartbeats" / ("worker-" + safe_host + ".json")


def process_exists(pid: int) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) must not be used on Windows: non-console signals can
        # invoke TerminateProcess. Query the process without changing its state.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OverflowError):
        return False


def check_worker_health(runtime: str | Path | None = None, *, current: datetime | None = None) -> dict:
    result = {"healthy": False, "scope": "Process liveness only; queue progress is not verified"}
    try:
        path = heartbeat_path(runtime)
        # Windows can briefly deny opening the target while another thread
        # atomically replaces it. Retry only that access error, within 20 ms;
        # persistent denial and all invalid or stale content still fail closed.
        for attempt in range(3):
            try:
                with path.open("rb") as stream:
                    content = stream.read(4097)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.01)
        if len(content) > 4096:
            raise ValueError("Oversized heartbeat")
        record = json.loads(content)
        if not isinstance(record, dict) or record.get("hostname") != socket.gethostname() or type(record.get("pid")) is not int:
            raise ValueError("Invalid heartbeat identity")
        updated = datetime.fromisoformat(record["updated_at"])
        stamp = current or datetime.now(timezone.utc)
        if updated.tzinfo is None or stamp.tzinfo is None:
            raise ValueError("Heartbeat timestamp must identify UTC")
        age = (stamp - updated).total_seconds()
        if not 0 <= age <= MAX_AGE_SECONDS:
            return {**result, "reason": "Heartbeat is stale or future-dated"}
        if not process_exists(record["pid"]):
            return {**result, "reason": "Heartbeat process is unavailable"}
        return {**result, "healthy": True, "age_seconds": age}
    except (OSError, ValueError, TypeError, KeyError):
        return {**result, "reason": "Worker heartbeat is missing or invalid"}


class WorkerHeartbeat:
    """Refresh independently while the main worker performs bounded model work."""
    def __init__(self, runtime: str | Path | None = None, *, interval_seconds: float = 5):
        if not 0 < interval_seconds <= 10:
            raise ValueError("Heartbeat interval must be positive and at most ten seconds")
        self.hostname = socket.gethostname()
        self.path = heartbeat_path(runtime, self.hostname)
        self.interval_seconds = interval_seconds
        self.stopped = Event()
        self.thread: Thread | None = None

    def _write(self):
        content = json.dumps({"hostname": self.hostname, "pid": os.getpid(),
                              "updated_at": datetime.now(timezone.utc).isoformat()}, separators=(",", ":"))
        temporary = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
            os.replace(temporary, self.path)
        finally:
            # This exact temporary filename belongs to this write. Never remove
            # another process's heartbeat or enumerate/delete the directory.
            temporary.unlink(missing_ok=True)

    def _refresh(self):
        while not self.stopped.wait(self.interval_seconds):
            try:
                self._write()
            except OSError:
                # Retry on the next bounded interval. If storage stays broken,
                # the last successful heartbeat expires and health fails closed.
                continue

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write()
        self.thread = Thread(target=self._refresh, name="airspace-worker-heartbeat", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(timeout=self.interval_seconds + 1)


def main() -> int:
    result = check_worker_health()
    print(json.dumps(result))
    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
