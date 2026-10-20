from unittest.mock import Mock
import mongomock
from manhwa.store import Store, now
from manhwa import promotions
from manhwa.telegram import DeliveryUnknown, DeliveryRejected


def setup():
    s = Store(mongomock.MongoClient().db)
    s.subs.insert_many([{'_id': 'a', 'channel': '@a', 'enabled': True, 'initialized': True, 'public_url': 'https://t.me/aaaaa'},
                       {'_id': 'b', 'channel': '@b', 'enabled': True, 'initialized': True, 'public_url': 'https://t.me/bbbbb'}])
    return s


def test_every_three_completed_chapters_even_with_archive_remaining():
    s=setup(); tg=Mock(); tg.message.return_value={'message_id':8}
    s.jobs.insert_many([{'subscription':'a','status':'pending'} for _ in range(7)])
    promotions.prepare(s)
    for n in range(1,7):
        j=s.jobs.find_one({'status':'pending'})
        s.jobs.update_one({'_id':j['_id']},{'$set':{'status':'sent','sent_parts':[{'message_id':n*2},{'message_id':n*2+1}]}})
        promotions.prepare(s);promotions.prepare(s)
        promotions.deliver_one(s,tg);promotions.deliver_one(s,tg)
        assert tg.message.call_count==n//3
    assert s.db.outbox.count_documents({'status':'sent'})==2
    assert s.subs.find_one({'_id':'a'})['promotion_anchor']==6
    assert tg.message.call_args.args[2][0][0]['url']=='https://t.me/bbbbb'


def test_unknown_promotion_never_retried_or_replaced():
    s=setup();s.subs.update_one({'_id':'a'},{'$set':{'promotion_anchor':0}})
    s.jobs.insert_many([{'subscription':'a','status':'sent'} for _ in range(3)])
    promotions.prepare(s)
    tg=Mock();tg.message.side_effect=DeliveryUnknown()
    promotions.deliver_one(s,tg)
    s.jobs.insert_many([{'subscription':'a','status':'sent'} for _ in range(3)])
    promotions.prepare(s);promotions.deliver_one(s,tg)
    assert tg.message.call_count==1
    assert s.db.outbox.count_documents({})==1
    assert s.db.outbox.find_one()['status']=='uncertain'


def test_paused_channel_does_not_block_other_recommendations():
    s=setup();s.subs.insert_one({'_id':'c','enabled':True,'initialized':True,'channel':'@c','public_url':'https://t.me/ccccc'})
    for sub in ('a','b'):
        s.jobs.insert_many([{'subscription':sub,'status':'sent'} for _ in range(3)])
    promotions.prepare(s);s.subs.update_one({'_id':'a'},{'$set':{'enabled':False}})
    tg=Mock();tg.message.return_value={'message_id':9}
    promotions.deliver_one(s,tg)
    assert tg.message.call_args.args[0]=='@b'


def test_multipart_in_flight_defers_recommendation():
    s=setup();s.jobs.insert_many([{'subscription':'a','status':'sent'} for _ in range(3)])
    promotions.prepare(s);s.jobs.insert_one({'subscription':'a','status':'sending'})
    tg=Mock();promotions.deliver_one(s,tg)
    tg.message.assert_not_called()


def test_late_recommendation_coalesces_backlog():
    s=setup();s.jobs.insert_many([{'subscription':'a','status':'sent'} for _ in range(3)])
    promotions.prepare(s)
    s.jobs.insert_many([{'subscription':'a','status':'sent'} for _ in range(9)])
    tg=Mock();tg.message.return_value={'message_id':10}
    promotions.deliver_one(s,tg);promotions.prepare(s);promotions.deliver_one(s,tg)
    assert tg.message.call_count==1
    assert s.subs.find_one({'_id':'a'})['promotion_anchor']==12
