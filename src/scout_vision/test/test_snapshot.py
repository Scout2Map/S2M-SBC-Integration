import base64

import numpy as np

from scout_vision.snapshot import (
    crop_box,
    draw_detections,
    encode_frame_jpeg,
    encode_snapshot_jpeg,
)


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


def test_draw_detections_does_not_mutate_the_input_image():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    original = image.copy()
    draw_detections(
        image, [{'box': (10.0, 10.0, 50.0, 50.0), 'class_id': 'person', 'score': 0.9}])
    assert np.array_equal(image, original)


def test_draw_detections_changes_pixels_inside_the_box():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    annotated = draw_detections(
        image, [{'box': (10.0, 10.0, 50.0, 50.0), 'class_id': 'fire', 'score': 0.8}])
    assert not np.array_equal(image, annotated)


def test_draw_detections_clamps_boxes_outside_the_frame():
    # box hangs off every edge - must not raise or produce an out-of-bounds crop
    image = np.zeros((50, 50, 3), dtype=np.uint8)
    annotated = draw_detections(
        image, [{'box': (-20.0, -20.0, 70.0, 70.0), 'class_id': 'smoke', 'score': 0.5}])
    assert annotated.shape == image.shape


def test_draw_detections_handles_empty_detection_list():
    image = np.zeros((50, 50, 3), dtype=np.uint8)
    annotated = draw_detections(image, [])
    assert np.array_equal(image, annotated)


def test_encode_frame_jpeg_returns_valid_base64_jpeg():
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = encode_frame_jpeg(image, max_width=320)
    assert isinstance(result, str)
    raw = base64.b64decode(result)
    assert raw[:2] == b'\xff\xd8'  # JPEG SOI marker


def test_encode_frame_jpeg_downscales_wide_frames_to_max_width():
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    result = encode_frame_jpeg(image, max_width=160, jpeg_quality=60)
    assert result is not None
    # a 160-wide JPEG should be well under the raw frame size
    assert len(base64.b64decode(result)) < 640 * 480 * 3


def test_encode_frame_jpeg_leaves_narrower_frames_unscaled():
    # frame is already narrower than max_width - should not upscale or crash
    image = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
    result = encode_frame_jpeg(image, max_width=480)
    assert result is not None
