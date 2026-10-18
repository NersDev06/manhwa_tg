"""Idempotent channel presentation using explicitly granted Bot API permissions."""
from pathlib import Path
import tempfile
from .seo import channel_title, bio, navigator
from .store import now
from .telegram import DeliveryRejected


def setup_channel(store, source, telegram, sub):
    meta = source.metadata(sub['url'])
    if sub.get('main_title_override'):
        if meta['main_title_ru'] != sub['main_title_override']:
            meta['alt_titles_ru'] = list(dict.fromkeys([meta['main_title_ru']] + meta['alt_titles_ru']))
        meta['main_title_ru'] = sub['main_title_override']
    meta['alt_titles_ru'] = [s for s in meta['alt_titles_ru'] if s != meta['main_title_ru']]
    store.subs.update_one({'_id': sub['_id']}, {'$set': {'metadata': meta}})
    channel = sub['channel']
    current = telegram.call('getChat', {'chat_id': channel})
    for method, values in [('setChatTitle', {'title': channel_title(meta)}),
                           ('setChatDescription', {'description': bio(meta)})]:
        if any(current.get(k, '') != v for k, v in values.items()):
            telegram.call(method, {'chat_id': channel, **values})
    if meta.get('cover_url') and not sub.get('cover_installed'):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cover.jpg'
            from PIL import Image
            raw = Path(folder) / 'cover.raw'
            with source.get(meta['cover_url'], stream=True) as r, raw.open('wb') as out:
                size = 0
                for block in r.iter_content(65536):
                    size += len(block)
                    if size > 10_000_000:
                        raise ValueError('Cover too large')
                    out.write(block)
            with Image.open(raw) as im:
                if im.width * im.height > 16_000_000:
                    raise ValueError('Cover pixel limit exceeded')
                im = im.convert('RGB'); im.thumbnail((1000, 1000)); im.save(path, 'JPEG', quality=92)
            telegram.set_photo(channel, path)
        store.subs.update_one({'_id': sub['_id']}, {'$set': {'cover_installed': True}})
    first = store.jobs.find_one({'subscription': sub['_id'], 'status': 'sent', 'sent_parts.0': {'$exists': True}}, sort=[('volume', 1), ('number', 1)])
    first_url = sub.get('public_url', '').rstrip('/') + '/' + str(first['sent_parts'][0]['message_id']) if first and sub.get('public_url') else None
    key = 'navigator:' + sub['_id']
    store.db.outbox.update_one({'_id': key}, {'$setOnInsert': {'kind': 'navigator', 'status': 'pending', 'created': now()}} ,upsert=True)
    item = store.db.outbox.find_one({'_id': key})
    if item['status'] == 'pending':
        store.db.outbox.update_one({'_id': key, 'status': 'pending'}, {'$set': {'status': 'sending'}})
        try:
            # Photo caption is short; all aliases live in the separate text navigator.
            if meta.get('cover_url'):
                result = telegram.call('sendPhoto', {'chat_id': channel, 'photo': meta['cover_url'],
                    'caption': meta['main_title_ru'], 'disable_notification': True, 'protect_content': True})
                store.db.outbox.update_one({'_id': key}, {'$set': {'cover_message_id': result['message_id']}})
            result = telegram.message(channel, navigator(meta, first_url))
        except DeliveryRejected:
            store.db.outbox.update_one({'_id': key}, {'$set': {'status': 'failed'}})
            raise
        except Exception:
            store.db.outbox.update_one({'_id': key}, {'$set': {'status': 'uncertain'}})
            raise
        store.db.outbox.update_one({'_id': key}, {'$set': {'status': 'sent', 'message_id': result['message_id'], 'first_url': first_url}})
        item = store.db.outbox.find_one({'_id': key})
    if item['status'] != 'sent':
        raise RuntimeError('Navigator delivery needs manual inspection')
    telegram.call('pinChatMessage', {'chat_id': channel, 'message_id': item['message_id'], 'disable_notification': True})
    # Refresh the direct first-chapter link on reruns without making another post.
    telegram.call('editMessageText', {'chat_id': channel, 'message_id': item['message_id'],
        'text': navigator(meta, first_url), 'parse_mode': 'HTML', 'link_preview_options': {'is_disabled': True}})
    store.db.outbox.update_one({'_id': key}, {'$set': {'first_url': first_url, 'pinned': True}})
    return item['message_id']


def refresh_navigation(store, telegram):
    for sub in store.subs.find({'enabled': True, 'public_url': {'$regex': '^https://t.me/'}}):
        item = store.db.outbox.find_one({'_id': 'navigator:' + sub['_id'], 'status': 'sent', 'pinned': True})
        if not item or item.get('first_url') or not sub.get('metadata'):
            continue
        first = store.jobs.find_one({'subscription': sub['_id'], 'status': 'sent', 'sent_parts.0': {'$exists': True}}, sort=[('volume', 1), ('number', 1)])
        if not first:
            continue
        first_url = sub['public_url'].rstrip('/') + '/' + str(first['sent_parts'][0]['message_id'])
        telegram.call('editMessageText', {'chat_id': sub['channel'], 'message_id': item['message_id'],
            'text': navigator(sub['metadata'], first_url), 'parse_mode': 'HTML',
            'link_preview_options': {'is_disabled': True}})
        store.db.outbox.update_one({'_id': item['_id']}, {'$set': {'first_url': first_url}})
