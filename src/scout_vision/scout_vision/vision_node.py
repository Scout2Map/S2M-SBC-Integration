"""ROS 2 image-to-detection wrapper for a YOLOv8 ONNX model."""

from collections import deque
import hashlib
import json
from pathlib import Path
import time

import cv2
from cv_bridge import CvBridge, CvBridgeError
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    qos_profile_sensor_data,
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from scout_vision.snapshot import encode_snapshot_jpeg
from scout_vision.yolo import decode_yolov8, prepare_input
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import (
    Detection2D,
    Detection2DArray,
    ObjectHypothesisWithPose,
    VisionInfo,
)


class VisionNode(Node):
    """Run bounded-rate inference while preserving the camera timestamp."""

    def __init__(self):
        super().__init__('scout_vision')
        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('detections_topic', '/vision/detections')
        self.declare_parameter('diagnostics_topic', '/diagnostics')
        self.declare_parameter('vision_info_topic', '/vision/info')
        self.declare_parameter('model_path', '')
        self.declare_parameter('labels_path', '')
        self.declare_parameter('input_width', 640)
        self.declare_parameter('input_height', 640)
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('nms_threshold', 0.45)
        self.declare_parameter('max_fps', 5.0)
        self.declare_parameter('frame_timeout_s', 2.0)

        # Small crop of each detection's bounding box, JPEG+base64 in a JSON
        # side topic, so a human can visually confirm a hazard without SSH-ing
        # into the robot. Off by default is not an option here - a wrongly
        # confirmed 'person_in_danger' with no way to check the frame is
        # worse than the extra CPU cost, so this defaults to enabled and only
        # runs when a frame actually has detections to crop.
        self.declare_parameter('snapshot_enabled', True)
        self.declare_parameter('snapshot_topic', '/vision/snapshots')
        self.declare_parameter('snapshot_max_size', 128)
        self.declare_parameter('snapshot_jpeg_quality', 60)
        self.declare_parameter('snapshot_margin_ratio', 0.15)

        gp = self.get_parameter
        self._input_width = int(gp('input_width').value)
        self._input_height = int(gp('input_height').value)
        self._confidence = float(gp('confidence_threshold').value)
        self._nms = float(gp('nms_threshold').value)
        max_fps = float(gp('max_fps').value)
        self._minimum_period = 1.0 / max_fps if max_fps > 0 else 0.0
        self._frame_timeout = max(0.1, float(gp('frame_timeout_s').value))

        self._snapshot_enabled = bool(gp('snapshot_enabled').value)
        self._snapshot_max_size = int(gp('snapshot_max_size').value)
        self._snapshot_jpeg_quality = int(gp('snapshot_jpeg_quality').value)
        self._snapshot_margin_ratio = float(gp('snapshot_margin_ratio').value)

        self._bridge = CvBridge()
        self._net = None
        self._labels = []
        self._model_hash = ''
        self._model_error = ''
        self._inference_error = ''
        self._last_frame_mono = None
        self._last_inference_mono = None
        self._latencies_ms = deque(maxlen=100)
        self._sequence = 0

        self._detections_pub = self.create_publisher(
            Detection2DArray,
            str(gp('detections_topic').value),
            10,
        )
        self._diagnostics_pub = self.create_publisher(
            DiagnosticArray,
            str(gp('diagnostics_topic').value),
            10,
        )
        info_qos = QoSProfile(depth=1)
        info_qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        info_qos.reliability = QoSReliabilityPolicy.RELIABLE
        self._info_pub = self.create_publisher(
            VisionInfo,
            str(gp('vision_info_topic').value),
            info_qos,
        )
        self._snapshot_pub = self.create_publisher(
            String,
            str(gp('snapshot_topic').value),
            10,
        )

        self._load_model(
            str(gp('model_path').value),
            str(gp('labels_path').value),
        )
        self.create_subscription(
            Image,
            str(gp('image_topic').value),
            self._on_image,
            qos_profile_sensor_data,
        )
        self.create_timer(1.0, self._publish_diagnostics)

    def _load_model(self, model_value, labels_value):
        try:
            model_path = Path(model_value).expanduser()
            labels_path = Path(labels_value).expanduser()
            if not model_value or not model_path.is_file():
                raise ValueError(f'model file not found: {model_value or "<empty>"}')
            if not labels_value or not labels_path.is_file():
                raise ValueError(
                    f'labels file not found: {labels_value or "<empty>"}')
            self._labels = [
                line.strip()
                for line in labels_path.read_text(encoding='utf-8').splitlines()
                if line.strip()
            ]
            if not self._labels:
                raise ValueError('labels file is empty')
            if self._input_width <= 0 or self._input_height <= 0:
                raise ValueError('input dimensions must be positive')

            self._net = cv2.dnn.readNetFromONNX(str(model_path))
            digest = hashlib.sha256()
            with model_path.open('rb') as model_file:
                for chunk in iter(lambda: model_file.read(1024 * 1024), b''):
                    digest.update(chunk)
            self._model_hash = digest.hexdigest()

            info = VisionInfo()
            info.header.stamp = self.get_clock().now().to_msg()
            info.method = f'yolov8-onnx:{model_path.name}:{self._model_hash}'
            info.database_location = str(labels_path)
            info.database_version = int(self._model_hash[:8], 16) & 0x7fffffff
            self._info_pub.publish(info)
            self.get_logger().info(
                f'loaded {model_path.name} ({len(self._labels)} classes, '
                f'sha256={self._model_hash})')
        except (OSError, ValueError, cv2.error) as exc:
            self._model_error = str(exc)
            self.get_logger().error(self._model_error)

    def _on_image(self, message):
        now = time.monotonic()
        self._last_frame_mono = now
        if self._net is None:
            return
        if (
            self._last_inference_mono is not None
            and now - self._last_inference_mono < self._minimum_period
        ):
            return
        self._last_inference_mono = now

        started = time.perf_counter()
        try:
            # receive native rgb8 image without extra format conversion
            image = self._bridge.imgmsg_to_cv2(
                message, desired_encoding='rgb8')
            tensor, scale, padding = prepare_input(
                image, self._input_width, self._input_height)
            self._net.setInput(tensor)
            detections = decode_yolov8(
                self._net.forward(),
                self._labels,
                self._confidence,
                self._nms,
                image.shape[:2],
                scale,
                padding,
            )
            output = Detection2DArray()
            output.header = message.header
            self._sequence += 1
            for index, item in enumerate(detections):
                x1, y1, x2, y2 = item['box']
                detection = Detection2D()
                detection.header = message.header
                detection.id = f'{self._sequence}:{index}'
                detection.bbox.center.position.x = (x1 + x2) / 2
                detection.bbox.center.position.y = (y1 + y2) / 2
                detection.bbox.size_x = x2 - x1
                detection.bbox.size_y = y2 - y1
                hypothesis = ObjectHypothesisWithPose()
                hypothesis.hypothesis.class_id = item['class_id']
                hypothesis.hypothesis.score = item['score']
                detection.results.append(hypothesis)
                output.detections.append(detection)
            self._detections_pub.publish(output)
            if self._snapshot_enabled and detections:
                self._publish_snapshots(image, message.header, detections)
            self._inference_error = ''
            self._latencies_ms.append(
                (time.perf_counter() - started) * 1000.0)
        except (ValueError, cv2.error, CvBridgeError, TypeError) as exc:
            self._inference_error = str(exc)
            self.get_logger().error(f'vision inference failed: {exc}')

    def _publish_snapshots(self, image, header, detections):
        """Crop+encode each detection's box and publish them as one frame.

        detection_id here must match the id scheme used when building the
        Detection2DArray above (f'{sequence}:{index}') so scout2map_event can
        correlate a snapshot with the detection it belongs to. A crop that
        fails to encode (degenerate box) is just skipped, not fatal to the
        rest of the frame.
        """
        snapshots = []
        for index, item in enumerate(detections):
            jpeg_b64 = encode_snapshot_jpeg(
                image,
                item['box'],
                max_size=self._snapshot_max_size,
                jpeg_quality=self._snapshot_jpeg_quality,
                margin_ratio=self._snapshot_margin_ratio,
            )
            if jpeg_b64 is None:
                continue
            snapshots.append({
                'detection_id': f'{self._sequence}:{index}',
                'class_id': item['class_id'],
                'jpeg_b64': jpeg_b64,
            })

        if not snapshots:
            return

        payload = {
            'stamp_sec': header.stamp.sec,
            'stamp_nanosec': header.stamp.nanosec,
            'frame_id': header.frame_id,
            'snapshots': snapshots,
        }
        self._snapshot_pub.publish(String(data=json.dumps(payload)))

    def _publish_diagnostics(self):
        now = time.monotonic()
        frame_age = (
            None if self._last_frame_mono is None
            else now - self._last_frame_mono
        )
        if self._model_error:
            level = DiagnosticStatus.ERROR
            summary = self._model_error
        elif self._inference_error:
            level = DiagnosticStatus.ERROR
            summary = self._inference_error
        elif frame_age is None:
            level = DiagnosticStatus.WARN
            summary = 'waiting for camera frames'
        elif frame_age > self._frame_timeout:
            level = DiagnosticStatus.STALE
            summary = f'camera frame stale ({frame_age:.2f}s)'
        else:
            level = DiagnosticStatus.OK
            summary = 'inference ready'

        latencies = sorted(self._latencies_ms)
        p95 = (
            latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
            if latencies else 0.0
        )
        status = DiagnosticStatus()
        status.level = level
        status.name = 'scout_vision/inference'
        status.message = summary
        status.hardware_id = 'COMS-AU142'
        status.values = [
            KeyValue(key='model_sha256', value=self._model_hash),
            KeyValue(key='frame_age_s', value=(
                'unknown' if frame_age is None else f'{frame_age:.3f}')),
            KeyValue(key='last_latency_ms', value=(
                f'{self._latencies_ms[-1]:.2f}'
                if latencies else 'unknown')),
            KeyValue(key='p95_latency_ms', value=(
                f'{p95:.2f}' if latencies else 'unknown')),
        ]
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.status.append(status)
        self._diagnostics_pub.publish(message)


def main():
    rclpy.init()
    node = VisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()