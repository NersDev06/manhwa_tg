import subprocess
import sys
from pathlib import Path

import img2pdf

MAX_PDF_BYTES = 45_000_000


def build_chapter(source, chapter_url, folder: Path):
    """Decode one source image at a time; embed disk-backed JPEG tiles in PDFs."""
    folder.mkdir(parents=True, exist_ok=True)
    pages = source.pages(chapter_url)
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
        prefix = f'page-{index:05d}'
        subprocess.run([sys.executable, '-m', 'manhwa.images', str(raw), str(folder), prefix],
                       check=True, capture_output=True, timeout=120)
        tiles.extend(sorted(folder.glob(prefix + '-*.jpg')))
        raw.unlink()
    outputs = []

    def write_group(group):
        path = folder / f'part-{len(outputs) + 1:03d}.pdf'
        with path.open('wb') as out:
            img2pdf.convert([str(p) for p in group], outputstream=out)
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
    for tile in tiles:
        if group and size + tile.stat().st_size > 38_000_000:
            write_group(group)
            group, size = [], 0
        group.append(tile)
        size += tile.stat().st_size
    if group:
        write_group(group)
    return outputs, {'source_images': len(pages), 'pdf_pages': len(tiles),
                     'parts': len(outputs), 'bytes': sum(p.stat().st_size for p in outputs)}
