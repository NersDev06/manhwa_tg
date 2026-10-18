"""Verified public catalogue and full-resolution reader for MangaBuff."""
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from .source import SourceError


def pages(source, url):
    match = re.fullmatch(r'https://mangabuff\.ru/manga/([^/]+)/(\d+)/(\d+(?:\.\d+)?)/?', url)
    if not match:
        raise SourceError('Unexpected full-resolution reader URL')
    with source.get(url) as r:
        soup = BeautifulSoup(r.content, 'html.parser')
    result, page_numbers = [], []
    for image in soup.select('.reader__item img'):
        label = image.get('alt', '')
        identity = re.search(r'том\s+(\d+)\s+глава\s+(\d+(?:\.\d+)?)\s+страница\s+(\d+)', label, re.I)
        if not identity or identity[1] != match[2] or identity[2] != match[3]:
            raise SourceError('Reader chapter identity does not match requested chapter')
        target = urljoin(url, image.get('data-src') or image.get('src', ''))
        if urlparse(target).scheme != 'https' or urlparse(target).netloc not in {'c2.mangabuff.ru','c3.mangabuff.ru','img.mangabuff.ru','custom.mangabuff.ru'}:
            raise SourceError('Unexpected full-resolution image host')
        result.append(target)
        page_numbers.append(int(identity[3]))
    if page_numbers != list(range(1, len(result) + 1)):
        raise SourceError('Reader page sequence is incomplete or duplicated')
    if not result:
        raise SourceError('Full-resolution reader images missing')
    return result


def catalogue(source, title_url):
    """Fetch the initial list and the same public continuation used by the reader UI."""
    with source.get(title_url) as response:
        soup = BeautifulSoup(response.content, 'html.parser')
    heading = soup.select_one('h1')
    if heading is None:
        raise SourceError('MangaBuff title heading missing')
    nodes = list(soup.select('a.chapters__item[href]'))
    manga, csrf = soup.select_one('.manga[data-id]'), soup.select_one('meta[name="csrf-token"]')
    if soup.select_one('.load-chapters-trigger') and (manga is None or csrf is None):
        raise SourceError('MangaBuff continuation parameters missing')
    if soup.select_one('.load-chapters-trigger') and manga and csrf:
        response = source.session.post('https://mangabuff.ru/chapters/load',
            data={'manga_id': manga['data-id']}, headers={'X-CSRF-TOKEN': csrf['content'],
                'X-Requested-With': 'XMLHttpRequest', 'Referer': title_url}, timeout=(15, 60))
        response.raise_for_status()
        fragment = response.json().get('content')
        if not isinstance(fragment, str):
            raise SourceError('MangaBuff continuation missing')
        nodes.extend(BeautifulSoup(fragment, 'html.parser').select('a.chapters__item[href]'))
    from .source import Chapter
    chapters = {}
    for a in nodes:
        target = urljoin(title_url, a['href'])
        match = re.fullmatch(re.escape(title_url) + r'/(\d+)/(\d+(?:\.\d+)?)/?', target)
        if match:
            chapters[target] = Chapter(target, 'Глава ' + match[2], match[1], match[2])
    if not chapters:
        raise SourceError('MangaBuff chapter catalogue empty')
    return heading.get_text(' ', strip=True), list(chapters.values())
