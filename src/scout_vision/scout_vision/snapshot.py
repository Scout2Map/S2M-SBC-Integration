"""Turn a detection bounding box into a small JPEG snapshot.

Kept separate from vision_node.py (like yolo.py) so the crop/encode math can
be unit tested without rclpy or a live camera - the node just wires this up
to whatever detections decode_yolov8() produced for the current frame.
"""

import base64

import cv2
import numpy as np


def crop_box(image, box, margin_ratio=0.15):
    """Return the region of `image` covered by an (x1, y1, x2, y2) box.

    Expands the box by margin_ratio on each side first - a tight crop on
    just the box often cuts off the context a human needs to tell a real
    detection from a false positive (e.g. "is that smoke or just fog on the
    lens"). Always clamped to the image bounds, and can return a zero-size
    crop for a box that falls entirely outside the image - callers should
    treat that as "no snapshot" rather than an error.
    """
    height, width = image.shape[:2]
    x1, y1, x2, y2 = box
    margin_x = (x2 - x1) * margin_ratio
    margin_y = (y2 - y1) * margin_ratio

    ix1 = int(np.clip(round(x1 - margin_x), 0, width))
    iy1 = int(np.clip(round(y1 - margin_y), 0, height))
    ix2 = int(np.clip(round(x2 + margin_x), 0, width))
    iy2 = int(np.clip(round(y2 + margin_y), 0, height))

    # a box degenerate to a single line/point still gets a 1px crop, as long
    # as there is room left in the image to grow into
    if ix2 <= ix1:
        ix2 = min(width, ix1 + 1)
    if iy2 <= iy1:
        iy2 = min(height, iy1 + 1)

    return image[iy1:iy2, ix1:ix2]


def encode_snapshot_jpeg(image_rgb, box, max_size=128, jpeg_quality=60,
                          margin_ratio=0.15):
    """Crop `box` out of an RGB image and return a small base64 JPEG string.

    The image the node hands in is already decoded to rgb8 (see
    _on_image()); this only needs to flip channel order for cv2.imencode.
    Downscaled to max_size on the longer side and JPEG-compressed at
    jpeg_quality to keep the payload small enough to ride along inside an
    /events JSON frame. Returns None for a degenerate crop (box entirely
    outside the frame) so the caller can skip attaching a snapshot instead
    of publishing a broken one.
    """
    crop = crop_box(image_rgb, box, margin_ratio)
    if crop.size == 0:
        return None

    crop_height, crop_width = crop.shape[:2]
    scale = max_size / max(crop_height, crop_width)
    if scale < 1.0:
        crop = cv2.resize(
            crop,
            (max(1, round(crop_width * scale)), max(1, round(crop_height * scale))),
        )

    bgr = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(
        '.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode('ascii')
