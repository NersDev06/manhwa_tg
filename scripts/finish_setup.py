"""Run after the owner saves MONGODB_URI in .env; never print secrets."""
import os
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values
from pymongo import MongoClient
import certifi

ROOT = Path(__file__).resolve().parent.parent
APP = 'manhwa-publisher-20261018'


def run(args, show=False):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(args[:2]))
    if show:
        print(result.stdout.strip())


def main():
    env = dotenv_values(ROOT / '.env')
    uri = env.get('MONGODB_URI')
    if not uri:
        raise ValueError('Owner must save MONGODB_URI in .env first')
    with MongoClient(uri, serverSelectionTimeoutMS=15000, tlsCAFile=certifi.where()) as client:
        client.admin.command('ping')
    print('MongoDB connection verified')
    run(['heroku', 'ps:scale', 'worker=0', '--app', APP])
    values = {k: env[k] for k in ['MONGODB_URI', 'MONGODB_DATABASE', 'TELEGRAM_BOT_TOKEN',
                                 'POLL_SECONDS', 'DAILY_CHAPTER_LIMIT'] if env.get(k)}
    run(['heroku', 'config:set', '--app', APP] + [k + '=' + v for k, v in values.items()])
    print('Heroku configuration saved')
    run(['heroku', 'run', '--no-tty', '--exit-code', '--size', 'basic', '--app', APP,
         'python -m manhwa configure'], show=True)
    run(['heroku', 'ps:scale', 'worker=1:basic', '--app', APP], show=True)
    run(['heroku', 'ps', '--app', APP], show=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Setup stopped:', type(exc).__name__, '(check account access and configuration)', file=sys.stderr)
        raise SystemExit(1)
