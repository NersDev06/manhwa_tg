"""Idempotent channel presentation using explicitly granted Bot API permissions."""
from pathlib import Path
import tempfile
from .seo import channel_title, bio, navigator, public_metadata
from .store import now
from .telegram import DeliveryRejected


def setup_channel(store, source, telegram, sub):
    meta = source.metadata(sub['url'])
    if sub.get('main_title_override'):
        if meta['main_title_ru'] != sub['main_title_override']:
            meta['alt_titles_ru'] = list(dict.fromkeys([meta['main_title_ru']] + meta['alt_titles_ru']))
        meta['main_title_ru'] = sub['main_title_override']
    meta['alt_titles_ru'] = [s for s in meta['alt_titles_ru'] if s != meta['main_title_ru']]
    meta = public_metadata(meta, sub['_id'])
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
    sub = {**sub, 'metadata': meta}
    navigation_text, first_url = navigation_content(store, sub)
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
            result = telegram.message(channel, navigation_text)
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
        'text': navigation_text, 'parse_mode': 'HTML', 'link_preview_options': {'is_disabled': True}})
    store.db.outbox.update_one({'_id': key}, {'$set': {'first_url': first_url, 'pinned': True}})
    return item['message_id']


def navigation_content(store, sub):
    chapters = list(store.jobs.find({'subscription': sub['_id'], 'status': 'sent',
        'sent_parts.0.message_id': {'$exists': True}},
        {'number': 1, 'volume': 1, 'sent_parts.message_id': 1}).sort([('volume', 1), ('number', 1)]))
    first_url = sub.get('public_url', '').rstrip('/') + '/' + str(chapters[0]['sent_parts'][0]['message_id']) if chapters and sub.get('public_url') else None
    meta = public_metadata(sub['metadata'], sub['_id'])
    return navigator(meta, first_url, chapters, sub.get('public_url')), first_url


def refresh_navigation(store, telegram, force=False):
    import hashlib
    from datetime import timedelta
    for sub in store.subs.find({'enabled': True, 'public_url': {'$regex': '^https://t.me/'}}):
        item = store.db.outbox.find_one({'_id': 'navigator:' + sub['_id'], 'status': 'sent', 'pinned': True})
        if not item or not sub.get('metadata'):
            continue
        checked = item.get('navigation_checked')
        if not force and checked and checked.replace(tzinfo=now().tzinfo) > now() - timedelta(minutes=5):
            continue
        text, first_url = navigation_content(store, sub)
        fingerprint = hashlib.sha256(text.encode()).hexdigest()
        if fingerprint != item.get('navigation_fingerprint'):
            telegram.call('editMessageText', {'chat_id': sub['channel'], 'message_id': item['message_id'],
                'text': text, 'parse_mode': 'HTML', 'link_preview_options': {'is_disabled': True}})
        store.db.outbox.update_one({'_id': item['_id']}, {'$set': {'first_url': first_url,
            'navigation_fingerprint': fingerprint, 'navigation_checked': now()}})
