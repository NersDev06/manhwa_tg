"""Run the publisher under the current macOS user's launchd, with local logs.
No credentials are copied into the plist. .env is loaded by the worker itself.
Stop this service before enabling the Heroku worker.
"""
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'local.manhwa-telegram.worker'
DOMAIN = f'gui/{os.getuid()}'
TARGET = DOMAIN + '/' + LABEL
RUNTIME = ROOT / 'tmp' / 'local-worker'
PLIST = RUNTIME / 'worker.plist'


def run(*args):
    return subprocess.run(['launchctl', *args], capture_output=True, text=True)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if action == 'start':
        if run('print', TARGET).returncode == 0:
            print('Local worker already loaded'); return
        RUNTIME.mkdir(parents=True, exist_ok=True)
        python = ROOT / '.venv' / 'bin' / 'python'
        if not python.exists():
            raise RuntimeError('Project virtual environment is missing')
        with PLIST.open('wb') as out:
            plistlib.dump({'Label': LABEL,
                'ProgramArguments': ['/usr/bin/caffeinate', '-i', str(python), '-u', '-m', 'manhwa', 'worker'],
                'WorkingDirectory': str(ROOT), 'RunAtLoad': True,
                'KeepAlive': True, 'ThrottleInterval': 30, 'ExitTimeOut': 240,
                'StandardOutPath': str(RUNTIME / 'worker.log'),
                'StandardErrorPath': str(RUNTIME / 'worker.log'),
                'EnvironmentVariables': {'PYTHONUNBUFFERED': '1'}}, out)
        PLIST.chmod(0o600)
        result = run('bootstrap', DOMAIN, str(PLIST))
        if result.returncode:
            raise RuntimeError('Unable to load local worker: ' + result.stderr.strip())
        print('Local worker loaded; log:', RUNTIME / 'worker.log')
    elif action == 'stop':
        result = run('bootout', TARGET)
        if result.returncode and run('print', TARGET).returncode == 0:
            raise RuntimeError('Unable to stop local worker')
        print('Local worker stopped')
    elif action == 'status':
        result = run('print', TARGET)
        if result.returncode:
            print('Local worker is not loaded'); return
        for line in result.stdout.splitlines():
            if any(key in line for key in ['state =', 'pid =', 'last exit code =', 'runs =']):
                print(line.strip())
    else:
        raise ValueError('Use start, stop or status')


if __name__ == '__main__':
    main()
