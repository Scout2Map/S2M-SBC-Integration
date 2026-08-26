"""Small YOLOv8 ONNX pre/post-processing helpers."""

import cv2
import numpy as np


def prepare_input(image, width, height):
    """Letterbox an RGB image and return an RGB NCHW float tensor."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('expected an image with three channels')
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
    # image is already rgb8 from node conversion
    tensor = np.ascontiguousarray(
        canvas.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, scale, (pad_x, pad_y)


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
    # use opencv c++ accelerated nms implementation
    for class_index in sorted({item['class_index'] for item in candidates}):
        group = [
            item for item in candidates
            if item['class_index'] == class_index
        ]
        # convert xyxy format to xywh format for cv2.dnn.nmsboxes
        cv_boxes = [
            [
                item['box'][0],
                item['box'][1],
                item['box'][2] - item['box'][0],
                item['box'][3] - item['box'][1],
            ]
            for item in group
        ]
        scores = [item['score'] for item in group]
        indices = cv2.dnn.NMSBoxes(
            cv_boxes,
            scores,
            score_threshold=confidence_threshold,
            nms_threshold=nms_threshold,
        )
        if len(indices) > 0:
            for idx in np.asarray(indices).flatten():
                selected.append(group[int(idx)])

    return sorted(selected, key=lambda item: item['score'], reverse=True)