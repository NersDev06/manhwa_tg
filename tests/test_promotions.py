from unittest.mock import Mock
import mongomock
from manhwa.store import Store
from manhwa import promotions
from manhwa.telegram import DeliveryUnknown


def setup():
    s = Store(mongomock.MongoClient().db)
    s.subs.insert_many([{'_id': 'a', 'channel': '@a', 'enabled': True, 'initialized': True, 'public_url': 'https://t.me/aaaaa'},
                       {'_id': 'b', 'channel': '@b', 'enabled': True, 'initialized': True, 'public_url': 'https://t.me/bbbbb'}])
    return s


def test_archive_suppressed_then_three_live_chapters():
    s = setup()
    s.jobs.insert_one({'subscription': 'a', 'status': 'pending'})
    promotions.prepare(s)
    assert s.subs.find_one({'_id': 'a'}).get('promotion_anchor') is None
    s.jobs.update_many({}, {'$set': {'status': 'sent'}})
    promotions.prepare(s)
    assert s.subs.find_one({'_id': 'a'})['promotion_anchor'] == 1
    s.jobs.insert_many([{'subscription': 'a', 'status': 'sent'} for _ in range(3)])
    promotions.prepare(s); promotions.prepare(s)
    assert s.db.outbox.count_documents({}) == 1
    tg = Mock(); tg.message.return_value = {'message_id': 8}
    promotions.deliver_one(s, tg); promotions.deliver_one(s, tg)
    assert tg.message.call_count == 1
    assert tg.message.call_args.args[2][0][0]['url'] == 'https://t.me/bbbbb'
    promotions.prepare(s)
    assert s.db.outbox.count_documents({}) == 1


def test_unknown_promotion_never_retried():
    s = setup()
    s.subs.update_one({'_id': 'a'}, {'$set': {'promotion_anchor': 0}})
    s.jobs.insert_many([{'subscription': 'a', 'status': 'sent'} for _ in range(3)])
    promotions.prepare(s)
    tg = Mock(); tg.message.side_effect = DeliveryUnknown()
    promotions.deliver_one(s, tg); promotions.deliver_one(s, tg)
    assert tg.message.call_count == 1
    assert s.db.outbox.find_one()['status'] == 'uncertain'
