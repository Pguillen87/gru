from io import BytesIO

from PIL import Image, ImageDraw

from modal_service.image_processing import POSE_BACKGROUND, master_transparency_qc, normalize_pose_presentation, remove_connected_flat_background, transparency_ratio


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
    qc = master_transparency_qc(normalized)
    assert qc["status"] == "passed"
    assert qc["alpha_ratio"] > 0


def test_alpha_qc_rejects_a_solid_master_without_mutating_it():
    image = Image.new("RGBA", (32, 32), (80, 45, 34, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    qc = master_transparency_qc(source.getvalue())

    assert qc["status"] == "failed"
    assert "ALPHA_INSUFFICIENT" in qc["safe_reasons"]


def test_pose_presentation_replaces_checkerboard_with_one_editorial_background():
    image = Image.new("RGBA", (32, 32), (28, 28, 28, 255))
    drawer = ImageDraw.Draw(image)
    for y in range(0, 32, 4):
        for x in range(0, 32, 4):
            if (x // 4 + y // 4) % 2:
                drawer.rectangle((x, y, x + 3, y + 3), fill=(92, 92, 92, 255))
    drawer.ellipse((10, 7, 21, 25), fill=(210, 120, 70, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    result = Image.open(BytesIO(normalize_pose_presentation(source.getvalue()))).convert("RGBA")

    assert result.size == (1024, 1024)
    assert result.getpixel((0, 0)) == POSE_BACKGROUND
    assert result.getpixel((512, 512)) != POSE_BACKGROUND
