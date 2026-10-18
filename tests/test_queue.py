from datetime import timedelta

import mongomock
import pytest
from bson.decimal128 import Decimal128

from manhwa.source import Chapter
from manhwa.store import Store, now


@pytest.fixture
def store(monkeypatch):
    # mongomock lacks BSON Decimal128 comparison; preserve MongoDB numeric semantics.
    import mongomock.filtering
    original = mongomock.filtering.bson_compare
    def compare(op, a, b, can_compare_types=True):
        if isinstance(a, Decimal128):
            a = a.to_decimal()
        if isinstance(b, Decimal128):
            b = b.to_decimal()
        return original(op, a, b, can_compare_types)
    monkeypatch.setattr(mongomock.filtering, 'bson_compare', compare)
    s = Store(mongomock.MongoClient(tz_aware=True).test)
    s.indexes()
    return s


def chapter(n):
    return Chapter(f'https://manga-shi.org/manga/test/tom-1/glava-{n}/', f'Глава {n}', '1', str(n))


def test_new_mode_baseline_and_no_duplicates(store):
    key = store.add('url', '@test', 'new')
    store.sync(store.subs.find_one(), 'Test', [chapter(1), chapter(2)])
    assert store.claim() is None
    store.sync(store.subs.find_one(), 'Test', [chapter(1), chapter(2), chapter(3)])
    store.sync(store.subs.find_one(), 'Test', [chapter(1), chapter(2), chapter(3)])
    assert store.jobs.count_documents({}) == 3
    assert store.claim()['name'] == 'Глава 3'


def test_earlier_failure_blocks_later_and_pause(store):
    key = store.add('url', '@test', 'archive', '1')
    store.sync(store.subs.find_one(), 'Test', [chapter(2), chapter(1)])
    job = store.claim()
    assert job['name'] == 'Глава 1'
    store.fail(job, 'timeout')
    assert store.claim() is None
    store.jobs.update_one({'_id': job['_id']}, {'$set': {'retry_at': now() - timedelta(seconds=1)}})
    assert store.claim()['_id'] == job['_id']
    store.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sent'}})
    store.subs.update_one({'_id': key}, {'$set': {'enabled': False}})
    assert store.claim() is None


def test_recover_never_retries_unknown_send(store):
    store.add('url', '@test', 'archive', '1')
    store.sync(store.subs.find_one(), 'Test', [chapter(1), chapter(2)])
    job = store.claim()
    store.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sending'}})
    store.recover()
    assert store.jobs.find_one({'_id': job['_id']})['status'] == 'uncertain'
    assert store.claim() is None


def test_single_worker_lease(store):
    other = Store(store.db)
    assert store.acquire()
    assert not other.acquire()
    assert store.renew()
    store.release()
    assert other.acquire()


def test_daily_quota_is_per_channel_and_retry_does_not_consume_second_slot(store):
    store.add('url', '@test', 'archive', '1')
    store.sync(store.subs.find_one(), 'Test', [chapter(1), chapter(2), chapter(3)])
    first = store.claim(daily_limit=2)
    store.fail(first, 'temporary')
    store.jobs.update_one({'_id': first['_id']}, {'$set': {'retry_at': now() - timedelta(seconds=1)}})
    retried = store.claim(daily_limit=2)
    assert retried['_id'] == first['_id']
    store.jobs.update_one({'_id': first['_id']}, {'$set': {'status': 'sent'}})
    second = store.claim(daily_limit=2)
    store.jobs.update_one({'_id': second['_id']}, {'$set': {'status': 'sent'}})
    assert store.claim(daily_limit=2) is None
    assert store.db.daily_quota.find_one()['count'] == 2


def test_second_channel_has_independent_daily_quota(store):
    first_id = store.add('url1', '@one', 'archive', '1')
    second_id = store.add('url2', '@two', 'archive', '1')
    for sub in store.subs.find():
        store.sync(sub, 'Test', [chapter(1), chapter(2)])
    first = store.claim(daily_limit=1)
    store.jobs.update_one({'_id': first['_id']}, {'$set': {'status': 'sent'}})
    second = store.claim(daily_limit=1)
    assert first['channel'] != second['channel']
    store.jobs.update_one({'_id': second['_id']}, {'$set': {'status': 'sent'}})
    assert store.claim(daily_limit=1) is None


def test_zero_limit_allows_more_than_ten(store):
    s = store
    s.add('url', '@unlimited', 'archive', '1')
    s.sync(s.subs.find_one(), 'Test', [Chapter(f'c{n}', f'Глава {n}', '1', str(n)) for n in range(1, 13)])
    for _ in range(12):
        job = s.claim(0)
        assert job is not None
        s.jobs.update_one({'_id': job['_id']}, {'$set': {'status': 'sent'}})
    assert s.claim(0) is None


def test_changed_source_url_does_not_recreate_sent_chapter(store):
    store.add('url','channel','archive','1');sub=store.subs.find_one()
    store.sync(sub,'title',[chapter(1)])
    original=store.jobs.find_one()
    store.jobs.update_one({'_id':original['_id']},{'$set':{'status':'sent','sent_parts':[{'message_id':42}]}})
    store.sync(sub,'title',[Chapter('another-site/edition/one','Глава 1','1','1.00')])
    assert store.jobs.count_documents({})==1
    assert store.jobs.find_one()['sent_parts'][0]['message_id']==42


def test_same_number_in_distinct_canonical_volumes_is_not_collapsed(store):
    store.add('url','channel','archive','1');sub=store.subs.find_one()
    store.sync(sub,'title',[Chapter('vol1','Глава 1','1','1'),Chapter('vol2','Глава 1','2','1')])
    assert store.jobs.count_documents({})==2


def test_new_old_bonus_does_not_get_posted_after_source_switch(store):
    store.add('url','channel','archive','1');sub=store.subs.find_one()
    store.sync(sub,'title',[chapter(1),chapter(3)])
    store.jobs.update_many({}, {'$set':{'status':'sent'}})
    store.sync(sub,'title',[chapter(1),chapter(2),chapter(3),chapter(4)])
    assert store.jobs.find_one({'chapter_url':chapter(2).url})['status']=='baseline'
    assert store.claim()['number']==Decimal128('4')
