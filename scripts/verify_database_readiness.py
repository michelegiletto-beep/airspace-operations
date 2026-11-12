"""Actual isolated CI regression: partial initialization must remain unhealthy.

Reuses the built database image, creates a unique database-only project without
published ports, injects an initial SQL failure before application-role creation,
and removes only that generated project's resources. No operator paths, models,
application records, service permission changes or credential output are used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PROJECT = re.compile(r'[a-z0-9][a-z0-9_-]{0,62}\Z')
IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')
CONTAINER = re.compile(r'[0-9a-f]{12,64}\Z')
DEADLINE_SECONDS = 180


def main() -> int:
    environment = dict(os.environ)
    parent = environment.get('COMPOSE_PROJECT_NAME', '')
    run_id = environment.get('GITHUB_RUN_ID', '')
    # Prevent accidental execution against the desktop or an operator deployment.
    if (environment.get('GITHUB_ACTIONS') != 'true' or sys.platform != 'linux'
            or not PROJECT.fullmatch(parent) or not re.fullmatch(r'[0-9]{1,20}', run_id)):
        print(json.dumps({'success': False, 'error': 'Isolated Linux GitHub CI environment required'}))
        return 1
    project = 'airspace-abi-negative-' + run_id + '-' + uuid4().hex[:8]
    assert PROJECT.fullmatch(project) and project != parent
    fixture = (ROOT/'tests/fixtures/postgres-init-fail.sql').resolve()
    assert fixture.is_file() and fixture.is_relative_to(ROOT.resolve())
    started = time.monotonic()
    report = {'scope': 'Actual database-only partial-init negative regression',
              'project': project, 'success': False, 'no_published_ports': False,
              'application_records_created': 0, 'model_calls': 0, 'checks': []}
    owned = False
    compose = ['docker', 'compose', '--project-name', project,
               '-f', 'compose.yaml', '-f', 'deploy/compose.readiness-test.yaml']

    def run(label, arguments, *, required=True, child_env=None, cleanup=False):
        remaining = DEADLINE_SECONDS - (time.monotonic() - started)
        if remaining <= 0 and not cleanup:
            raise TimeoutError('Regression deadline exceeded')
        timeout = 20 if cleanup else max(1, min(15, remaining))
        result = subprocess.run(arguments, cwd=ROOT,
                                env=environment if child_env is None else child_env,
                                capture_output=True, text=True, timeout=timeout,
                                shell=False, check=False)
        # Output may contain credentials: retain only fixed labels/exit codes.
        report['checks'].append({'check': label, 'exit_code': result.returncode})
        if required and result.returncode:
            raise RuntimeError(label + ' failed')
        return result

    def inspect(container):
        result = run('inspect isolated database state', ['docker', 'inspect', '--format',
                     '{"state":{{json .State}},"restart_count":{{json .RestartCount}},"ports":{{json .HostConfig.PortBindings}},"health_test":{{json .Config.Healthcheck.Test}}}', container])
        return json.loads(result.stdout)

    def query(container, sql):
        # The password is passed only through the child's environment, never argv.
        child_env = dict(environment, PGPASSWORD=environment['POSTGRES_PASSWORD'])
        return run('read-only administrator readiness query',
                   ['docker', 'exec', '-e', 'PGPASSWORD', container, 'psql',
                    '-h', '127.0.0.1', '-U', 'airspace_admin', '-d', 'airspace',
                    '-v', 'ON_ERROR_STOP=1', '-Atqc', sql], child_env=child_env)

    try:
        image = run('identify already built database image', ['docker', 'image', 'inspect',
                    '--format', '{{.Id}}', parent + '-database']).stdout.strip()
        assert IMAGE.fullmatch(image), 'Built image identity is invalid'
        environment['AIRSPACE_READINESS_IMAGE'] = image
        environment['AIRSPACE_READINESS_FAILURE_SQL'] = str(fixture)
        report['built_database_image'] = image
        for kind, command in [('containers', ['docker', 'ps', '--all', '--quiet']),
                              ('volumes', ['docker', 'volume', 'ls', '--quiet']),
                              ('networks', ['docker', 'network', 'ls', '--quiet'])]:
            result = run('refuse existing generated-project ' + kind,
                         command + ['--filter', 'label=com.docker.compose.project=' + project])
            assert not result.stdout.strip(), 'Generated project already has resources'
        owned = True
        run('start isolated database without building or pulling',
            compose + ['up', '--detach', '--no-build', '--pull', 'never', 'database'])
        identifiers = run('identify isolated database', compose + ['ps', '--all', '--quiet', 'database']).stdout.split()
        assert len(identifiers) == 1 and CONTAINER.fullmatch(identifiers[0])
        container = identifiers[0]
        # Deliberately failed init must restart with PGDATA present. Merely being
        # TCP-ready after that restart must not admit dependent application work.
        while True:
            state = inspect(container)
            assert not state['ports'], 'Negative regression published a host port'
            ready = run('probe final TCP accepting connections', ['docker', 'exec', container,
                        'pg_isready', '-h', '127.0.0.1', '-U', 'airspace_admin', '-d', 'airspace'], required=False)
            if state['restart_count'] >= 1 and state['state']['Running'] and ready.returncode == 0:
                break
            if time.monotonic() - started >= DEADLINE_SECONDS:
                raise TimeoutError('Partial-init restart did not become TCP-ready')
            time.sleep(1)
        absent = query(container, "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='airspace'), EXISTS(SELECT 1 FROM pg_extension WHERE extname='postgis'), EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector');")
        assert absent.stdout.strip() == 'f|f|f', 'Fault fixture did not leave the expected missing role/extensions'
        health_test = state['health_test']
        assert isinstance(health_test, list) and len(health_test) >= 2
        if health_test[0] == 'CMD':
            health_arguments = health_test[1:]
        elif health_test[0] == 'CMD-SHELL' and len(health_test) == 2:
            health_arguments = ['/bin/sh', '-c', health_test[1]]
        else:
            raise RuntimeError('Unsupported production healthcheck form')
        probe = run('exact production health rejects partial init',
                    ['docker', 'exec', container] + health_arguments, required=False)
        assert probe.returncode != 0, 'Production health accepted missing extensions/application role'
        after = inspect(container)
        assert after['state'].get('Health', {}).get('Status') != 'healthy', 'Docker reports partially initialized database healthy'
        report.update(success=True, no_published_ports=True,
                      initial_sql_failure_injected=True, database_restart_count=after['restart_count'],
                      final_tcp_accepting=True, application_role_absent=True,
                      required_extensions_absent=True, exact_health_exit=probe.returncode,
                      docker_health_status=after['state'].get('Health', {}).get('Status'),
                      source_of_health_command='Actual isolated container Config.Healthcheck.Test')
    except Exception as error:
        # Exception text/subprocess output may expose credentials; print only type.
        report['error_type'] = type(error).__name__
    finally:
        if owned:
            try:
                assert project.startswith('airspace-abi-negative-') and project != parent
                result = run('cleanup only generated negative-test project',
                             compose + ['down', '--volumes', '--remove-orphans', '--timeout', '10'],
                             required=False, cleanup=True)
                report['cleanup_exit'] = result.returncode
                if result.returncode:
                    report['success'] = False
            except Exception as error:
                report['cleanup_error_type'] = type(error).__name__
                report['success'] = False
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
