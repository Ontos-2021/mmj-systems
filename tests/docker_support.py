"""Disposable, no-network/no-published-port image test helpers."""
from contextlib import contextmanager
import json
import os
import subprocess
import time
import uuid


def docker(*args, check=True):
    result = subprocess.run(['docker', *args], capture_output=True, text=True,
                            timeout=35, check=False)
    if check and result.returncode:
        raise AssertionError(f'docker {args!r} failed ({result.returncode}): '
                             f'{result.stdout}{result.stderr}')
    return result


def require_local_docker():
    if os.environ.get('DOCKER_HOST') or os.environ.get('DOCKER_CONTEXT'):
        raise RuntimeError('Health tests require the default local Docker context')
    context = docker('context', 'show').stdout.strip()
    endpoint = docker('context', 'inspect', context, '--format',
                      '{{.Endpoints.docker.Host}}').stdout.strip()
    if context != 'default' or endpoint != 'unix:///var/run/docker.sock':
        raise RuntimeError('Health tests refuse a non-default/non-local Docker daemon')


def image_config(image):
    return json.loads(docker('image', 'inspect', image).stdout)[0]['Config']


@contextmanager
def container(image, *, environment=None, user=None, entrypoint=None, command=()):
    require_local_docker()
    name = 'mmj-health-test-' + uuid.uuid4().hex
    args = ['run', '-d', '--name', name, '--label', 'mmj.health-test=' + name,
            '--network', 'none', '--restart=no',
            '--tmpfs', '/data:rw,noexec,nosuid,mode=1777']
    for key, value in (environment or {}).items():
        args.extend(['--env', f'{key}={value}'])
    if user:
        args.extend(['--user', user])
    if entrypoint:
        args.extend(['--entrypoint', entrypoint])
    try:
        docker(*args, image, *command)
        yield name
    finally:
        # Exact random resource, including an image's possible anonymous volumes.
        cleanup = docker('rm', '-f', '-v', name, check=False)
        if cleanup.returncode and 'No such container' not in cleanup.stderr:
            raise AssertionError(f'Could not clean test container {name}: {cleanup.stderr}')
        remaining = docker('ps', '-a', '--filter', 'name=^/' + name + '$', '-q')
        if remaining.stdout.strip():
            raise AssertionError(f'Test container left behind: {name}')


def wait_http(name, *, api=False, port=8471):
    if api:
        command = ['python', '-c',
                   'import http.client; '
                   f'c=http.client.HTTPConnection("127.0.0.1", {port}, timeout=1); '
                   'c.request("GET", "/salud"); r=c.getresponse(); '
                   'assert r.status == 200; c.close()']
    else:
        command = ['curl', '-q', '--noproxy', '*', '--silent', '--fail',
                   '--max-time', '1', 'http://127.0.0.1/']
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = docker('exec', name, *command, check=False)
        if not result.returncode:
            return
        time.sleep(0.05)
    raise AssertionError('HTTP did not start: ' + docker('logs', name).stdout)


def probe(name, image, *, environment=None):
    test = image_config(image).get('Healthcheck', {}).get('Test', [])
    if not test or test[0] not in ('CMD', 'CMD-SHELL'):
        raise AssertionError('Final image has no executable HEALTHCHECK')
    command = test[1:] if test[0] == 'CMD' else ['sh', '-c', test[1]]
    args = ['exec']
    for key, value in (environment or {}).items():
        args.extend(['--env', f'{key}={value}'])
    return docker(*args, name, *command, check=False)
