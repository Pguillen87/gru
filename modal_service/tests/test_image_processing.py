from io import BytesIO

from PIL import Image

from modal_service.image_processing import remove_connected_flat_background, transparency_ratio


def test_flat_border_background_becomes_transparent_without_erasing_subject():
    image = Image.new("RGB", (64, 64), (235, 231, 222))
    for x in range(20, 44):
        for y in range(16, 56):
            image.putpixel((x, y), (120, 55, 30))
    source = BytesIO()
    image.save(source, format="PNG")

    normalized = remove_connected_flat_background(source.getvalue())
    result = Image.open(BytesIO(normalized)).convert("RGBA")

    assert result.getpixel((0, 0))[3] == 0
    assert result.width < 64
    assert result.height < 64
    assert result.getchannel("A").getbbox() is not None
    assert transparency_ratio(normalized) > 0.1
