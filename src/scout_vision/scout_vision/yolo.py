"""Small YOLOv8 ONNX pre/post-processing helpers."""

import cv2
import numpy as np


def prepare_input(image, width, height):
    """Letterbox a BGR image and return an RGB NCHW float tensor."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('expected a BGR image with three channels')
    source_height, source_width = image.shape[:2]
    scale = min(width / source_width, height / source_height)
    resized_width = max(1, round(source_width * scale))
    resized_height = max(1, round(source_height * scale))
    resized = cv2.resize(image, (resized_width, resized_height))
    pad_x = (width - resized_width) // 2
    pad_y = (height - resized_height) // 2
    canvas = np.full((height, width, 3), 114, dtype=np.uint8)
    canvas[
        pad_y:pad_y + resized_height,
        pad_x:pad_x + resized_width,
    ] = resized
    tensor = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    tensor = np.ascontiguousarray(
        tensor.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, scale, (pad_x, pad_y)


def _nms(boxes, scores, threshold):
    order = np.asarray(scores).argsort()[::-1]
    boxes = np.asarray(boxes, dtype=np.float32)
    keep = []
    while order.size:
        current = int(order[0])
        keep.append(current)
        if order.size == 1:
            break
        remaining = order[1:]
        overlap_x1 = np.maximum(boxes[current, 0], boxes[remaining, 0])
        overlap_y1 = np.maximum(boxes[current, 1], boxes[remaining, 1])
        overlap_x2 = np.minimum(boxes[current, 2], boxes[remaining, 2])
        overlap_y2 = np.minimum(boxes[current, 3], boxes[remaining, 3])
        intersection = (
            np.maximum(0.0, overlap_x2 - overlap_x1)
            * np.maximum(0.0, overlap_y2 - overlap_y1)
        )
        current_area = (
            (boxes[current, 2] - boxes[current, 0])
            * (boxes[current, 3] - boxes[current, 1])
        )
        remaining_area = (
            (boxes[remaining, 2] - boxes[remaining, 0])
            * (boxes[remaining, 3] - boxes[remaining, 1])
        )
        union = current_area + remaining_area - intersection
        iou = np.divide(
            intersection,
            union,
            out=np.zeros_like(intersection),
            where=union > 0,
        )
        order = remaining[iou <= threshold]
    return keep


def decode_yolov8(
    output,
    labels,
    confidence_threshold,
    nms_threshold,
    image_shape,
    scale,
    padding,
):
    """Decode one Ultralytics YOLOv8 detection output."""
    predictions = np.asarray(output)
    if predictions.ndim == 3 and predictions.shape[0] == 1:
        predictions = predictions[0]
    if predictions.ndim != 2:
        raise ValueError(f'expected a 2D YOLO output, got {predictions.shape}')

    feature_count = len(labels) + 4
    if predictions.shape[0] == feature_count:
        predictions = predictions.T
    elif predictions.shape[1] != feature_count:
        raise ValueError(
            f'expected {feature_count} output features for {len(labels)} labels, '
            f'got {predictions.shape}')

    class_scores = predictions[:, 4:]
    class_indices = class_scores.argmax(axis=1)
    scores = class_scores[np.arange(len(predictions)), class_indices]
    source_height, source_width = image_shape
    pad_x, pad_y = padding
    candidates = []

    for row, class_index, score in zip(
            predictions, class_indices, scores):
        score = float(score)
        if not np.isfinite(score) or score < confidence_threshold:
            continue
        center_x, center_y, width, height = map(float, row[:4])
        x1 = np.clip((center_x - width / 2 - pad_x) / scale,
                     0.0, source_width)
        y1 = np.clip((center_y - height / 2 - pad_y) / scale,
                     0.0, source_height)
        x2 = np.clip((center_x + width / 2 - pad_x) / scale,
                     0.0, source_width)
        y2 = np.clip((center_y + height / 2 - pad_y) / scale,
                     0.0, source_height)
        if x2 <= x1 or y2 <= y1:
            continue
        candidates.append({
            'class_index': int(class_index),
            'class_id': labels[int(class_index)],
            'score': score,
            'box': (float(x1), float(y1), float(x2), float(y2)),
        })

    selected = []
    for class_index in sorted({item['class_index'] for item in candidates}):
        group = [
            item for item in candidates
            if item['class_index'] == class_index
        ]
        for index in _nms(
                [item['box'] for item in group],
                [item['score'] for item in group],
                nms_threshold):
            selected.append(group[index])
    return sorted(selected, key=lambda item: item['score'], reverse=True)
