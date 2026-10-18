import logging
import re
import signal
import tempfile
import threading
from pathlib import Path

from .pdf import build_chapter
from .store import now
from .telegram import DeliveryRejected, DeliveryUnknown

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, store, source, telegram, poll_seconds=1800, admin=None, daily_limit=10):
        self.store, self.source, self.telegram = store, source, telegram
        self.poll_seconds, self.admin = poll_seconds, admin
        self.daily_limit = daily_limit
        self.stop = threading.Event()
        self.heartbeat_stop = threading.Event()
        self.lease_ok = threading.Event()
        self.lease_ok.set()

    def heartbeat(self):
        while not self.heartbeat_stop.wait(20):
            try:
                if self.store.renew():
                    continue
            except Exception:
                pass
            self.lease_ok.clear()
            self.stop.set()
            return

    def discover(self):
        for sub in self.store.subs.find({'enabled': True}):
            if sub.get('checked') and (now() - sub['checked'].replace(tzinfo=now().tzinfo)).total_seconds() < self.poll_seconds:
                continue
            try:
                title, chapters = self.source.chapters(sub['url'])
                if not self.lease_ok.is_set():
                    return
                self.store.sync(sub, title, chapters)
                log.info('Checked subscription %s: %s chapters', sub['_id'], len(chapters))
            except Exception as exc:
                # Do not log exception strings: HTTP errors may include credentials.
                kind = type(exc).__name__
                self.store.subs.update_one({'_id': sub['_id']}, {'$set': {'checked': now(), 'error': kind}})
                if not sub.get('error'):
                    self.telegram.alert(self.admin, f"Ошибка источника для {sub['_id']}: {kind}")
                log.warning('Source check failed for %s (%s)', sub['_id'], kind)

    def process(self, job):
        sending = False
        sent = list(job.get('sent_parts', []))
        try:
            with tempfile.TemporaryDirectory(prefix='manhwa-') as folder:
                paths, stats = build_chapter(self.source, job['chapter_url'], Path(folder))
                self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'pdf_stats': stats}})
                for index, path in enumerate(paths):
                    if index < len(sent):
                        continue
                    if not self.lease_ok.is_set() or self.stop.is_set() or not self.store.renew():
                        raise RuntimeError('Worker stopping before upload')
                    self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sending'}})
                    sending = True
                    title = job['title']
                    part = f' · Часть {index + 1}/{len(paths)}' if len(paths) > 1 else ''
                    filename = re.sub(r'[^\w .-]', '_', f"{title} - {job['name']}")[:140]
                    receipt = self.telegram.document(job['channel'], path,
                        f"{title}\n{job['name']}{part}", f'{filename}-{index + 1}.pdf')
                    sent.append(receipt)
                    self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'sent_parts': sent}})
                    sending = False
                self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sent', 'sent_at': now(), 'error': None}})
                log.info('Published job %s (%s PDF pages)', job['_id'], stats['pdf_pages'])
        except Exception as exc:
            uncertain = isinstance(exc, DeliveryUnknown) or (sending and not isinstance(exc, DeliveryRejected))
            status = self.store.fail(job, type(exc).__name__, uncertain=uncertain)
            if isinstance(exc, DeliveryRejected) and exc.retry_after:
                from datetime import timedelta
                self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'retry_at': now() + timedelta(seconds=exc.retry_after + 5)}})
            if status in ('failed', 'uncertain'):
                self.telegram.alert(self.admin, f"Нужна проверка главы {job['name']}: {status}. ID: {job['_id']}")
            log.warning('Job %s: %s (%s)', job['_id'], status, type(exc).__name__)

    def run(self):
        if not self.store.acquire():
            raise RuntimeError('Another worker holds the lease')
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: self.stop.set())
        beat = threading.Thread(target=self.heartbeat, daemon=True)
        beat.start()
        try:
            self.store.recover()
            while not self.stop.is_set():
                self.discover()
                if not self.lease_ok.is_set():
                    break
                job = self.store.claim(self.daily_limit)
                if job:
                    self.process(job)
                    self.stop.wait(60)
                else:
                    self.stop.wait(10)
        finally:
            self.stop.set()
            self.heartbeat_stop.set()
            beat.join(timeout=25)
            self.store.release()
