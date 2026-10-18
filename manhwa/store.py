from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import uuid
from zoneinfo import ZoneInfo

from bson.decimal128 import Decimal128
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, BulkWriteError


def now():
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, db):
        self.db = db
        self.jobs = db.jobs
        self.subs = db.subscriptions
        self.owner = uuid.uuid4().hex

    def indexes(self):
        self.subs.create_index([('url', ASCENDING), ('channel', ASCENDING)], unique=True)
        self.jobs.create_index([('subscription', 1), ('chapter_url', 1)], unique=True)
        self.jobs.create_index([('subscription', 1), ('volume', 1), ('number', 1)])
        self.db.outbox.create_index([('kind', 1), ('status', 1), ('created', 1)])

    def acquire(self):
        try:
            result = self.db.locks.find_one_and_update(
                {'_id': 'worker', '$or': [{'expires': {'$lt': now()}}, {'owner': self.owner}]},
                {'$set': {'owner': self.owner, 'expires': now() + timedelta(seconds=90)}},
                upsert=True, return_document=ReturnDocument.AFTER)
            return result is not None
        except DuplicateKeyError:
            return False

    def renew(self):
        return self.db.locks.update_one(
            {'_id': 'worker', 'owner': self.owner, 'expires': {'$gt': now()}},
            {'$set': {'expires': now() + timedelta(seconds=90)}}).matched_count == 1

    def release(self):
        self.db.locks.delete_one({'_id': 'worker', 'owner': self.owner})

    def recover(self):
        self.jobs.update_many({'status': 'processing'}, {'$set': {'status': 'pending'}})
        self.jobs.update_many({'status': 'sending'}, {'$set': {'status': 'uncertain',
            'error': 'Worker stopped during Telegram delivery; check channel before resolving'}})

    def add(self, url, channel, mode, start=None):
        if mode == 'archive' and start is None:
            raise ValueError('Archive mode requires --start chapter number')
        if start is not None:
            Decimal(start)
        key = hashlib.sha256((url + '\n' + channel).encode()).hexdigest()[:20]
        self.subs.insert_one({'_id': key, 'url': url, 'channel': channel, 'mode': mode,
            'start': start, 'enabled': True, 'initialized': False, 'created': now()})
        return key

    def sync(self, sub, title, chapters):
        baseline = not sub['initialized'] and sub['mode'] == 'new'
        existing = {j['chapter_url'] for j in self.jobs.find({'subscription': sub['_id']}, {'chapter_url': 1})}
        additions = []
        for chapter in chapters:
            if chapter.url in existing or (sub['start'] is not None and Decimal(chapter.number) < Decimal(sub['start'])):
                continue
            existing.add(chapter.url)
            additions.append({'subscription': sub['_id'], 'chapter_url': chapter.url,
                'title': title, 'name': chapter.name, 'volume': int(chapter.volume),
                'number': Decimal128(chapter.number), 'channel': sub['channel'],
                'status': 'baseline' if baseline else 'pending',
                'attempts': 0, 'sent_parts': [], 'created': now()})
        if additions:
            try:
                self.jobs.insert_many(additions, ordered=False)
            except BulkWriteError as exc:
                if exc.details.get('writeConcernErrors') or any(e['code'] != 11000 for e in exc.details.get('writeErrors', [])):
                    raise
        self.subs.update_one({'_id': sub['_id']}, {'$set': {
            'initialized': True, 'title': title, 'checked': now(), 'error': None}})

    def claim(self, daily_limit=0):
        day = now().astimezone(ZoneInfo("Asia/Bishkek")).date().isoformat()
        # An unresolved earlier chapter blocks later chapters of the same title.
        for sub in self.subs.find({'enabled': True}).sort('last_processed', 1):
            job = self.jobs.find_one({'subscription': sub['_id'],
                'status': {'$nin': ['sent', 'baseline', 'skipped']}}, sort=[('volume', 1), ('number', 1), ('chapter_url', 1)])
            if job is None or job['status'] != 'pending':
                continue
            due = job.get('retry_at')
            if due and due.replace(tzinfo=timezone.utc) > now():
                continue
            if daily_limit > 0 and job.get('quota_day') != day:
                quota_key = day + ':' + sub['channel']
                self.db.daily_quota.update_one({'_id': quota_key}, {'$setOnInsert': {'count': 0}}, upsert=True)
                reserved = self.db.daily_quota.find_one_and_update(
                    {'_id': quota_key, 'count': {'$lt': daily_limit}}, {'$inc': {'count': 1}})
                if reserved is None:
                    continue
                # Reserve first: a crash can lose one slot but cannot exceed the cap.
                self.jobs.update_one({'_id': job['_id']}, {'$set': {'quota_day': day}})
            result = self.jobs.find_one_and_update({'_id': job['_id'], 'status': 'pending'},
                {'$set': {'status': 'processing', 'started': now()}, '$inc': {'attempts': 1}},
                return_document=ReturnDocument.AFTER)
            if result:
                self.subs.update_one({'_id': sub['_id']}, {'$set': {'last_processed': now()}})
                return result
        return None

    def fail(self, job, error, uncertain=False):
        status = 'uncertain' if uncertain else 'failed' if job['attempts'] >= 5 else 'pending'
        self.jobs.update_one({'_id': job['_id']}, {'$set': {'status': status,
            'error': error[:500], 'retry_at': now() + timedelta(seconds=min(3600, 60 * 2 ** job['attempts']))}})
        return status
