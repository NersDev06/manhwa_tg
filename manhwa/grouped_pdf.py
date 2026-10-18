"""Place a reader's JPEG fragments on their original continuous PDF canvas.
JPEG bytes remain compressed; no chapter-sized bitmap is allocated.
"""
from PIL import Image
import pikepdf
from .source import SourceError


def write(sheets, target):
    with pikepdf.Pdf.new() as pdf:
        for sheet in sheets:
            descriptions = []
            for path in sheet:
                with Image.open(path) as image:
                    if image.format != 'JPEG' or image.mode not in ('RGB', 'L') or image.getexif().get(274, 1) != 1:
                        raise SourceError('Unsupported JPEG fragment presentation')
                    descriptions.append((path, image.width, image.height, image.mode))
            widths = {width for _, width, _, _ in descriptions}
            if len(widths) != 1:
                raise SourceError('Reader fragments have inconsistent widths')
            width = widths.pop()
            height = sum(h for _, _, h, _ in descriptions)
            scale = min(1.0, 14000 / max(width, height))
            page = pdf.add_blank_page(page_size=(max(3, width * scale), max(3, height * scale)))
            objects = pikepdf.Dictionary()
            commands, top = [], height
            for index, (path, w, h, mode) in enumerate(descriptions):
                top -= h
                image = pdf.make_stream(path.read_bytes())
                image.Type = pikepdf.Name.XObject
                image.Subtype = pikepdf.Name.Image
                image.Width, image.Height = w, h
                image.ColorSpace = pikepdf.Name.DeviceRGB if mode == 'RGB' else pikepdf.Name.DeviceGray
                image.BitsPerComponent = 8
                image.Filter = pikepdf.Name.DCTDecode
                name = '/Im' + str(index)
                objects[name] = image
                commands.append(f'q {w * scale:.8f} 0 0 {h * scale:.8f} 0 {top * scale:.8f} cm {name} Do Q')
            page.Resources = pikepdf.Dictionary(XObject=objects)
            page.Contents = pdf.make_stream(('\n'.join(commands) + '\n').encode('ascii'))
        pdf.save(target)
