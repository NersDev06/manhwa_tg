"""Durable promotions: suppress archives, send after each three live chapters.
Unknown delivery is held for manual inspection, never automatically reposted.
"""
from datetime import timedelta
from .store import now
from .telegram import DeliveryRejected

DONE = ['sent', 'baseline', 'skipped']


def prepare(store):
    for sub in store.subs.find({'enabled': True, 'initialized': True}):
        if store.jobs.find_one({'subscription': sub['_id'], 'status': {'$nin': DONE}}):
            continue
        count = store.jobs.count_documents({'subscription': sub['_id'], 'status': 'sent'})
        anchor = sub.get('promotion_anchor')
        if anchor is None:
            store.subs.update_one({'_id': sub['_id'], 'promotion_anchor': {'$exists': False}},
                                 {'$set': {'promotion_anchor': count, 'caught_up_at': now()}})
            continue
        # One outbox item per group. Jumping over a backlog must not produce a promo flood.
        if count - anchor >= 3:
            key = f"promo:{sub['_id']}:{anchor + 3}"
            store.db.outbox.update_one({'_id': key}, {'$setOnInsert': {
                'subscription': sub['_id'], 'channel': sub['channel'], 'kind': 'promotion', 'status': 'pending',
                'through': count, 'created': now(), 'attempts': 0}}, upsert=True)


def deliver_one(store, telegram):
    item = store.db.outbox.find_one({'kind': 'promotion', 'status': 'pending', '$or': [
        {'retry_at': {'$exists': False}}, {'retry_at': {'$lte': now()}}]}, sort=[('created', 1)])
    if item is None:
        return
    # Do not put promotions between pending archive chapters or while a title is paused.
    sub = store.subs.find_one({'_id': item['subscription'], 'enabled': True})
    if sub is None or store.jobs.find_one({'subscription': sub['_id'], 'status': {'$nin': DONE}}):
        return
    buttons = [[{'text': other.get('metadata', {}).get('main_title_ru') or other.get('title', 'Манхва'),
                 'url': other['public_url']}]
               for other in store.subs.find({'enabled': True, 'public_url': {'$regex': '^https://t.me/'}})
               if other['_id'] != item['subscription']]
    if not buttons:
        return
    claimed = store.db.outbox.update_one({'_id': item['_id'], 'status': 'pending'},
        {'$set': {'status': 'sending'}, '$inc': {'attempts': 1}})
    if not claimed.modified_count:
        return
    try:
        result = telegram.message(item['channel'], '📚 Вам также могут понравиться\n\nДругие манхвы в наших каналах:', buttons)
    except DeliveryRejected as exc:
        if exc.retry_after:
            store.db.runtime.update_one({'_id': 'telegram'}, {'$max': {'not_before': now() + timedelta(seconds=exc.retry_after + 5)}}, upsert=True)
        store.db.outbox.update_one({'_id': item['_id']}, {'$set': {
            'status': 'pending' if item['attempts'] < 4 else 'failed',
            'retry_at': now() + timedelta(seconds=max(60, exc.retry_after + 5)), 'error': str(exc)}})
        return
    except Exception as exc:
        store.db.outbox.update_one({'_id': item['_id']}, {'$set': {'status': 'uncertain', 'error': type(exc).__name__}})
        return
    store.db.outbox.update_one({'_id': item['_id']}, {'$set': {'status': 'sent',
        'message_id': result['message_id'], 'sent_at': now()}})
    store.subs.update_one({'_id': item['subscription']}, {'$max': {'promotion_anchor': item['through']}})


def recover(store):
    store.db.outbox.update_many({'status': 'sending'}, {'$set': {'status': 'uncertain', 'error': 'Restart during delivery'}})
    # A crash after saving the receipt must advance the anchor, not create another post.
    for item in store.db.outbox.find({'kind': 'promotion', 'status': 'sent'}):
        store.subs.update_one({'_id': item['subscription']}, {'$max': {'promotion_anchor': item['through']}})
