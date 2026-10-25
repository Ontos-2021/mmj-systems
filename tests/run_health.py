#!/usr/bin/env python3
"""Build the candidate web image locally and run the health tests against it.

Disposable local Docker only (default context). Serializes builds with the
shared lock used by the other Coolify health worktrees.
"""
import fcntl
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = Path('/home/ontos/.hermes/cache/scratch/coolify-health-build.lock')
IMAGE = 'local/mmj-web-health:check'


def main():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        build = subprocess.run(['docker', 'build', '-q', '-t', IMAGE, str(ROOT)],
                               capture_output=True, text=True, timeout=900)
    if build.returncode:
        print(build.stdout, build.stderr, file=sys.stderr)
        return build.returncode
    env = dict(os.environ, MMJ_WEB_TEST_IMAGE=IMAGE)
    os.environ.update(env)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent),
                                                pattern='test_health.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
