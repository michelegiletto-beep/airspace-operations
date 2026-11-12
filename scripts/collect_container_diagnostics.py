"""Best-effort, read-only CI diagnostics; never replace the failed gate's exit."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 64 * 1024
TIMEOUT = 15
MAX_CONTAINERS = 8
PROJECT = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}\Z")
CONTAINER_ID = re.compile(r"[a-f0-9]{12,64}\Z")
SECRET_NAME = re.compile(r"AUDIT_KEY|PASSWORD|TOKEN|SECRET|DATABASE_URL", re.I)
URL_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]{0,31}://)[^\s/@]+@", re.I)
STATE_FORMAT = ('{"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
                '"status":{{json .State.Status}},"exit_code":{{json .State.ExitCode}},'
                '"error":{{json .State.Error}},"health":{{json .State.Health}},'
                '"started_at":{{json .State.StartedAt}},"finished_at":{{json .State.FinishedAt}},'
                '"oom_killed":{{json .State.OOMKilled}},"restart_count":{{json .RestartCount}},'
                '"running":{{json .State.Running}},"restarting":{{json .State.Restarting}}}')


def redact(value: str, environment: dict[str, str]) -> str:
    for secret in sorted({v for k, v in environment.items() if v and SECRET_NAME.search(k)},
                         key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    return URL_CREDENTIALS.sub(r"\1[REDACTED]@", value)


def collect(environment=None, runner=None) -> dict:
    environment = dict(os.environ if environment is None else environment)
    runner = subprocess.run if runner is None else runner
    project = environment.get("COMPOSE_PROJECT_NAME", "")
    report = {"scope": "read-only isolated compose diagnostics", "commands": []}
    if not PROJECT.fullmatch(project):
        report["error"] = "COMPOSE_PROJECT_NAME is missing or invalid; no Docker command executed"
        return report
    report["project"] = project
    compose = ["docker", "compose", "--project-name", project,
               "-f", "compose.yaml", "-f", "deploy/compose.ci.yaml"]

    def run(arguments):
        entry = {"command": arguments}
        report["commands"].append(entry)
        try:
            result = runner(arguments, cwd=ROOT, env=environment, capture_output=True,
                            text=True, timeout=TIMEOUT, check=False, shell=False)
            entry.update(exit_code=result.returncode,
                         stdout=redact(result.stdout or "", environment),
                         stderr=redact(result.stderr or "", environment))
            return result.stdout if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired) as error:
            # TimeoutExpired may contain secret-bearing output; do not stringify it.
            entry["error"] = type(error).__name__
            return None

    run(compose + ["ps", "--all"])
    identifiers = run(compose + ["ps", "--all", "--quiet"])
    if identifiers:
        valid = []
        for identifier in dict.fromkeys(identifiers.split()):
            if not CONTAINER_ID.fullmatch(identifier):
                report.setdefault("warnings", []).append("Invalid container identifier rejected")
                continue
            valid.append(identifier)
        if len(valid) > MAX_CONTAINERS:
            report["omitted_container_count"] = len(valid) - MAX_CONTAINERS
        for identifier in valid[:MAX_CONTAINERS]:
            # Only identifiers selected by this explicit Compose project are inspected.
            run(["docker", "inspect", "--format", STATE_FORMAT, identifier])
    # Preserve the decisive state first if unusually large logs hit the output cap.
    run(compose + ["logs", "--no-color", "--tail", "120"])
    return report


def render(report: dict, environment=None) -> str:
    environment = dict(os.environ if environment is None else environment)
    output = redact(json.dumps(report, ensure_ascii=True, sort_keys=True), environment)
    if len(output.encode("utf-8")) > MAX_BYTES:
        # Keep valid JSON and an explicit bound, even for unusually verbose failures.
        output = json.dumps({"truncated": True, "diagnostics": output[:MAX_BYTES // 2]},
                            ensure_ascii=True)
        while len(output.encode("utf-8")) > MAX_BYTES:
            output = json.dumps({"truncated": True, "diagnostics": output[:MAX_BYTES // 4]})
    return output


def main() -> int:
    try:
        print(render(collect()))
    except Exception as error:
        # Diagnostics must never obscure the original health-step failure.
        print(json.dumps({"diagnostic_collection_failed": type(error).__name__}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
