"""Optional owner-session username assignment; Bot API cannot do this.
Requires an already authorised Telethon client. Never performs interactive login.
"""
from datetime import timedelta
from telethon import errors, functions
from .seo import usernames
from .store import now


async def assign_username(client, store, subscription):
    client.flood_sleep_threshold = 0
    me = await client.get_me()
    if me is None or me.bot:
        raise ValueError('An authorised owner user session is required')
    if not subscription.get('metadata'):
        raise ValueError('Title metadata is required')
    channel = await client.get_entity(int(subscription['channel']))
    # Keep published addresses stable on reruns.
    if channel.username:
        return channel.username
    cooldown = store.db.runtime.find_one({'_id': 'owner_api'}) or {}
    if cooldown.get('not_before') and cooldown['not_before'].replace(tzinfo=now().tzinfo) > now():
        return None
    key = 'username:' + subscription['_id']
    store.db.owner_tasks.update_one({'_id': key}, {'$setOnInsert': {'status': 'pending', 'candidate_index': 0}}, upsert=True)
    task = store.db.owner_tasks.find_one({'_id': key})
    candidates = usernames(subscription['metadata'])
    for index in range(task['candidate_index'], len(candidates)):
        name = candidates[index]
        try:
            available = await client(functions.channels.CheckUsernameRequest(channel, name))
            if not available:
                store.db.owner_tasks.update_one({'_id': key}, {'$set': {'candidate_index': index + 1}})
                continue
            await client(functions.channels.UpdateUsernameRequest(channel, name))
        except (errors.UsernameOccupiedError, errors.UsernameInvalidError, errors.UsernamePurchaseAvailableError):
            store.db.owner_tasks.update_one({'_id': key}, {'$set': {'candidate_index': index + 1}})
            continue
        except errors.FloodWaitError as exc:
            due = now() + timedelta(seconds=exc.seconds + 5)
            store.db.runtime.update_one({'_id': 'owner_api'}, {'$set': {'not_before': due}}, upsert=True)
            store.db.owner_tasks.update_one({'_id': key}, {'$set': {'status': 'pending', 'retry_at': due, 'candidate_index': index}})
            return None
        store.db.owner_tasks.update_one({'_id': key}, {'$set': {'status': 'done', 'username': name}})
        store.subs.update_one({'_id': subscription['_id']}, {'$set': {'public_url': 'https://t.me/' + name}})
        return name
    store.db.owner_tasks.update_one({'_id': key}, {'$set': {'status': 'exhausted'}})
    return None


async def main():
    import os, sys
    from dotenv import load_dotenv
    from telethon import TelegramClient
    from .__main__ import database
    load_dotenv()
    session = os.environ.get('TELEGRAM_OWNER_SESSION')
    api_id, api_hash = os.environ.get('TELEGRAM_API_ID'), os.environ.get('TELEGRAM_API_HASH')
    if not session or not api_id or not api_hash:
        raise ValueError('Configure an already authorised owner session and Telegram API credentials locally')
    store = database()
    sub = store.subs.find_one({'_id': sys.argv[1]})
    if sub is None:
        raise ValueError('Unknown subscription')
    client = TelegramClient(session, int(api_id), api_hash, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise ValueError('Owner session is not authorised; no login will be attempted')
        result = await assign_username(client, store, sub)
        print('Assigned: @' + result if result else 'Deferred; see owner_tasks')
    finally:
        await client.disconnect()


if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except Exception as exc:
        print('Owner username setup failed:', type(exc).__name__)
        raise SystemExit(1)
