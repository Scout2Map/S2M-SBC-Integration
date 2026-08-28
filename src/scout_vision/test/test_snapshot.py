import base64

import numpy as np

from scout_vision.snapshot import crop_box, encode_snapshot_jpeg


def test_crop_box_expands_by_margin():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    # box is 20x20 centered at (50, 50); margin_ratio 0.5 grows it by 10px
    # on every side, so the crop should end up 40x40
    crop = crop_box(image, (40.0, 40.0, 60.0, 60.0), margin_ratio=0.5)
    assert crop.shape[:2] == (40, 40)


def test_crop_box_clamps_to_image_edges():
    image = np.zeros((50, 50, 3), dtype=np.uint8)
    crop = crop_box(image, (0.0, 0.0, 10.0, 10.0), margin_ratio=1.0)
    assert crop.shape[0] <= 50 and crop.shape[1] <= 50
    assert crop.shape[0] > 0 and crop.shape[1] > 0


def test_crop_box_handles_zero_width_box_inside_image():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    crop = crop_box(image, (50.0, 50.0, 50.0, 50.0), margin_ratio=0.0)
    assert crop.shape[0] >= 1 and crop.shape[1] >= 1


def test_crop_box_returns_empty_for_box_entirely_outside_image():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    crop = crop_box(image, (200.0, 200.0, 210.0, 210.0))
    assert crop.size == 0


def test_encode_snapshot_jpeg_returns_valid_base64_jpeg():
    image = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
    result = encode_snapshot_jpeg(image, (10.0, 10.0, 190.0, 150.0), max_size=64)
    assert isinstance(result, str)
    raw = base64.b64decode(result)
    assert raw[:2] == b'\xff\xd8'  # JPEG SOI marker


def test_encode_snapshot_jpeg_downscales_to_max_size():
    image = np.random.randint(0, 255, (400, 400, 3), dtype=np.uint8)
    result = encode_snapshot_jpeg(
        image, (0.0, 0.0, 400.0, 400.0), max_size=32, margin_ratio=0.0)
    assert result is not None
    # a downscaled 32x32 JPEG should be well under the raw crop size
    assert len(base64.b64decode(result)) < 400 * 400 * 3


def test_encode_snapshot_jpeg_returns_none_for_box_outside_image():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    result = encode_snapshot_jpeg(image, (200.0, 200.0, 210.0, 210.0))
    assert result is None
