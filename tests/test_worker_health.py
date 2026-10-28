"""Isolated process-heartbeat checks, never operational readiness assertions."""
from datetime import datetime, timedelta, timezone
import json
import os
import socket
import sys
import time

import pytest

from airspace.worker_health import (WorkerHeartbeat, check_worker_health,
                                    heartbeat_path, process_exists, main)


def write_record(runtime, *, updated=None, pid=None, hostname=None):
    path = heartbeat_path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"hostname": hostname or socket.gethostname(),
              "pid": os.getpid() if pid is None else pid,
              "updated_at": (updated or datetime.now(timezone.utc)).isoformat()}
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_missing_heartbeat_fails_without_claiming_queue_progress(tmp_path):
    result = check_worker_health(tmp_path)
    assert not result["healthy"]
    assert "queue progress is not verified" in result["scope"]
    assert not heartbeat_path(tmp_path).exists()


@pytest.mark.parametrize("age,healthy", [(30, True), (31, False), (-1, False)])
def test_freshness_is_bounded_including_future_clock_values(tmp_path, age, healthy):
    current = datetime(2030, 1, 1, tzinfo=timezone.utc)
    write_record(tmp_path, updated=current - timedelta(seconds=age))
    assert check_worker_health(tmp_path, current=current)["healthy"] is healthy


def test_wrong_or_invalid_pid_does_not_report_a_live_worker(tmp_path):
    assert process_exists(os.getpid())
    assert not process_exists(0)
    assert not process_exists(-1)
    assert not process_exists(True)
    write_record(tmp_path, pid=2_147_483_647)
    result = check_worker_health(tmp_path)
    assert not result["healthy"]
    assert result["reason"] == "Heartbeat process is unavailable"


def test_heartbeat_belongs_to_this_hostname(tmp_path):
    write_record(tmp_path, hostname="other-isolated-test-host")
    assert not check_worker_health(tmp_path)["healthy"]
    escaped = heartbeat_path(tmp_path, "../../outside-isolated-root")
    assert escaped.parent == tmp_path / "worker-heartbeats"


@pytest.mark.parametrize("content", ["invalid json", "[]", '{"pid": true}', "x" * 4097])
def test_invalid_or_oversized_heartbeat_fails_closed(tmp_path, content):
    path = heartbeat_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    assert not check_worker_health(tmp_path)["healthy"]


def test_naive_timestamp_is_rejected(tmp_path):
    write_record(tmp_path, updated=datetime(2030, 1, 1))
    assert not check_worker_health(tmp_path)["healthy"]


def test_actual_context_refreshes_during_main_thread_work_and_stops_cleanly(tmp_path):
    with WorkerHeartbeat(tmp_path, interval_seconds=0.02) as heartbeat:
        first = json.loads(heartbeat.path.read_text(encoding="utf-8"))
        assert heartbeat.thread.daemon and heartbeat.thread.is_alive()
        deadline = time.monotonic() + 2
        latest = first
        # The main thread does not call a refresh function. The real daemon must
        # keep writing while the worker can be occupied with another task.
        while latest["updated_at"] == first["updated_at"] and time.monotonic() < deadline:
            time.sleep(0.02)
            latest = json.loads(heartbeat.path.read_text(encoding="utf-8"))
        assert latest["updated_at"] != first["updated_at"]
        assert latest["pid"] == os.getpid()
        assert set(latest) == {"hostname", "pid", "updated_at"}
        assert check_worker_health(tmp_path)["healthy"]
    assert not heartbeat.thread.is_alive()
    assert not list(heartbeat.path.parent.glob("*.tmp"))


def test_health_command_exit_status_and_liveness_boundary(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AIRSPACE_RUNTIME", str(tmp_path))
    assert main() == 1
    assert not json.loads(capsys.readouterr().out)["healthy"]
    with WorkerHeartbeat(tmp_path):
        assert main() == 0
        result = json.loads(capsys.readouterr().out)
        assert result["healthy"]
        assert "queue progress is not verified" in result["scope"]


def test_worker_cli_runs_inside_actual_heartbeat_context(tmp_path, monkeypatch):
    from airspace import cli, worker
    from airspace.storage import Store
    store = Store("sqlite:///" + (tmp_path / "isolated-worker.db").as_posix(),
                  b"isolated-worker-heartbeat-test-key")
    monkeypatch.setenv("AIRSPACE_RUNTIME", str(tmp_path))
    monkeypatch.setattr(cli, "local_store", lambda: store)
    monkeypatch.setattr(sys, "argv", ["airspace", "worker", "--once"])
    observations = []

    def isolated_no_job(_):
        observations.append(check_worker_health(tmp_path))
        return None

    monkeypatch.setattr(worker, "run_once", isolated_no_job)
    try:
        cli.main()
    finally:
        store.engine.dispose()
    assert len(observations) == 1 and observations[0]["healthy"]
