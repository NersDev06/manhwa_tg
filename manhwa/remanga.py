"""Read public, free chapters from ReManga's current public API."""
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlparse
from .source import Chapter, SourceError

API = 'https://api.remanga.org'


class ReaderPages(list):
    def __init__(self, groups):
        super().__init__(url for group in groups for url in group)
        self.groups = tuple(len(group) for group in groups)


def catalogue(source, config):
    with source.get(API + '/api/v2/titles/' + quote(config['directory'], safe='') + '/') as response:
        title = response.json()
    if title.get('id') != config['title_id']:
        raise SourceError('ReManga title identity changed')
    if config['branch_id'] not in {b['id'] for b in title.get('branches', [])}:
        raise SourceError('Configured ReManga translation branch unavailable')
    chapters, ids, signatures = [], set(), set()
    page = 1
    while True:
        with source.get(API + '/api/titles/chapters/', params={
                'branch_id': config['branch_id'], 'count': 100, 'ordering': 'index', 'page': page}) as response:
            data = response.json()
        content = data.get('content')
        if not isinstance(content, list):
            raise SourceError('ReManga chapter catalogue missing')
        if not content:
            break
        signature = tuple(c.get('id') for c in content)
        if signature in signatures or page > 2000:
            raise SourceError('Repeated ReManga pagination')
        signatures.add(signature)
        for c in content:
            # Never use paid, unpublished or unknown-access releases.
            if c.get('is_paid') is not False or c.get('is_published') is False:
                continue
            if c.get('id') in ids:
                continue
            try:
                number = Decimal(str(c['chapter']))
                if not number.is_finite() or number < 0:
                    raise InvalidOperation
            except (KeyError, InvalidOperation):
                raise SourceError('Invalid ReManga chapter number') from None
            ids.add(c['id'])
            text = format(number, 'f')
            chapters.append(Chapter(API + f"/api/titles/chapters/{c['id']}/",
                'Глава ' + text, str(c['tome']), text))
        # The public endpoint returns up to count rows; stop only on an empty page.
        page += 1
    if not chapters:
        raise SourceError('No free chapters in configured ReManga branch')
    return title['main_name'], chapters


def pages(source, url, config, number):
    if not url.startswith(API + '/api/titles/chapters/'):
        raise SourceError('Unexpected ReManga chapter endpoint')
    with source.get(url) as response:
        data = response.json().get('content', {})
    if (data.get('title_id') != config['title_id'] or data.get('branch_id') != config['branch_id']
            or Decimal(str(data.get('chapter', '-1'))) != Decimal(number)):
        raise SourceError('ReManga chapter identity mismatch')
    if data.get('is_paid') is not False or data.get('is_published') is not True:
        raise SourceError('ReManga chapter is not publicly available for free')
    groups = []
    for group in data.get('pages', []):
        if not isinstance(group, list):
            raise SourceError('Unexpected ReManga image groups')
        result = []
        for fragment in group:
            url = fragment.get('link', '')
            host = urlparse(url).hostname or ''
            if urlparse(url).scheme != 'https' or not any(
                    host == domain or host.endswith('.' + domain) for domain in ('reimg2.org', 'remanga.org')):
                raise SourceError('Unexpected ReManga image host')
            result.append(url)
        if not result:
            raise SourceError('ReManga reader contains an empty original page')
        groups.append(result)
    if not groups:
        raise SourceError('ReManga reader images missing')
    return ReaderPages(groups)
