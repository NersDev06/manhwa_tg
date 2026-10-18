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
