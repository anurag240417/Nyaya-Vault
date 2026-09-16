from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Protocol

from app.core.config import Settings


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2, normalized 0-1
    frame_timestamp_seconds: float | None = None  # None for a still image


class ObjectDetector(Protocol):
    def detect_image(self, image_bytes: bytes) -> list[Detection]: ...
    def detect_video_frame(self, frame_bytes: bytes, timestamp_seconds: float) -> list[Detection]: ...


class YoloObjectDetector:
    """Wraps a self-hosted Ultralytics YOLO model. Only imports ultralytics
    at first real use (not at module import time) so this module can be
    imported freely even when the heavy vision dependencies aren't
    installed - ENABLE_VISION_ANALYSIS=false is the normal state and must
    not require torch to be present at all.

    Uses stock COCO-pretrained weights: 80 general object classes (person,
    car, truck, backpack, knife, etc.) - this is genuine object/scene
    detection, not a weapons detector. There is no "gun" or "pistol" class
    in the standard dataset; do not represent this as detecting firearms.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None

    def _load_model(self):
        if self._model is None:
            from ultralytics import YOLO  # heavy import, deferred to first use
            self._model = YOLO(self.settings.vision_model_path)
        return self._model

    def _run(self, image_bytes: bytes, timestamp_seconds: float | None) -> list[Detection]:
        from PIL import Image
        model = self._load_model()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = image.size
        results = model.predict(image, verbose=False, conf=self.settings.vision_confidence_threshold)
        detections: list[Detection] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(Detection(
                    label=names[int(box.cls[0])],
                    confidence=float(box.conf[0]),
                    bbox=(x1 / width, y1 / height, x2 / width, y2 / height),
                    frame_timestamp_seconds=timestamp_seconds,
                ))
        return detections

    def detect_image(self, image_bytes: bytes) -> list[Detection]:
        return self._run(image_bytes, timestamp_seconds=None)

    def detect_video_frame(self, frame_bytes: bytes, timestamp_seconds: float) -> list[Detection]:
        return self._run(frame_bytes, timestamp_seconds=timestamp_seconds)


def _default_detector(settings: Settings) -> ObjectDetector:
    return YoloObjectDetector(settings)


def sample_video_frames(video_bytes: bytes, *, max_frames: int, interval_seconds: float) -> list[tuple[bytes, float]]:
    """Extracts up to max_frames JPEG frames from a video, spaced
    interval_seconds apart, starting from the beginning. Returns
    (jpeg_bytes, timestamp_seconds) pairs. Deferred cv2 import for the same
    reason as YOLO above - must not be required when vision is disabled.
    """
    import cv2
    import numpy as np
    import tempfile

    frames: list[tuple[bytes, float]] = []
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        tmp.write(video_bytes)
        tmp.flush()
        capture = cv2.VideoCapture(tmp.name)
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        frame_interval = max(int(fps * interval_seconds), 1)
        frame_index = 0
        try:
            while len(frames) < max_frames:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % frame_interval == 0:
                    success, buffer = cv2.imencode(".jpg", frame)
                    if success:
                        timestamp = frame_index / fps
                        frames.append((buffer.tobytes(), timestamp))
                frame_index += 1
        finally:
            capture.release()
    return frames


class VisionService:
    def __init__(self, settings: Settings, detector: ObjectDetector | None = None) -> None:
        self.settings = settings
        self.detector = detector or _default_detector(settings)

    def analyze_image(self, image_bytes: bytes) -> list[dict[str, Any]]:
        if not self.settings.enable_vision_analysis:
            return []
        detections = self.detector.detect_image(image_bytes)
        return [self._to_entity_payload(d) for d in detections]

    def analyze_video(self, video_bytes: bytes) -> list[dict[str, Any]]:
        if not self.settings.enable_vision_analysis:
            return []
        frames = sample_video_frames(
            video_bytes,
            max_frames=self.settings.vision_max_video_frames,
            interval_seconds=self.settings.vision_frame_interval_seconds,
        )
        payloads: list[dict[str, Any]] = []
        for frame_bytes, timestamp in frames:
            for detection in self.detector.detect_video_frame(frame_bytes, timestamp):
                payloads.append(self._to_entity_payload(detection))
        return payloads

    @staticmethod
    def _to_entity_payload(detection: Detection) -> dict[str, Any]:
        """Shaped to slot directly into document_entities - status stays
        unconfirmed (confirmed=false is the table default) so a human must
        review every detection before it counts as anything, same gate as
        every other AI-derived fact in this codebase.
        """
        return {
            "entity_type": "OBJECT_DETECTED",
            "value": detection.label,
            "confidence": round(detection.confidence, 4),
            "metadata": {
                "bbox": list(detection.bbox),
                "frame_timestamp_seconds": detection.frame_timestamp_seconds,
                "model": "yolov8n (COCO, 80 general classes - not a weapons detector)",
            },
        }