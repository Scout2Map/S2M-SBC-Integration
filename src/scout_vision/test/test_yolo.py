import numpy as np

from scout_vision.yolo import decode_yolov8, prepare_input


def test_letterbox_and_decode_suppress_overlapping_boxes():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    tensor, scale, padding = prepare_input(image, 640, 640)
    output = np.array([[
        [320.0, 330.0],
        [320.0, 330.0],
        [320.0, 320.0],
        [160.0, 160.0],
        [0.90, 0.80],
        [0.10, 0.20],
    ]], dtype=np.float32)

    detections = decode_yolov8(
        output, ['person', 'smoke'], 0.5, 0.45,
        image.shape[:2], scale, padding)

    assert tensor.shape == (1, 3, 640, 640)
    assert padding == (0, 160)
    assert len(detections) == 1
    assert detections[0]['class_id'] == 'person'
    assert np.allclose(detections[0]['box'], (50.0, 25.0, 150.0, 75.0))
