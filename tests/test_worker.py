from unittest.mock import Mock
from pathlib import Path
import mongomock
import pytest

from manhwa.store import Store
from manhwa.source import Chapter
from manhwa.worker import Worker
from manhwa.telegram import DeliveryUnknown, DeliveryRejected


def setup(monkeypatch, tmp_path):
    store = Store(mongomock.MongoClient().db)
    assert store.acquire()
    store.add('url', '@channel', 'archive', '1')
    store.sync(store.subs.find_one(), 'Test', [Chapter('chapter', 'Глава 1', '1', '1')])
    job = store.claim()
    path = tmp_path / 'test.pdf'; path.write_bytes(b'pdf')
    monkeypatch.setattr('manhwa.spool.build_chapter', lambda *a: ([path], {'pdf_pages': 1}))
    monkeypatch.setattr('manhwa.worker.from_cached_pages', lambda *a: path)
    telegram = Mock()
    telegram.photo.return_value = {'message_id': 122}
    return store, job, telegram, Worker(store, Mock(), telegram)


def test_ambiguous_upload_requires_manual_resolution(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.document.side_effect = DeliveryUnknown('timeout')
    worker.process(job)
    assert store.jobs.find_one() ['status'] == 'uncertain'
    assert store.claim() is None


def test_explicit_rejection_can_retry(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.document.side_effect = DeliveryRejected(429, retry_after=60)
    worker.process(job)
    assert store.jobs.find_one()['status'] == 'pending'
    assert store.jobs.find_one()['sent_parts'] == []


def test_success_persists_receipt(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.document.return_value = {'message_id': 123, 'file_id': 'test'}
    worker.process(job)
    saved = store.jobs.find_one()
    assert saved['status'] == 'sent'
    assert saved['sent_parts'][0]['message_id'] == 123


def test_unknown_preview_blocks_pdf(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.photo.side_effect = DeliveryUnknown('preview timeout')
    worker.process(job)
    assert store.jobs.find_one()['status'] == 'uncertain'
    telegram.document.assert_not_called()


def test_preview_is_not_repeated_on_pdf_retry(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.document.side_effect = DeliveryRejected(429, retry_after=60)
    worker.process(job)
    saved = store.jobs.find_one()
    assert saved['preview_receipt']['message_id'] == 122
    telegram.document.side_effect = None
    telegram.document.return_value = {'message_id':123,'file_id':'test'}
    worker.process(saved)
    assert telegram.photo.call_count == 1
    assert store.jobs.find_one()['status'] == 'sent'


def test_source_recovery_rearms_failures_but_not_unknown_deliveries(monkeypatch):
    from bson.decimal128 import Decimal128
    import mongomock.filtering
    original = mongomock.filtering.bson_compare
    def compare(op, a, b, can_compare_types=True):
        if isinstance(a, Decimal128): a = a.to_decimal()
        if isinstance(b, Decimal128): b = b.to_decimal()
        return original(op, a, b, can_compare_types)
    monkeypatch.setattr(mongomock.filtering, "bson_compare", compare)
    from types import SimpleNamespace
    store=Store(mongomock.MongoClient().db)
    store.add('url','channel','archive','1');sub=store.subs.find_one()
    chapters=[Chapter('one','Глава 1','1','1'),Chapter('two','Глава 2','1','2')]
    store.sync(sub,'title',chapters)
    store.jobs.update_one({'chapter_url':'one'},{'$set':{'status':'uncertain','error_type':'DeliveryUnknown'}})
    store.jobs.update_one({'chapter_url':'two'},{'$set':{'status':'failed','error_type':'HTTPError','attempts':5}})
    store.subs.update_one({'_id':sub['_id']},{'$unset':{'checked':''}})
    worker=Worker(store,SimpleNamespace(chapters=lambda url:('title',chapters)),Mock())
    worker.discover()
    assert store.jobs.find_one({'chapter_url':'one'})['status']=='uncertain'
    assert store.jobs.find_one({'chapter_url':'two'})['status']=='pending'
    assert store.claim() is None


def test_explicit_rate_limit_stays_retryable_after_five_attempts(monkeypatch,tmp_path):
    store,job,telegram,worker=setup(monkeypatch,tmp_path)
    job['attempts']=10
    telegram.document.side_effect=DeliveryRejected(429,retry_after=120)
    worker.process(job)
    assert store.jobs.find_one()['status']=='pending'
    assert store.jobs.find_one()['preview_receipt']['message_id']==122


def test_graceful_stop_preserves_pending_without_consuming_attempt(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    worker.stop.set()
    worker.process(job)
    saved = store.jobs.find_one()
    assert saved['status'] == 'pending'
    assert saved['attempts'] == 0
    telegram.photo.assert_not_called()
    telegram.document.assert_not_called()


def test_event_failure_does_not_requeue_confirmed_delivery(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.document.return_value = {'message_id': 123, 'file_id': 'test'}
    monkeypatch.setattr(store.db.events, 'insert_one', Mock(side_effect=RuntimeError('telemetry unavailable')))
    worker.process(job)
    assert store.jobs.find_one()['status'] == 'sent'
    assert len(store.jobs.find_one()['sent_parts']) == 1


def test_lost_lease_cannot_send_or_requeue_another_workers_job(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(store, 'renew', lambda: False)
    worker.process(job)
    assert not worker.lease_ok.is_set()
    assert store.jobs.find_one()['status'] == 'processing'
    telegram.photo.assert_not_called()
    telegram.document.assert_not_called()


def test_post_delivery_state_failure_keeps_confirmed_status(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.document.return_value = {'message_id': 123, 'file_id': 'test'}
    original = worker.state
    def state(**fields):
        if fields.get('stage') == 'idle':
            raise RuntimeError('metrics unavailable')
        original(**fields)
    worker.state = state
    worker.process(job)
    assert store.jobs.find_one()['status'] == 'sent'


def test_reaction_failure_does_not_republish_or_block_pdf(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.react.side_effect = RuntimeError('reaction unavailable')
    telegram.document.return_value = {'message_id': 123, 'file_id': 'test'}
    worker.process(job)
    assert store.jobs.find_one()['status'] == 'sent'
    assert telegram.photo.call_count == telegram.document.call_count == 1


def test_free_reaction_seeded_on_preview_and_document(monkeypatch, tmp_path):
    store, job, telegram, worker = setup(monkeypatch, tmp_path)
    telegram.react.return_value = True
    telegram.document.return_value = {'message_id': 123, 'file_id': 'test'}
    worker.process(job)
    assert store.jobs.find_one()['reaction_seeded'] == [122, 123]


def test_restart_waits_for_previous_worker_without_stealing_lease(monkeypatch):
    db = mongomock.MongoClient().db
    previous, replacement = Store(db), Store(db)
    assert previous.acquire()
    worker = Worker(replacement, Mock(), Mock())
    def finish_previous(_):
        assert db.locks.find_one({'_id': 'worker'})['owner'] == previous.owner
        previous.release()
    monkeypatch.setattr(worker.stop, 'wait', finish_previous)
    assert worker.acquire_lease()
    assert db.locks.find_one({'_id': 'worker'})['owner'] == replacement.owner


def test_startup_timeout_preserves_live_worker_lease(monkeypatch):
    db = mongomock.MongoClient().db
    previous, replacement = Store(db), Store(db)
    assert previous.acquire()
    worker = Worker(replacement, Mock(), Mock())
    with pytest.raises(RuntimeError, match='still holds the lease'):
        worker.acquire_lease(timeout=0)
    assert db.locks.find_one({'_id': 'worker'})['owner'] == previous.owner


def test_shutdown_during_lease_wait_does_not_acquire(monkeypatch):
    store = Mock()
    store.acquire.return_value = False
    worker = Worker(store, Mock(), Mock())
    monkeypatch.setattr(worker.stop, 'wait', lambda _: worker.stop.set())
    assert worker.acquire_lease() is False
    store.recover.assert_not_called()
    store.release.assert_not_called()
