from io import BytesIO

from PIL import Image, ImageDraw

from modal_service.image_processing import POSE_BACKGROUND, master_transparency_qc, normalize_pose_presentation, pose_set_visual_consistency_qc, pose_transparency_qc, remove_connected_flat_background, transparency_ratio


def _pose(role: str, *, width=1024, height=1024, bbox=(120, 80, 850, 940)):
    return {"runtimeRole": role, "qc": {"status": "passed", "width": width, "height": height, "bounding_box": list(bbox)}}


def test_pose_set_visual_consistency_accepts_a_full_body_set_with_a_shared_frame():
    result = pose_set_visual_consistency_qc([
        _pose("normal"),
        _pose("listening", bbox=(125, 85, 855, 945)),
        _pose("transcribing", bbox=(115, 82, 845, 942)),
    ])
    assert result["status"] == "passed"


def test_pose_set_visual_consistency_rejects_camera_and_frame_drift():
    result = pose_set_visual_consistency_qc([
        _pose("normal"),
        _pose("listening", width=640, height=640, bbox=(0, 5, 640, 635)),
        _pose("transcribing", bbox=(320, 80, 1000, 940)),
    ])
    assert result["status"] == "failed"
    assert "CANVAS_DIMENSIONS_MISMATCH" in result["safe_reasons"]
    assert "FRAME_CROP_RISK" in result["safe_reasons"]
    assert "CENTER_OFFSET_MISMATCH" in result["safe_reasons"]


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


def test_editorial_pose_background_removal_keeps_a_subject_touching_the_canvas_edge():
    image = Image.new("RGBA", (96, 96), (253, 243, 218, 255))
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((0, 32, 40, 88), fill=(56, 82, 121, 255))
    drawer.ellipse((32, 18, 68, 56), fill=(216, 158, 128, 255))
    image.putpixel((90, 90), (253, 243, 218, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    normalized = remove_connected_flat_background(source.getvalue())
    result = Image.open(BytesIO(normalized)).convert("RGBA")
    qc = pose_transparency_qc(normalized)

    assert result.getpixel((0, 0))[3] == 0
    assert qc["status"] == "passed"
    assert qc["border_opaque_ratio"] == 0


def test_editorial_pose_background_removal_drops_tiny_disconnected_noise():
    image = Image.new("RGBA", (96, 96), (253, 243, 218, 255))
    drawer = ImageDraw.Draw(image)
    drawer.ellipse((28, 18, 68, 76), fill=(56, 82, 121, 255))
    image.putpixel((84, 84), (56, 82, 121, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    normalized = remove_connected_flat_background(source.getvalue())
    qc = pose_transparency_qc(normalized)

    assert qc["status"] == "passed"
    assert qc["component_count"] == 1


def test_editorial_pose_background_removal_drops_detached_cream_floor_flecks():
    image = Image.new("RGBA", (128, 128), (253, 243, 218, 255))
    drawer = ImageDraw.Draw(image)
    drawer.ellipse((40, 20, 88, 108), fill=(56, 82, 121, 255))
    drawer.ellipse((18, 112, 32, 120), fill=(231, 216, 183, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    normalized = remove_connected_flat_background(source.getvalue())
    qc = pose_transparency_qc(normalized)

    assert qc["status"] == "passed"
    assert qc["component_count"] == 1


def test_alpha_qc_rejects_a_solid_master_without_mutating_it():
    image = Image.new("RGBA", (32, 32), (80, 45, 34, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    qc = master_transparency_qc(source.getvalue())

    assert qc["status"] == "failed"
    assert "ALPHA_INSUFFICIENT" in qc["safe_reasons"]


def test_alpha_qc_reports_hash_bbox_components_and_rejects_disconnected_noise():
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((18, 18, 44, 48), fill=(80, 45, 34, 255))
    image.putpixel((2, 2), (80, 45, 34, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    qc = pose_transparency_qc(source.getvalue())

    assert qc["format"] == "PNG" and qc["mode"] == "RGBA"
    assert len(qc["sha256"]) == 64
    assert qc["bounding_box"] == [2, 2, 45, 49]
    assert qc["component_count"] == 2
    assert qc["status"] == "failed"
    assert "DISCONNECTED_NOISE" in qc["safe_reasons"]


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
