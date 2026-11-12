"""Run the real health shell against an isolated psql substitute, never a database."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/database-health.sh"
BASH = shutil.which("bash")
if not BASH and Path("C:/Program Files/Git/bin/bash.exe").is_file():
    BASH = "C:/Program Files/Git/bin/bash.exe"
pytestmark = pytest.mark.skipif(not BASH, reason="Requires bash; actual Linux CI also runs this script")


def shell_path(path):
    path = path.resolve()
    return "/" + path.drive[0].lower() + path.as_posix()[2:] if os.name == "nt" else str(path)


@pytest.fixture
def probe(tmp_path):
    executable = tmp_path / "psql"
    executable.write_text("""#!/bin/sh
printf '%s\\n' "$PGPASSWORD" > "$HEALTH_TEST_CAPTURE/password"
printf '%s\\n' "$@" > "$HEALTH_TEST_CAPTURE/arguments"
printf '%s\\n' "$PGOPTIONS" > "$HEALTH_TEST_CAPTURE/options"
cat > "$HEALTH_TEST_CAPTURE/query"
printf '%s\\n' "$HEALTH_TEST_RESPONSE"
exit "$HEALTH_TEST_EXIT"
""", encoding="utf-8", newline="\n")
    executable.chmod(0o700)
    def run(response="t", exit_code=0, **overrides):
        environment = {k: v for k, v in os.environ.items()
                       if not k.startswith(("AIRSPACE_", "POSTGRES_", "PG"))}
        environment.update(AIRSPACE_DB_APP_PASSWORD="isolated-health-password", POSTGRES_DB="airspace",
                           HEALTH_TEST_CAPTURE=shell_path(tmp_path), HEALTH_TEST_RESPONSE=response,
                           HEALTH_TEST_EXIT=str(exit_code))
        environment.update(overrides)
        result = subprocess.run([BASH, "--noprofile", "--norc", "-c",
                                 'export PATH="$1:$PATH"; exec /bin/sh "$2"',
                                 "health-test", shell_path(tmp_path), shell_path(SCRIPT)],
                                env=environment, capture_output=True, text=True, timeout=10)
        return result, tmp_path
    return run


def test_real_script_requires_authenticated_tcp_and_readonly_loaded_extensions(probe):
    result, capture = probe(PGHOST="operator.invalid", PGPORT="6543", PGUSER="operator",
                            PGDATABASE="operator-data", PGPASSWORD="operator-password")
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    arguments = (capture / "arguments").read_text()
    assert all(option in arguments for option in ["--host=127.0.0.1", "--port=5432", "--username=airspace",
                                                 "--dbname=airspace", "--no-password", "ON_ERROR_STOP=1", "-X"])
    assert "operator" not in arguments and "password" not in arguments.replace("--no-password", "")
    assert (capture / "password").read_text().strip() == "isolated-health-password"
    options = (capture / "options").read_text()
    assert "default_transaction_read_only=on" in options and "statement_timeout=1000" in options
    query = (capture / "query").read_text()
    assert "public.postgis_lib_version()" in query and "public.vector_dims('[0]'::public.vector)" in query
    assert all(flag in query for flag in ["rolcanlogin", "NOT rolsuper", "NOT rolcreatedb", "NOT rolcreaterole",
                                         "NOT rolreplication", "NOT rolbypassrls", "'CONNECT'", "'USAGE'", "'CREATE'"])
    assert "isolated-health-password" not in result.stdout + result.stderr + arguments + query


@pytest.mark.parametrize("response", ["f", "", "t\nf", "BEGIN\nt\nCOMMIT", "not-ready"])
def test_zero_exit_false_empty_or_extra_results_never_mean_ready(probe, response):
    result, _ = probe(response=response)
    assert result.returncode != 0


@pytest.mark.parametrize("exit_code", [1, 2, 127])
def test_authentication_missing_extension_or_client_failure_fails_closed(probe, exit_code):
    result, _ = probe(response="t", exit_code=exit_code)
    assert result.returncode != 0


@pytest.mark.parametrize("database", ["postgresql://user:secret@operator/db", "host=operator", ""])
def test_connection_string_database_override_cannot_access_an_operator_host(probe, database):
    result, capture = probe(POSTGRES_DB=database)
    assert result.returncode != 0
    assert not (capture / "arguments").exists()
