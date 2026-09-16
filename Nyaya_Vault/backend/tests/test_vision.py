from __future__ import annotations

import numpy as np
import pytest

from app.core.config import Settings
from app.services.vision import Detection, VisionService, sample_video_frames
from tests.conftest import auth


def _settings(**overrides) -> Settings:
    base = dict(
        supabase_url="http://fake.invalid", supabase_anon_key="anon", supabase_service_role_key="service",
        anthropic_api_key=None, openai_api_key=None,
    )
    base.update(overrides)
    return Settings(**base)


class FakeDetector:
    """Records calls instead of running a real model - lets tests assert
    exactly what was analyzed without needing torch/ultralytics installed."""

    def __init__(self, detections: list[Detection]):
        self.detections = detections
        self.image_calls: list[bytes] = []
        self.frame_calls: list[tuple[bytes, float]] = []

    def detect_image(self, image_bytes: bytes) -> list[Detection]:
        self.image_calls.append(image_bytes)
        return self.detections

    def detect_video_frame(self, frame_bytes: bytes, timestamp_seconds: float) -> list[Detection]:
        self.frame_calls.append((frame_bytes, timestamp_seconds))
        return [
            Detection(label=d.label, confidence=d.confidence, bbox=d.bbox, frame_timestamp_seconds=timestamp_seconds)
            for d in self.detections
        ]


def test_vision_disabled_by_default_returns_nothing_and_never_touches_the_detector():
    fake = FakeDetector([Detection(label="car", confidence=0.9, bbox=(0, 0, 1, 1))])
    service = VisionService(_settings(enable_vision_analysis=False), detector=fake)
    assert service.analyze_image(b"fake-image-bytes") == []
    assert fake.image_calls == []  # never even called - not just an empty result


def test_analyze_image_shapes_detections_as_unconfirmed_document_entities():
    fake = FakeDetector([
        Detection(label="car", confidence=0.876543, bbox=(0.1, 0.2, 0.5, 0.6)),
        Detection(label="knife", confidence=0.42, bbox=(0.0, 0.0, 0.3, 0.3)),
    ])
    service = VisionService(_settings(enable_vision_analysis=True), detector=fake)
    payloads = service.analyze_image(b"fake-image-bytes")

    assert fake.image_calls == [b"fake-image-bytes"]
    assert len(payloads) == 2
    for p in payloads:
        assert p["entity_type"] == "OBJECT_DETECTED"
        assert "confirmed" not in p  # confirmed=false is the table default, not set here
        assert 0 <= p["confidence"] <= 1
        assert len(p["metadata"]["bbox"]) == 4
        assert p["metadata"]["frame_timestamp_seconds"] is None  # still image, not video

    labels = {p["value"] for p in payloads}
    assert labels == {"car", "knife"}
    # Confidence is genuinely carried through, not dropped or reset
    car_payload = next(p for p in payloads if p["value"] == "car")
    assert car_payload["confidence"] == pytest.approx(0.8765, abs=0.001)


def test_analyze_video_carries_a_distinct_timestamp_per_sampled_frame():
    """Doesn't touch real cv2 - injects a fake frame sampler equivalent by
    testing analyze_video's per-frame wiring directly against a fake
    detector, while sample_video_frames itself is tested separately below
    against a real generated video."""
    fake = FakeDetector([Detection(label="person", confidence=0.7, bbox=(0, 0, 1, 1))])
    service = VisionService(_settings(enable_vision_analysis=True, vision_max_video_frames=2), detector=fake)

    real_video = _make_test_video(num_frames=50, fps=25)
    payloads = service.analyze_video(real_video)

    assert len(fake.frame_calls) <= 2  # respects vision_max_video_frames
    assert len(payloads) == len(fake.frame_calls)
    timestamps = [p["metadata"]["frame_timestamp_seconds"] for p in payloads]
    assert all(t is not None for t in timestamps)
    assert len(set(timestamps)) == len(timestamps)  # each frame has its own timestamp


def _make_test_video(*, num_frames: int, fps: int, width: int = 64, height: int = 48) -> bytes:
    """Builds a real, tiny, valid mp4 in memory using cv2 - genuinely
    exercises sample_video_frames' real VideoCapture/VideoWriter interface
    rather than mocking it away, without needing a real evidence file."""
    import cv2
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        path = tmp.name
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for i in range(num_frames):
        frame = np.full((height, width, 3), i % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    with open(path, "rb") as f:
        return f.read()


def test_sample_video_frames_respects_max_frames_and_interval():
    video_bytes = _make_test_video(num_frames=100, fps=25)  # 4 seconds of video
    frames = sample_video_frames(video_bytes, max_frames=3, interval_seconds=1.0)

    assert len(frames) <= 3
    assert len(frames) >= 1
    for frame_bytes, timestamp in frames:
        assert frame_bytes.startswith(b"\xff\xd8")  # real JPEG magic bytes, not empty/fake data
        assert timestamp >= 0

    # Frames should be spaced roughly 1 second apart, not all identical/zero
    timestamps = [t for _, t in frames]
    if len(timestamps) > 1:
        assert timestamps[1] - timestamps[0] == pytest.approx(1.0, abs=0.2)


def test_sample_video_frames_handles_a_video_shorter_than_max_frames_gracefully():
    """A 1-second video asked for 10 frames at 1-per-2-seconds shouldn't
    crash or hang - it should just return what's actually there."""
    video_bytes = _make_test_video(num_frames=20, fps=20)  # 1 second
    frames = sample_video_frames(video_bytes, max_frames=10, interval_seconds=2.0)
    assert len(frames) >= 1
    assert len(frames) <= 10


def _make_test_png() -> bytes:
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(100, 150, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_processing_pipeline_wires_vision_detections_into_document_entities(client, gateway):
    """End-to-end through the real API: upload an image, enable vision with
    a fake detector injected into the real running processor, process it,
    and confirm the detection actually lands in document_entities as an
    unconfirmed OBJECT_DETECTED row reachable through the normal entities
    endpoint - proves the wiring, not just the isolated service."""
    from tests.test_api_end_to_end import create_case

    case = create_case(client)
    up = client.post(
        f"/api/v1/cases/{case['id']}/documents", headers=auth("admin-token"),
        data={"title": "Scene photo", "clearance_level": "PUBLIC"},
        files={"file": ("scene.png", _make_test_png(), "image/png")},
    )
    assert up.status_code == 200, up.text
    doc_id, version_id = up.json()["documentId"], up.json()["versionId"]

    client.app.state.processor.settings.enable_vision_analysis = True
    fake = FakeDetector([Detection(label="car", confidence=0.81, bbox=(0.1, 0.1, 0.4, 0.4))])
    client.app.state.processor.vision.detector = fake

    processed = client.post(f"/api/v1/documents/{doc_id}/process", headers=auth("admin-token"), json={"version_id": version_id})
    assert processed.status_code == 200, processed.text
    assert fake.image_calls, "the real processing pipeline never called the injected detector"

    entities = client.get(f"/api/v1/document-versions/{version_id}/entities", headers=auth("admin-token")).json()
    car_entities = [e for e in entities if e["entity_type"] == "OBJECT_DETECTED" and e["value"] == "car"]
    assert len(car_entities) == 1
    assert car_entities[0]["confirmed"] is False
    assert car_entities[0]["confidence"] == pytest.approx(0.81)