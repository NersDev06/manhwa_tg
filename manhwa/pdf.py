import subprocess
import sys
import tempfile
import requests
from pathlib import Path

import img2pdf
from PIL import Image, UnidentifiedImageError
from .source import SourceError

MAX_PDF_BYTES = 49_000_000


def build_chapter(source, chapter_url, folder: Path):
    candidates = getattr(source, 'candidates', None)
    if not callable(candidates):
        return _build_chapter(source, chapter_url, folder)
    folder.mkdir(parents=True, exist_ok=True)
    for candidate in candidates(chapter_url):
        try:
            with tempfile.TemporaryDirectory(prefix='.candidate-', dir=folder) as attempt:
                attempt = Path(attempt)
                pages = source.provider_pages(candidate)
                paths, stats = _build_chapter(source, candidate.url, attempt, pages=pages)
                names = [p.name for p in paths]
                for pattern in ('page-*-*.jpg', 'part-*.pdf', 'original-*', 'preview.jpg'):
                    for previous in folder.glob(pattern):
                        previous.unlink()
                # Promote an entire validated chapter. Never combine pages from different sites.
                for path in attempt.iterdir():
                    path.replace(folder / path.name)
                stats.update(source=candidate.name, source_chapter_url=candidate.url)
                return [folder / name for name in names], stats
        except (requests.RequestException, SourceError, ValueError, RuntimeError,
                subprocess.SubprocessError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            source.reject(candidate, exc)
    raise SourceError('No source could produce a readable complete chapter')


def _build_chapter(source, chapter_url, folder: Path, pages=None):
    """Decode one source image at a time; embed disk-backed JPEG tiles in PDFs."""
    folder.mkdir(parents=True, exist_ok=True)
    pages = pages if pages is not None else source.pages(chapter_url)
    tiles = []
    for index, url in enumerate(pages):
        raw = folder / f'original-{index}'
        with source.get(url, stream=True) as response, raw.open('wb') as out:
            size = 0
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > 30_000_000:
                    raise ValueError('Source image exceeds 30 MB')
                out.write(chunk)
        with Image.open(raw) as image:
            if image.width < 320 and image.height > 1000:
                raise ValueError('Reader supplied a low-resolution long strip; refusing unreadable PDF')
        prefix = f'page-{index:05d}'
        result = subprocess.run([sys.executable, '-m', 'manhwa.images', str(raw), str(folder), prefix],
                       capture_output=True, timeout=120)
        if result.returncode:
            # Only the final exception line; no image URLs or response bodies.
            reason = result.stderr.decode('utf-8', errors='replace').strip().splitlines()[-1:]
            raise RuntimeError('Image conversion: ' + (' '.join(reason))[:250])
        if callable(getattr(source, 'progress', None)):
            source.progress(index + 1, len(pages))
        tiles.extend(sorted(folder.glob(prefix + '-*.jpg')))
        raw.unlink()
    counts = getattr(pages, 'groups', None)
    sheets = []
    if counts is not None:
        if sum(counts) != len(tiles) or any(n <= 0 for n in counts):
            raise SourceError('Reader fragment grouping does not match downloaded images')
        cursor = 0
        for count in counts:
            sheets.append(tiles[cursor:cursor + count])
            cursor += count
    else:
        sheets = [[tile] for tile in tiles]
    outputs = []

    def write_group(group):
        path = folder / f'part-{len(outputs) + 1:03d}.pdf'
        if counts is not None:
            from .grouped_pdf import write
            write(group, path)
        else:
            with path.open('wb') as out:
                img2pdf.convert([str(p) for sheet in group for p in sheet], outputstream=out)
        if path.stat().st_size > MAX_PDF_BYTES:
            path.unlink()
            if len(group) == 1:
                raise ValueError('One PDF page exceeds upload limit')
            mid = len(group) // 2
            write_group(group[:mid])
            write_group(group[mid:])
        else:
            outputs.append(path)

    group, size = [], 0
    for sheet in sheets:
        sheet_size = sum(tile.stat().st_size for tile in sheet)
        if group and size + sheet_size > 45_000_000:
            write_group(group)
            group, size = [], 0
        group.append(sheet)
        size += sheet_size
    if group:
        write_group(group)
    return outputs, {'source_images': len(pages), 'pdf_pages': len(sheets),
                     'parts': len(outputs), 'bytes': sum(p.stat().st_size for p in outputs)}
