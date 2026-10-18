"""Ordered public source chain. Job identity and Telegram receipts never depend on a site URL."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests
from .source import MangaShi, Chapter, SourceError
from .store import now
from . import buff, remanga

LABELS = {'mangashi': 'MangaShi', 'wamanga': 'WaManga', 'mangabuff': 'MangaBuff', 'remanga': 'ReManga'}


@dataclass(frozen=True)
class Candidate:
    kind: str
    url: str
    canonical: str
    number: str
    config: dict

    @property
    def name(self):
        return LABELS[self.kind]


class ResilientSource(MangaShi):
    def __init__(self, *args, config=None, **kwargs):
        super().__init__(*args, **kwargs)
        rows = config if config is not None else json.loads(
            (Path(__file__).resolve().parent.parent / 'config/channels.json').read_text())
        self.titles = {r['url']: r for r in rows}
        self.store = None
        self.cache = {}
        self.cooldowns = {}

    def bind(self, store):
        self.store = store

    def get(self, url, **kwargs):
        host = urlparse(url).hostname or ''
        if host == 'mangabuff.ru' or host.endswith('.mangabuff.ru'):
            headers = {'Referer': 'https://mangabuff.ru/'}
        elif host in ('remanga.org', 'reimg2.org') or host.endswith(('.remanga.org', '.reimg2.org')):
            headers = {'Referer': 'https://remanga.org/', 'Origin': 'https://remanga.org'}
        elif host == 'wamanga.ru':
            headers = {'Referer': 'https://wamanga.ru/'}
        else:
            headers = {}
        kwargs['headers'] = {**headers, **kwargs.get('headers', {})}
        return super().get(url, **kwargs)

    @staticmethod
    def _number(value):
        try:
            number = Decimal(str(value).replace(',', '.'))
            if not number.is_finite() or number < 0:
                raise InvalidOperation
            return number
        except InvalidOperation:
            raise SourceError('Invalid chapter number') from None

    def _health(self, canonical, kind, **values):
        config = next((c for c in self.titles.get(canonical, {}).get('sources', []) if c['kind'] == kind), {})
        values['images_enabled'] = config.get('images_enabled', True)
        if self.store:
            self.store.subs.update_many({'url': canonical}, {'$set': {
                'source_health.' + kind: {'updated': now(), **values}}})

    def _probe(self, canonical, config, call, *, chapter=None):
        kind = config['kind']
        keys = [(kind, '*'), (kind, canonical), (kind, chapter)]
        if any(self.cooldowns.get(k, 0) > time.monotonic() for k in keys):
            self._health(canonical, kind, state='unavailable', error='Cooldown')
            raise SourceError(LABELS[kind] + ' temporarily unavailable')
        try:
            return call()
        except (requests.RequestException, SourceError, ValueError, KeyError, TypeError, AttributeError, InvalidOperation) as exc:
            code = exc.response.status_code if isinstance(exc, requests.HTTPError) and exc.response is not None else None
            global_failure = code in (403, 429, 500, 502, 503, 504) or isinstance(exc, (requests.Timeout, requests.ConnectionError))
            key = (kind, '*') if global_failure else (kind, chapter or canonical)
            self.cooldowns[key] = time.monotonic() + (900 if global_failure else 300)
            self._health(canonical, kind, state='unavailable', error=type(exc).__name__, http_status=code)
            if isinstance(exc, (KeyError, TypeError, AttributeError, InvalidOperation)):
                raise SourceError('Malformed provider response') from None
            raise

    def reject(self, candidate, exc):
        # A bad image or failed chapter must not disable unrelated chapters or sites.
        self.cooldowns[(candidate.kind, candidate.url)] = time.monotonic() + 300
        self._health(candidate.canonical, candidate.kind, state='chapter_failed', error=type(exc).__name__)

    def _wa_catalogue(self, url):
        with self.get(url) as response:
            soup = BeautifulSoup(response.content, 'html.parser')
        heading = soup.select_one('h1')
        if heading is None:
            raise SourceError('WaManga title heading missing')
        chapters = {}
        for a in soup.select('a[href*="/glava-"]'):
            target = urljoin('https://wamanga.ru/', a['href'])
            match = re.fullmatch(re.escape(urlparse(url).path) + r'/glava-(\d+(?:[.,_-]\d+)?)/?', urlparse(target).path)
            if match and urlparse(target).hostname == 'wamanga.ru':
                number = re.sub('[,_-]', '.', match[1])
                chapters[target] = Chapter(target, 'Глава ' + number, '0', number)
        if not chapters:
            raise SourceError('WaManga chapter catalogue empty')
        return heading.get_text(' ', strip=True), list(chapters.values())

    def _catalogue(self, canonical, config):
        kind = config['kind']
        key = (canonical, kind)
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < 1800:
            return cached[1], cached[2]
        def read():
            if kind == 'mangashi':
                return MangaShi.chapters(self, config['url'])
            if kind == 'wamanga':
                return self._wa_catalogue(config['url'])
            if kind == 'mangabuff':
                return buff.catalogue(self, config['url'])
            if kind == 'remanga':
                return remanga.catalogue(self, config)
            raise SourceError('Unknown source kind')
        title, chapters = self._probe(canonical, config, read)
        indexed = {}
        for chapter in chapters:
            number = self._number(chapter.number)
            previous = indexed.get(number)
            if previous and previous.url != chapter.url:
                raise SourceError('Ambiguous chapter numbers in ' + LABELS[kind])
            indexed[number] = chapter
        if not indexed:
            raise SourceError('Empty source catalogue')
        self.cache[key] = (time.monotonic(), title, indexed)
        self._health(canonical, kind, state='available', chapters=len(indexed))
        return title, indexed

    def _catalogues(self, canonical):
        result = []
        for config in self.titles[canonical]['sources']:
            try:
                title, chapters = self._catalogue(canonical, config)
                result.append((config, title, chapters))
            except (requests.RequestException, SourceError, ValueError):
                continue
        if not result:
            raise SourceError('All configured source catalogues unavailable')
        return result

    def chapters(self, url):
        if url not in self.titles:
            return MangaShi.chapters(self, url)
        row = self.titles[url]
        catalogues = self._catalogues(url)
        volume = int(row['canonical_volume'])
        existing = {}
        if self.store:
            sub = self.store.subs.find_one({'url': url})
            if sub:
                for job in self.store.jobs.find({'subscription': sub['_id']}):
                    number = job['number'].to_decimal()
                    if number in existing or job['volume'] != volume:
                        raise SourceError('Queue identity ambiguous; explicit volume mapping required')
                    existing[number] = job
        merged = {}
        for config, title, chapters in catalogues:
            for number, chapter in chapters.items():
                if number in merged:
                    continue
                prior = existing.get(number)
                # New job URLs are stable internal routes; actual reader URLs live in the source cache.
                stable = prior['chapter_url'] if prior else url + f'tom-{volume}/glava-{format(number, "f")}/'
                merged[number] = Chapter(stable, prior['name'] if prior else chapter.name, str(volume), format(number, 'f'))
        if self.store:
            self.store.subs.update_many({'url': url}, {'$set': {
                'fallback_missing': [format(n, 'f') for n in existing if n not in merged],
                'available_sources': [LABELS[c['kind']] for c, _, _ in catalogues if c.get('images_enabled', True)]}})
        return catalogues[0][1], sorted(merged.values(), key=lambda chapter: chapter.order)

    def _resolve(self, url):
        for canonical, row in self.titles.items():
            roots = [canonical] + [c['url'] for c in row['sources']]
            if any(url == root or url.startswith(root.rstrip('/') + '/') for root in roots):
                match = re.search(r'/glava[-_](\d+(?:[.,_-]\d+)?)/?$', urlparse(url).path)
                if match:
                    return canonical, self._number(re.sub('[,_-]', '.', match[1]))
                match = re.search(r'/\d+/(\d+(?:\.\d+)?)/?$', urlparse(url).path)
                if match:
                    return canonical, self._number(match[1])
        raise SourceError('Chapter URL is not in the verified title mapping')

    def candidates(self, url):
        try:
            canonical, number = self._resolve(url)
        except SourceError:
            parsed = urlparse(url)
            match = re.fullmatch(r'/manga/([^/]+)/(?:tom[-_]\d+/)?glava[-_](\d+(?:[.,_-]\d+)?)/?', parsed.path)
            if parsed.scheme != 'https' or parsed.hostname != 'manga-shi.org' or not match:
                raise
            canonical = 'https://manga-shi.org/manga/' + match[1] + '/'
            if canonical in self.titles:
                raise
            return [Candidate('mangashi', url, canonical, str(self._number(re.sub('[,_-]', '.', match[2]))),
                              {'kind': 'mangashi', 'url': canonical})]
        result = []
        for config, _, chapters in self._catalogues(canonical):
            if config.get('images_enabled', True) and number in chapters:
                chapter = chapters[number]
                if self.cooldowns.get((config['kind'], chapter.url), 0) <= time.monotonic():
                    result.append(Candidate(config['kind'], chapter.url, canonical, format(number, 'f'), config))
        if not result:
            raise SourceError('Requested chapter missing from all available image sources')
        return result

    def provider_pages(self, candidate):
        def read():
            if candidate.kind == 'mangashi':
                return MangaShi.pages(self, candidate.url)
            if candidate.kind == 'mangabuff':
                return buff.pages(self, candidate.url)
            if candidate.kind == 'remanga':
                return remanga.pages(self, candidate.url, candidate.config, candidate.number)
            with self.get(candidate.url) as response:
                soup = BeautifulSoup(response.content, 'html.parser')
            pages = [urljoin(candidate.url, i.get('data-src') or i.get('src', '')) for i in soup.select('img.reader-page')]
            if not pages or any(urlparse(p).scheme != 'https' or urlparse(p).hostname != 'wamanga.ru' for p in pages):
                raise SourceError('WaManga reader images missing or unexpected host')
            return pages
        return self._probe(candidate.canonical, candidate.config, read, chapter=candidate.url)

    def pages(self, url):
        for candidate in self.candidates(url):
            try:
                return self.provider_pages(candidate)
            except (requests.RequestException, SourceError, ValueError):
                continue
        raise SourceError('Requested chapter reader unavailable in all sources')

    def metadata(self, url):
        if self.store:
            sub = self.store.subs.find_one({'url': url}) or {}
            if sub.get('metadata'):
                return sub['metadata']
        return MangaShi.metadata(self, url)
