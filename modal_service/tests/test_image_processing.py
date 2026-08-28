from io import BytesIO

from PIL import Image, ImageDraw

from modal_service.image_processing import POSE_BACKGROUND, master_transparency_qc, normalize_pose_presentation, pose_set_visual_consistency_qc, pose_transparency_qc, remove_connected_flat_background, transparency_ratio


def _pose(role: str, *, width=1024, height=1024, bbox=(120, 80, 850, 940), foreground_ratio=0.24):
    return {
        "runtimeRole": role,
        "qc": {
            "status": "passed",
            "width": width,
            "height": height,
            "bounding_box": list(bbox),
            "foreground_ratio": foreground_ratio,
        },
    }


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
    assert "SCALE_MISMATCH" in result["safe_reasons"]
    assert "CENTER_OFFSET_MISMATCH" in result["safe_reasons"]


def test_pose_set_visual_consistency_rejects_excessive_width_and_occupied_area():
    result = pose_set_visual_consistency_qc([
        _pose("normal"),
        _pose("listening", bbox=(130, 80, 860, 940)),
        _pose("transcribing", bbox=(0, 30, 1024, 994)),
    ])

    assert result["status"] == "failed"
    assert "SCALE_WIDTH_MISMATCH" in result["safe_reasons"]
    assert "OCCUPANCY_MISMATCH" in result["safe_reasons"]


def test_pose_set_visual_consistency_rejects_a_misaligned_foot_baseline():
    result = pose_set_visual_consistency_qc([
        _pose("normal"),
        _pose("listening", bbox=(125, 85, 855, 945)),
        _pose("transcribing", bbox=(120, 80, 850, 890)),
    ])

    assert result["status"] == "failed"
    assert "FOOT_BASE_MISMATCH" in result["safe_reasons"]


def test_pose_set_visual_consistency_rejects_a_dominant_scene_but_allows_a_small_prop():
    dominant_scene = pose_set_visual_consistency_qc([
        _pose("normal", bbox=(329, 51, 698, 996), foreground_ratio=0.220186),
        _pose("listening", bbox=(298, 48, 707, 994), foreground_ratio=0.214193),
        _pose("transcribing", bbox=(85, 100, 939, 944), foreground_ratio=0.429605),
    ])
    small_prop = pose_set_visual_consistency_qc([
        _pose("normal"),
        _pose("listening", bbox=(125, 85, 855, 945), foreground_ratio=0.27),
        _pose("transcribing", bbox=(115, 82, 845, 942), foreground_ratio=0.28),
    ])

    assert dominant_scene["status"] == "failed"
    assert "SCENE_DOMINANT" in dominant_scene["safe_reasons"]
    assert small_prop["status"] == "passed"


def test_current_smoke_transcribing_regression_is_rejected_while_normal_and_listening_match():
    result = pose_set_visual_consistency_qc([
        _pose("normal", bbox=(329, 51, 698, 996), foreground_ratio=0.220186),
        _pose("listening", bbox=(298, 48, 707, 994), foreground_ratio=0.214193),
        _pose("transcribing", bbox=(85, 100, 939, 944), foreground_ratio=0.429605),
    ])

    assert result["status"] == "failed"
    assert {"SCALE_WIDTH_MISMATCH", "OCCUPANCY_MISMATCH", "SCENE_DOMINANT"} <= set(result["safe_reasons"])


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


def _editorial_pose_with_enclosed_background():
    image = Image.new("RGBA", (128, 128), (253, 243, 218, 255))
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((38, 20, 90, 64), fill=(56, 82, 121, 255))
    drawer.rectangle((42, 60, 58, 110), fill=(56, 82, 121, 255))
    drawer.rectangle((70, 60, 86, 110), fill=(56, 82, 121, 255))
    drawer.rectangle((18, 44, 34, 68), fill=(252, 250, 245, 255))
    drawer.rectangle((92, 42, 108, 74), fill=(216, 158, 128, 255))
    drawer.ellipse((30, 108, 100, 120), fill=(218, 198, 161, 255))
    source = BytesIO()
    image.save(source, format="PNG")
    return source.getvalue()


def test_editorial_background_inside_legs_and_at_feet_is_removed_but_paper_skin_and_clothing_stay():
    normalized = remove_connected_flat_background(_editorial_pose_with_enclosed_background(), crop=False)
    image = Image.open(BytesIO(normalized)).convert("RGBA")

    assert image.getpixel((64, 82))[3] == 0
    assert image.getpixel((64, 116))[3] == 0
    assert image.getpixel((26, 56))[:3] == (252, 250, 245)
    assert image.getpixel((100, 58))[:3] == (216, 158, 128)
    assert image.getpixel((50, 42))[:3] == (56, 82, 121)
    assert pose_transparency_qc(normalized)["status"] == "passed"


def test_qc_rejects_clean_outer_alpha_when_internal_editorial_background_remains():
    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((24, 18, 72, 76), fill=(56, 82, 121, 255))
    drawer.rectangle((43, 42, 53, 67), fill=(253, 243, 218, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    rejected = pose_transparency_qc(source.getvalue())
    corrected = pose_transparency_qc(remove_connected_flat_background(source.getvalue(), crop=False))

    assert rejected["status"] == "failed"
    assert "INTERNAL_BACKGROUND_RESIDUE" in rejected["safe_reasons"]
    assert rejected["internal_background_components"] == 1
    assert rejected["internal_background_area"] > 12
    assert rejected["largest_internal_background_component"] > 12
    assert corrected["status"] == "passed"
    assert corrected["internal_background_components"] == 0


def test_editorial_background_between_arm_and_torso_is_removed():
    image = Image.new("RGBA", (96, 96), (253, 243, 218, 255))
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((30, 20, 66, 74), fill=(56, 82, 121, 255))
    drawer.rectangle((18, 34, 32, 62), fill=(216, 158, 128, 255))
    drawer.rectangle((34, 34, 40, 62), fill=(253, 243, 218, 255))
    source = BytesIO()
    image.save(source, format="PNG")

    normalized = Image.open(BytesIO(remove_connected_flat_background(source.getvalue(), crop=False))).convert("RGBA")

    assert normalized.getpixel((36, 48))[3] == 0
    assert normalized.getpixel((24, 48))[:3] == (216, 158, 128)


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
