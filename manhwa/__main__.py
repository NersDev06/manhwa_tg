import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

from .source import MangaShi
from .store import Store, now
from .telegram import Telegram


def database():
    uri = os.environ.get('MONGODB_URI')
    if not uri:
        raise ValueError('Set MONGODB_URI in .env or Heroku Config Vars')
    client = MongoClient(uri, serverSelectionTimeoutMS=15000, maxPoolSize=5, tz_aware=True)
    client.admin.command('ping')
    store = Store(client[os.environ.get('MONGODB_DATABASE', 'manhwa_telegram')])
    store.indexes()
    return store


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description='MangaShi channel publisher')
    commands = parser.add_subparsers(dest='command', required=True)
    search = commands.add_parser('search'); search.add_argument('query')
    listing = commands.add_parser('chapters'); listing.add_argument('url')
    preview = commands.add_parser('preview'); preview.add_argument('chapter_url')
    preview.add_argument('--output', default='output/pdf')
    add = commands.add_parser('add')
    add.add_argument('--url', required=True); add.add_argument('--channel', required=True)
    add.add_argument('--mode', choices=['new', 'archive'], default='new')
    add.add_argument('--start', help='Required for archive; inclusive chapter number across volumes')
    commands.add_parser('status'); commands.add_parser('worker')
    commands.add_parser('init-db')
    configure = commands.add_parser('configure')
    configure.add_argument('--file', default='config/channels.json')
    for name in ['pause', 'resume']:
        cmd = commands.add_parser(name); cmd.add_argument('subscription')
    check = commands.add_parser('check-channel'); check.add_argument('channel')
    resolve = commands.add_parser('resolve')
    resolve.add_argument('job'); resolve.add_argument('--action', choices=['retry', 'sent', 'skip'], required=True)
    resolve.add_argument('--checked-channel', action='store_true', required=True,
                         help='Confirm channel was checked manually for this job')
    args = parser.parse_args()
    source = MangaShi()
    if args.command == 'search':
        print(json.dumps(source.search(args.query), ensure_ascii=False, indent=2)); return
    if args.command == 'chapters':
        title, chapters = source.chapters(args.url)
        print(title)
        for c in chapters:
            print(c.volume, c.number, c.name, c.url)
        print(f'Total: {len(chapters)}'); return
    if args.command == 'preview':
        from .pdf import build_chapter
        with tempfile.TemporaryDirectory(prefix='manhwa-preview-') as folder:
            paths, stats = build_chapter(source, args.chapter_url, Path(folder))
            output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
            for p in paths:
                target = output / p.name
                shutil.copyfile(p, target)
                print(target.resolve())
            print(json.dumps(stats))
        return
    if args.command == 'check-channel':
        print(Telegram(os.environ.get('TELEGRAM_BOT_TOKEN')).check_channel(args.channel)); return
    store = database()
    if args.command == 'init-db':
        print('MongoDB connected; indexes ready')
    elif args.command == 'configure':
        from pymongo.errors import DuplicateKeyError
        from decimal import Decimal
        from zoneinfo import ZoneInfo
        from datetime import datetime
        items = json.loads(Path(args.file).read_text())
        telegram = Telegram(os.environ.get('TELEGRAM_BOT_TOKEN'))
        receipts_path = Path('config/bootstrap-receipts.json')
        receipts = json.loads(receipts_path.read_text()) if receipts_path.exists() else []
        for item in items:
            url = source.title_url(item['url'])
            telegram.check_channel(item['channel'])
            try:
                key = store.add(url, item['channel'], item['mode'], item['start'])
            except DuplicateKeyError:
                key = store.subs.find_one({'url': url, 'channel': item['channel']})['_id']
            sub = store.subs.find_one({'_id': key})
            title, chapters = source.chapters(url)
            store.sync(sub, title, chapters)
            for receipt in receipts:
                if receipt['channel'] != item['channel']:
                    continue
                store.jobs.update_one({'subscription': key, 'chapter_url': receipt['chapter_url']},
                    {'$set': {'status': 'sent', 'sent_parts': receipt['sent_parts'],
                              'sent_at': datetime.fromisoformat(receipt['sent_at'])}})
            print('Configured:', item['title'], key)
        # Restore today's consumed quota from the imported delivery records.
        day = now().astimezone(ZoneInfo('Asia/Bishkek')).date().isoformat()
        for channel in {item['channel'] for item in items}:
            consumed = store.jobs.count_documents({'channel': channel, 'status': 'sent',
                'sent_at': {'$gte': datetime.fromisoformat(day).replace(tzinfo=ZoneInfo('Asia/Bishkek'))}})
            store.db.daily_quota.update_one({'_id': day + ':' + channel}, {'$max': {'count': consumed}}, upsert=True)
    elif args.command == 'add':
        url = source.title_url(args.url)
        print(store.add(url, args.channel, args.mode, args.start))
    elif args.command == 'status':
        for sub in store.subs.find():
            print(sub['_id'], sub.get('title', sub['url']), sub['channel'],
                  'active' if sub['enabled'] else 'paused', sub.get('error') or '')
        print('Jobs:', list(store.jobs.aggregate([{'$group': {'_id': '$status', 'count': {'$sum': 1}}}])))
        for job in store.jobs.find({'status': {'$in': ['failed', 'uncertain']}}).limit(30):
            print('Needs attention:', job['_id'], job['name'], job['status'])
    elif args.command in ('pause', 'resume'):
        r = store.subs.update_one({'_id': args.subscription}, {'$set': {'enabled': args.command == 'resume'}})
        print('Updated:', r.matched_count)
    elif args.command == 'resolve':
        status = {'retry': 'pending', 'sent': 'sent', 'skip': 'skipped'}[args.action]
        r = store.jobs.update_one({'_id': ObjectId(args.job), 'status': {'$in': ['failed', 'uncertain']}},
            {'$set': {'status': status, 'retry_at': now(), 'attempts': 0, 'error': None}})
        print('Resolved:', r.matched_count)
    elif args.command == 'worker':
        from .worker import Worker
        Worker(store, source, Telegram(os.environ.get('TELEGRAM_BOT_TOKEN')),
               max(60, int(os.environ.get('POLL_SECONDS', '1800'))), os.environ.get('ADMIN_CHAT_ID'),
               max(1, int(os.environ.get('DAILY_CHAPTER_LIMIT', '10')))).run()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        main()
    except Exception as exc:
        # Never print raw connection strings or Telegram request URLs.
        logging.error('Command failed (%s). Check configuration and service availability.', type(exc).__name__)
        raise SystemExit(1)
