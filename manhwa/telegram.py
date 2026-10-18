import json
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder


class DeliveryUnknown(RuntimeError):
    pass


class DeliveryRejected(RuntimeError):
    def __init__(self, code, retry_after=0):
        super().__init__(f'Telegram rejected request (code {code})')
        self.code, self.retry_after = code, retry_after


class Telegram:
    def __init__(self, token):
        if not token:
            raise ValueError('TELEGRAM_BOT_TOKEN is required')
        self.base = 'https://api.telegram.org/bot' + token

    def document(self, channel, path, caption, filename):
        # Streaming upload avoids requests' default in-memory multipart encoding.
        with path.open('rb') as stream:
            encoder = MultipartEncoder(fields={'chat_id': str(channel), 'caption': caption[:1024],
                'parse_mode': 'HTML', 'protect_content': 'true',
                'document': (filename, stream, 'application/pdf')})
            try:
                response = requests.post(self.base + '/sendDocument', data=encoder,
                    headers={'Content-Type': encoder.content_type}, timeout=(20, 180))
            except requests.RequestException:
                raise DeliveryUnknown('Connection interrupted during Telegram upload') from None
        try:
            data = response.json()
        except ValueError:
            raise DeliveryUnknown('Telegram returned an unreadable response') from None
        if not data.get('ok'):
            code = data.get('error_code', response.status_code)
            if code >= 500:
                raise DeliveryUnknown('Telegram server error; delivery requires checking')
            raise DeliveryRejected(code, data.get('parameters', {}).get('retry_after', 0))
        try:
            return {'message_id': data['result']['message_id'],
                    'file_id': data['result']['document']['file_id']}
        except (KeyError, TypeError):
            raise DeliveryUnknown('Incomplete Telegram delivery receipt') from None

    def check_channel(self, channel):
        def call(method, data):
            try:
                result = requests.post(self.base + '/' + method, data=data, timeout=30).json()
            except (requests.RequestException, ValueError):
                raise RuntimeError('Unable to check Telegram permissions') from None
            if not result.get('ok'):
                raise RuntimeError('Telegram permission check rejected')
            return result['result']
        me = call('getMe', {})
        chat = call('getChat', {'chat_id': channel})
        member = call('getChatMember', {'chat_id': channel, 'user_id': me['id']})
        if chat.get('type') != 'channel' or not member.get('can_post_messages'):
            raise RuntimeError('Bot must be a channel administrator with posting permission')
        return {'bot': me['username'], 'channel': chat['title'], 'id': chat['id']}

    def alert(self, chat_id, text):
        if not chat_id:
            return
        try:
            requests.post(self.base + '/sendMessage', data={'chat_id': chat_id, 'text': text[:3500]}, timeout=20)
        except requests.RequestException:
            pass

    def call(self, method, payload):
        try:
            response = requests.post(self.base + '/' + method, json=payload, timeout=(20, 90))
            data = response.json()
        except (requests.RequestException, ValueError):
            raise DeliveryUnknown('Telegram response unavailable; check before retrying') from None
        if not data.get('ok'):
            code = data.get('error_code', response.status_code)
            if method.startswith('editMessage') and code == 400 and 'message is not modified' in data.get('description', '').lower():
                return True
            if code >= 500:
                raise DeliveryUnknown('Telegram server error; check before retrying')
            raise DeliveryRejected(code, data.get('parameters', {}).get('retry_after', 0))
        return data['result']

    def message(self, channel, text, buttons=None):
        payload = {'chat_id': channel, 'text': text, 'parse_mode': 'HTML',
            'protect_content': True, 'disable_notification': True,
            'link_preview_options': {'is_disabled': True}}
        if buttons:
            payload['reply_markup'] = {'inline_keyboard': buttons}
        return self.call('sendMessage', payload)

    def photo(self, channel, path, caption):
        with path.open('rb') as stream:
            encoder = MultipartEncoder(fields={'chat_id': str(channel), 'caption': caption,
                'protect_content': 'true', 'disable_notification': 'true',
                'photo': (path.name, stream, 'image/jpeg')})
            try:
                response = requests.post(self.base + '/sendPhoto', data=encoder,
                    headers={'Content-Type': encoder.content_type}, timeout=(20, 120))
                data = response.json()
            except (requests.RequestException, ValueError):
                raise DeliveryUnknown('Preview delivery requires checking') from None
        if not data.get('ok'):
            code = data.get('error_code', response.status_code)
            if code >= 500:
                raise DeliveryUnknown('Preview delivery requires checking')
            raise DeliveryRejected(code, data.get('parameters', {}).get('retry_after', 0))
        return data['result']

    def set_photo(self, channel, path):
        with path.open('rb') as stream:
            encoder = MultipartEncoder(fields={'chat_id': str(channel), 'photo': (path.name, stream, 'image/jpeg')})
            try:
                response = requests.post(self.base + '/setChatPhoto', data=encoder,
                    headers={'Content-Type': encoder.content_type}, timeout=(20, 90))
                data = response.json()
            except (requests.RequestException, ValueError):
                raise DeliveryUnknown('Channel photo result unavailable') from None
        if not data.get('ok'):
            raise DeliveryRejected(data.get('error_code', response.status_code))
        return data['result']
