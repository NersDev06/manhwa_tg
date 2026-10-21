import logging
import os
import re
import signal
import threading
import time

from . import spool
from .preview import from_cached_pages
from .store import now
from bson.decimal128 import Decimal128
from .seo import chapter_caption, public_metadata
from . import promotions
from .channel_setup import refresh_navigation
from .telegram import DeliveryRejected, DeliveryUnknown

log = logging.getLogger(__name__)


class WorkerStopping(Exception):
    pass


class Worker:
    def __init__(self, store, source, telegram, poll_seconds=3600, admin=None, daily_limit=0, chapter_delay=10):
        self.store, self.source, self.telegram = store, source, telegram
        if hasattr(source, "bind"):
            source.bind(store)
        self.poll_seconds, self.admin = poll_seconds, admin
        self.daily_limit = daily_limit
        self.chapter_delay = max(1, int(chapter_delay))
        self.stop = threading.Event()
        self.heartbeat_stop = threading.Event()
        self.lease_ok = threading.Event()
        self.lease_ok.set()

    def state(self, **fields):
        self.store.db.runtime.update_one({'_id': 'worker_state'}, {'$set': {**fields, 'updated': now()}}, upsert=True)

    def metrics(self):
        import resource, sys
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        self.state(peak_memory_mb=round(rss / (1024 ** 2 if sys.platform == 'darwin' else 1024), 1))
        try:
            stats = self.store.db.command('dbStats')
            self.state(database_bytes=stats.get('dataSize', 0) + stats.get('indexSize', 0))
        except Exception:
            pass
        for sub in self.store.subs.find({'enabled': True}):
            try:
                chat = self.telegram.call('getChat', {'chat_id': sub['channel']})
                count = self.telegram.call('getChatMemberCount', {'chat_id': sub['channel']})
                self.store.subs.update_one({'_id': sub['_id']}, {'$set': {'telegram_stats': {
                    'subscribers': count, 'linked_chat_id': chat.get('linked_chat_id'),
                    'username': chat.get('username'), 'updated': now()}}})
            except Exception as exc:
                log.warning('Channel metrics unavailable (%s)', type(exc).__name__)

    def heartbeat(self):
        while not self.heartbeat_stop.wait(20):
            try:
                if self.store.renew():
                    self.state(heartbeat=now())
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
                # Only source-side failures are re-armed after a successful discovery.
                # Unknown Telegram deliveries must never be automatically repeated.
                available = [Decimal128(c.number) for c in chapters]
                self.store.jobs.update_many({'subscription': sub['_id'], 'status': 'failed',
                    'error_type': {'$in': ['HTTPError', 'ConnectTimeout', 'ReadTimeout', 'ConnectionError', 'Timeout', 'RetryError', 'SourceError']},
                    'number': {'$in': available}}, {'$set': {'status': 'pending', 'attempts': 0, 'retry_at': now(), 'error': None}})
                if hasattr(self.source, 'metadata'):
                    meta = self.source.metadata(sub['url'])
                    if sub.get('main_title_override'):
                        if meta['main_title_ru'] != sub['main_title_override']:
                            meta['alt_titles_ru'] = list(dict.fromkeys([meta['main_title_ru']] + meta['alt_titles_ru']))
                        meta['main_title_ru'] = sub['main_title_override']
                    meta = public_metadata(meta, sub['_id'])
                    self.store.subs.update_one({'_id': sub['_id']}, {'$set': {'metadata': meta}})
                log.info('Checked subscription %s: %s chapters', sub['_id'], len(chapters))
            except Exception as exc:
                # Do not log exception strings: HTTP errors may include credentials.
                kind = type(exc).__name__
                self.store.subs.update_one({'_id': sub['_id']}, {'$set': {'checked': now(), 'error': kind}})
                if not sub.get('error'):
                    self.telegram.alert(self.admin, f"Ошибка источника для {sub['_id']}: {kind}")
                log.warning('Source check failed for %s (%s)', sub['_id'], kind)

    def check_delivery_lease(self):
        if self.stop.is_set() or not self.lease_ok.is_set():
            raise WorkerStopping()
        if not self.store.renew():
            self.lease_ok.clear()
            self.stop.set()
            raise WorkerStopping()

    def seed_reaction(self, job, message_id):
        if self.stop.is_set() or not self.lease_ok.is_set():
            return
        try:
            if self.telegram.react(job['channel'], message_id):
                self.store.jobs.update_one({'_id': job['_id']},
                    {'$addToSet': {'reaction_seeded': message_id}})
            else:
                log.warning('Free reaction unavailable for message %s', message_id)
        except Exception:
            # The original message is already confirmed; reaction errors are optional.
            log.warning('Free reaction deferred for message %s', message_id)

    def process(self, job):
        sending = False
        confirmed = False
        self.state(stage='preparing', job=str(job['_id']), title=job['title'].split(' / ')[0], chapter=str(job['number']), page=0, pages=0, error=None)
        self.source.progress = lambda page, total: self.state(stage='preparing', page=page, pages=total)
        self.telegram.progress = lambda sent, total: self.state(upload_sent=sent, upload_total=total)
        sent = list(job.get('sent_parts', []))
        try:
            with spool.prepared(self.source, job) as (folder, (paths, stats)):
                self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'pdf_stats': stats}})
                if stats.get('source'):
                    self.store.subs.update_one({'_id': job['subscription']}, {'$set': {'active_source': stats['source']}})
                meta = (self.store.subs.find_one({'_id': job['subscription']}) or {}).get('metadata') or {'main_title_ru': job['title'].split(' / ')[0]}
                if not job.get('preview_receipt') and not sent:
                    preview = from_cached_pages(folder)
                    self.check_delivery_lease()
                    self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sending', 'delivery_phase': 'preview'}})
                    sending = True
                    photo = self.telegram.photo(job['channel'], preview,
                        f"📖 {meta['main_title_ru']} — Глава {job['number']}\nПревью главы")
                    receipt = {'message_id': photo['message_id']}
                    self.store.jobs.update_one({'_id': job['_id']}, {'$set': {
                        'preview_receipt': receipt, 'status': 'processing', 'delivery_phase': 'pdf'}})
                    sending = False
                    self.seed_reaction(job, photo['message_id'])

                for index, path in enumerate(paths):
                    if index < len(sent):
                        continue
                    self.check_delivery_lease()
                    self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sending'}})
                    sending = True
                    self.state(stage='uploading', part=index + 1, parts=len(paths), upload_bytes=path.stat().st_size, upload_sent=0, upload_total=path.stat().st_size)
                    title = job['title']
                    part = f' · Часть {index + 1}/{len(paths)}' if len(paths) > 1 else ''
                    filename = re.sub(r'[^\w .-]', '_', meta['main_title_ru'])[:100] + ' - Глава ' + str(job['number'])
                    filename += f' - Часть {index + 1}' if len(paths) > 1 else ''
                    receipt = self.telegram.document(job['channel'], path,
                        chapter_caption(meta, str(job['number']), part), f'{filename}.pdf')
                    sent.append(receipt)
                    self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'sent_parts': sent}})
                    sending = False
                    self.seed_reaction(job, receipt['message_id'])
                self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sent', 'sent_at': now(), 'error': None}})
                confirmed = True
                spool.clean(job)
                self.state(stage='idle', job=None)
                self.store.event('published', job['subscription'], job['_id'], number=str(job['number']), source=stats.get('source'), pages=stats['pdf_pages'])
                log.info('Published job %s (%s PDF pages)', job['_id'], stats['pdf_pages'])
        except WorkerStopping:
            if self.lease_ok.is_set():
                self.store.jobs.update_one({'_id': job['_id'], 'status': 'processing'},
                    {'$set': {'status': 'pending', 'retry_at': now()}, '$inc': {'attempts': -1}})
            self.state(stage='stopping', job=None)
        except Exception as exc:
            if confirmed:
                log.warning('Post-delivery maintenance deferred (%s)', type(exc).__name__)
                return
            uncertain = isinstance(exc, DeliveryUnknown) or (sending and not isinstance(exc, DeliveryRejected))
            kind = type(exc).__name__
            detail = str(exc)[:350] if isinstance(exc, (ValueError, RuntimeError)) else kind
            self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'error_type': kind}})
            status = self.store.fail(job, detail, uncertain=uncertain,
                retryable=isinstance(exc, DeliveryRejected) and exc.code in (408, 429))
            self.store.event('delivery_uncertain' if uncertain else 'job_failed', job['subscription'], job['_id'], number=str(job['number']), error_type=kind, status=status)
            self.state(stage='error', error=detail, job=str(job['_id']))
            if isinstance(exc, DeliveryRejected) and exc.retry_after:
                from datetime import timedelta
                self.store.db.runtime.update_one({'_id': 'telegram'}, {'$max': {'not_before': now() + timedelta(seconds=exc.retry_after + 5)}}, upsert=True)
                self.store.jobs.update_one({'_id': job['_id']}, {'$set': {'retry_at': now() + timedelta(seconds=exc.retry_after + 5)}})
            if status in ('failed', 'uncertain'):
                self.telegram.alert(self.admin, f"Нужна проверка главы {job['name']}: {status}. ID: {job['_id']}")
            log.warning('Job %s: %s (%s)', job['_id'], status, type(exc).__name__)

    def acquire_lease(self, timeout=120):
        # Heroku can start the replacement before the old dyno finishes stopping.
        # Wait for its release/expiry; never override a live worker's ownership.
        deadline = time.monotonic() + timeout
        waiting = False
        while not self.stop.is_set():
            if self.store.acquire():
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Another worker still holds the lease')
            if not waiting:
                log.info('Waiting for previous worker to release its lease')
                waiting = True
            self.stop.wait(min(5, remaining))
        return False

    def run(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: self.stop.set())
        if not self.acquire_lease():
            return
        beat = threading.Thread(target=self.heartbeat, daemon=True)
        beat.start()
        try:
            self.store.recover()
            self.state(stage='starting', host='heroku' if os.environ.get('DYNO') else 'local', chapter_delay=self.chapter_delay, poll_seconds=self.poll_seconds, heartbeat=now())
            self.store.event('worker_started')
            metrics_at = 0
            promotions.recover(self.store)
            while not self.stop.is_set():
                import time
                if time.monotonic() - metrics_at > 300:
                    self.metrics()
                    metrics_at = time.monotonic()
                self.discover()
                if self.stop.is_set() or not self.lease_ok.is_set():
                    break
                control = self.store.db.runtime.find_one({'_id': 'publisher_control'}) or {}
                if control.get('paused'):
                    self.state(stage='paused', job=None)
                    self.stop.wait(5)
                    continue
                cooldown = self.store.db.runtime.find_one({'_id': 'telegram'}) or {}
                until = cooldown.get('not_before')
                if until and until.replace(tzinfo=now().tzinfo) > now():
                    self.stop.wait(10)
                    continue
                try:
                    refresh_navigation(self.store, self.telegram)
                except Exception as exc:
                    log.warning('Navigator refresh deferred (%s)', type(exc).__name__)
                    if isinstance(exc, DeliveryRejected) and exc.retry_after:
                        from datetime import timedelta
                        self.store.db.runtime.update_one({'_id': 'telegram'}, {'$max': {'not_before': now() + timedelta(seconds=exc.retry_after + 5)}}, upsert=True)
                        continue
                promotions.prepare(self.store)
                if self.store.renew():
                    promotions.deliver_one(self.store, self.telegram)
                else:
                    break
                cooldown = self.store.db.runtime.find_one({'_id': 'telegram'}) or {}
                if cooldown.get('not_before') and cooldown['not_before'].replace(tzinfo=now().tzinfo) > now():
                    continue
                if self.stop.is_set() or (self.store.db.runtime.find_one({'_id': 'publisher_control'}) or {}).get('paused'):
                    continue
                job = self.store.claim(self.daily_limit)
                if job:
                    self.process(job)
                    self.stop.wait(self.chapter_delay)
                else:
                    self.state(stage='idle', job=None)
                    self.stop.wait(10)
        finally:
            self.stop.set()
            self.heartbeat_stop.set()
            beat.join(timeout=25)
            if self.lease_ok.is_set():
                self.state(stage='stopped', job=None)
                self.store.event('worker_stopped')
            self.store.release()
