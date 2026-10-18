from unittest.mock import Mock
from pathlib import Path
import mongomock

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
    monkeypatch.setattr('manhwa.worker.build_chapter', lambda *a: ([path], {'pdf_pages': 1}))
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
