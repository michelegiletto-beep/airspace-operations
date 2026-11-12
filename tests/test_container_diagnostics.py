"""Isolated collector tests: no Docker daemon, application or operator data."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

SPEC = importlib.util.spec_from_file_location(
    "container_diagnostics", Path(__file__).resolve().parents[1] / "scripts/collect_container_diagnostics.py")
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


def test_only_owned_project_commands_and_allowlisted_state_are_requested():
    calls = []
    identifier = "a" * 64
    def runner(args, **kwargs):
        calls.append((args, kwargs))
        output = identifier + "\n--bad\n$(touch-nope)\n" if args[-1] == "--quiet" else "worker failed"
        return subprocess.CompletedProcess(args, 0, output, "")
    report = diagnostics.collect({"COMPOSE_PROJECT_NAME": "airspace-ci-123"}, runner)
    assert len(calls) == 4
    assert all(isinstance(args, list) and not opts["shell"] and opts["timeout"] == 15
               for args, opts in calls)
    assert all(args[2:4] == ["--project-name", "airspace-ci-123"]
               for args, _ in calls if args[1] == "compose")
    inspect = calls[2][0]
    assert inspect == ["docker", "inspect", "--format", diagnostics.STATE_FORMAT, identifier]
    assert ".Config.Env" not in inspect[3]
    assert all(field in inspect[3] for field in (".State.Status", ".State.ExitCode", ".State.Error", ".State.Health",
                                               ".State.StartedAt", ".State.FinishedAt", ".State.OOMKilled", ".RestartCount",
                                               ".State.Running", ".State.Restarting"))
    assert len(report["warnings"]) == 2


def test_inspect_subprocess_budget_is_bounded_even_for_valid_identifiers():
    calls = []
    def runner(args, **kwargs):
        calls.append(args)
        output = "\n".join(f"{index:064x}" for index in range(20)) if args[-1] == "--quiet" else ""
        return subprocess.CompletedProcess(args, 0, output, "")
    report = diagnostics.collect({"COMPOSE_PROJECT_NAME": "airspace-ci-123"}, runner)
    assert len(calls) == 3 + diagnostics.MAX_CONTAINERS == 11
    assert report["omitted_container_count"] == 12


@pytest.mark.parametrize("project", ["", "../operator", "--help", "AIRSPACE", "x;whoami"])
def test_invalid_project_never_invokes_subprocess(project):
    def forbidden(*args, **kwargs):
        pytest.fail("Docker must not be invoked")
    assert "error" in diagnostics.collect({"COMPOSE_PROJECT_NAME": project}, forbidden)


def test_secret_environment_and_url_credentials_redacted_from_both_streams():
    env = {"COMPOSE_PROJECT_NAME": "airspace-ci-123", "AIRSPACE_AUDIT_KEY": "actual-key",
           "OTHER_TOKEN": "actual-token", "POSTGRES_PASSWORD": "actual-password",
           "AIRSPACE_DATABASE_URL": "postgresql://app:actual-db-password@db/airspace"}
    text = " ".join(env.values()) + " https://different:unlisted-password@host/path"
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, text, text)
    output = diagnostics.render(diagnostics.collect(env, runner), env)
    for secret in ("actual-key", "actual-token", "actual-password", "actual-db-password", "unlisted-password"):
        assert secret not in output
    assert "[REDACTED]" in output


@pytest.mark.parametrize("failure", [FileNotFoundError("private-secret"),
                                    subprocess.TimeoutExpired("docker", 15, output="private-secret")])
def test_collection_failure_is_bounded_and_does_not_leak_exception_output(failure, monkeypatch, capsys):
    def runner(*args, **kwargs):
        raise failure
    report = diagnostics.collect({"COMPOSE_PROJECT_NAME": "airspace-ci-123"}, runner)
    assert len(report["commands"]) == 3
    assert "private-secret" not in diagnostics.render(report, {})
    monkeypatch.setattr(diagnostics, "collect", lambda: report)
    assert diagnostics.main() == 0
    json.loads(capsys.readouterr().out)


def test_output_has_hard_byte_bound_and_valid_json():
    output = diagnostics.render({"logs": "\\\"\n" * 100000}, {})
    assert len(output.encode("utf-8")) <= 64 * 1024
    assert json.loads(output)["truncated"] is True


def test_decisive_state_is_collected_before_large_logs_are_truncated():
    identifier = "a" * 64
    def runner(args, **kwargs):
        if args[-1] == "--quiet":
            output = identifier
        elif args[1] == "inspect":
            output = "decisive-early-process-exit"
        elif "logs" in args:
            output = "verbose-log" * 100000
        else:
            output = "worker restarting"
        return subprocess.CompletedProcess(args, 0, output, "")
    output = diagnostics.render(diagnostics.collect({"COMPOSE_PROJECT_NAME": "airspace-ci-123"}, runner), {})
    assert len(output.encode("utf-8")) <= diagnostics.MAX_BYTES
    assert "decisive-early-process-exit" in output
    assert json.loads(output)["truncated"] is True
