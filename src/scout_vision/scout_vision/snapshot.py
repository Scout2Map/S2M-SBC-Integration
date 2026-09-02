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


# BGR, matches the crop's own box color so a viewer can tell at a glance
# that a full-frame box and a per-detection crop describe the same hit
_BOX_COLOR_BGR = (0, 64, 255)
_TEXT_COLOR_BGR = (255, 255, 255)


def draw_detections(
    image_rgb, detections, box_color=_BOX_COLOR_BGR,
    text_color=_TEXT_COLOR_BGR, thickness=2,
):
    """Return a copy of image_rgb with every detection's box and label drawn.

    Kept separate from encode_frame_jpeg() so the drawing step is unit
    testable on its own (no JPEG round-trip needed to check pixel content).
    Operates on a copy - the caller's original frame (e.g. the one also
    handed to encode_snapshot_jpeg() for the per-detection crops) is left
    untouched.
    """
    annotated = image_rgb.copy()
    height, width = annotated.shape[:2]
    for item in detections:
        x1, y1, x2, y2 = (int(round(v)) for v in item['box'])
        x1, x2 = sorted((max(0, min(x1, width)), max(0, min(x2, width))))
        y1, y2 = sorted((max(0, min(y1, height)), max(0, min(y2, height))))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, thickness)

        label = f"{item['class_id']} {item['score']:.2f}"
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        # label plate sits just above the box, or just below it if the box
        # touches the top edge, so the text never gets clipped off-frame
        label_y2 = y1 if y1 - text_h - baseline - 4 >= 0 else min(
            height, y2 + text_h + baseline + 4)
        label_y1 = label_y2 - text_h - baseline - 4
        cv2.rectangle(
            annotated, (x1, max(0, label_y1)), (min(width, x1 + text_w + 6), label_y2),
            box_color, -1)
        cv2.putText(
            annotated, label, (x1 + 3, label_y2 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1, cv2.LINE_AA)
    return annotated


def encode_frame_jpeg(image_rgb, max_width=480, jpeg_quality=55):
    """Downscale (if needed) and JPEG-encode a full RGB frame, no cropping.

    Meant for draw_detections()'s output - one annotated full-frame image
    per inference cycle, so an operator can see *where* in the shot a
    hazard was found instead of just the tight per-detection crop from
    encode_snapshot_jpeg(). max_width is independent of snapshot_max_size:
    a full frame is naturally much bigger than a single box crop, so it
    gets its own (larger) budget - tune it down further if the link to the
    web client is bandwidth constrained.
    """
    height, width = image_rgb.shape[:2]
    if width > max_width > 0:
        scale = max_width / width
        image_rgb = cv2.resize(
            image_rgb, (max_width, max(1, round(height * scale))))

    bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(
        '.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode('ascii')
