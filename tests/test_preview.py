from PIL import Image, ImageDraw
from manhwa.preview import crop_preview


def test_preview_removes_blank_edges_and_keeps_square(tmp_path):
    image=Image.new('RGB',(400,1200),'white')
    ImageDraw.Draw(image).rectangle((0,450,399,849),fill=(120,30,50))
    raw=tmp_path/'raw.png';image.save(raw)
    output=crop_preview(raw,tmp_path/'preview.jpg')
    with Image.open(output) as result:
        assert abs(result.width-result.height) <= 5
        assert result.getpixel((result.width//2,0))[0] < 200
        assert result.getpixel((result.width//2,result.height-1))[0] < 200


def test_rectangular_panel_preserved_without_zoom(tmp_path):
    image=Image.new('RGB',(600,1400),'white')
    ImageDraw.Draw(image).rectangle((40,300,559,1099),fill=(120,30,50))
    raw=tmp_path/'raw.png';image.save(raw)
    output=crop_preview(raw,tmp_path/'preview.jpg')
    with Image.open(output) as result:
        assert abs(result.width-520)<=5
        assert abs(result.height-800)<=10
        assert result.height > result.width


def test_black_padding_also_separates_full_panels(tmp_path):
    image=Image.new('RGB',(600,1800),'black')
    ImageDraw.Draw(image).rectangle((0,500,599,1299),fill=(120,30,50))
    raw=tmp_path/'black.png';image.save(raw)
    output=crop_preview(raw,tmp_path/'preview.jpg')
    with Image.open(output) as result:
        assert result.width==600
        assert abs(result.height-800)<=10
