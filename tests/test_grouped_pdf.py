from PIL import Image
import pikepdf
from manhwa.grouped_pdf import write


def test_fragments_keep_original_bytes_order_and_tiny_tail(tmp_path):
    paths = []
    for index, (height, color) in enumerate([(100, 'red'), (2, 'blue')]):
        path = tmp_path / f'{index}.jpg'
        Image.new('RGB', (80, height), color).save(path)
        paths.append(path)
    target = tmp_path / 'chapter.pdf'
    write([paths], target)
    with pikepdf.open(target) as pdf:
        assert len(pdf.pages) == 1
        page = pdf.pages[0]
        assert list(page.MediaBox) == [0, 0, 80, 102]
        objects = page.Resources.XObject
        assert objects['/Im0'].read_raw_bytes() == paths[0].read_bytes()
        assert objects['/Im1'].read_raw_bytes() == paths[1].read_bytes()
        commands = page.Contents.read_bytes().decode()
        assert '100.00000000 0 2.00000000 cm /Im0' in commands
        assert '2.00000000 0 0.00000000 cm /Im1' in commands
