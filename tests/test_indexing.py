import unittest
from unittest.mock import patch

import numpy as np

from vidxp.core.contracts import CancellationToken, IndexConfig, VideoSource
from vidxp.core.indexing import (
    build_dialogue_phrases,
    index_actors,
    index_dialogue,
    index_scenes,
)
from vidxp.core.video import FrameSample, VideoInfo


class CapturingStorage:
    def __init__(self):
        self.calls = []

    def upsert(self, modality, records, **options):
        self.calls.append((modality, list(records), options))
        return len(records)


class FakeEncoder:
    def __init__(self):
        self.batches = []

    def encode(self, texts, **_):
        self.batches.append(list(texts))
        return np.asarray([[float(index), 1.0] for index, _ in enumerate(texts)])


class FakeClipModel:
    def __init__(self):
        self.batch_sizes = []

    def encode_image(self, images):
        import torch

        self.batch_sizes.append(images.shape[0])
        return torch.ones((images.shape[0], 2), dtype=torch.float32)


class IndexingTests(unittest.TestCase):
    def test_timestamped_words_and_segments_keep_real_intervals(self):
        phrases = build_dialogue_phrases(
            [
                {
                    "words": [
                        {"word": "one", "start": 0.0, "end": 0.4},
                        {"word": "two", "start": 0.5, "end": 0.9},
                        {"word": "three", "start": 1.0, "end": 1.4},
                    ]
                },
                {"text": "released ASR span", "start": 2.0, "end": 4.0},
            ],
            words_per_phrase=2,
        )

        self.assertEqual(
            [(item.text, item.start, item.end) for item in phrases],
            [
                ("one two", 0.0, 0.9),
                ("three", 1.0, 1.4),
                ("released ASR span", 2.0, 4.0),
            ],
        )

    def test_supplied_transcript_is_batched_without_video_or_whisper(self):
        config = IndexConfig(
            dataset="hirest",
            split="test",
            run_id="asr",
            video_id="video-1",
            enabled_modalities=("dialogue",),
            dialogue_batch_size=2,
        )
        source = VideoSource(
            video_id="video-1",
            transcript=(
                {"text": "first", "start": 0.0, "end": 1.0},
                {"text": "second", "start": 1.0, "end": 2.0},
                {"text": "third", "start": 2.0, "end": 3.0},
            ),
        )
        storage = CapturingStorage()
        encoder = FakeEncoder()
        with (
            patch(
                "vidxp.core.indexing.get_embedder",
                return_value=encoder,
            ),
            patch(
                "vidxp.core.indexing.transcribe_video",
                side_effect=AssertionError("video/Whisper path was used"),
            ),
        ):
            stats = index_dialogue(
                source,
                config=config,
                storage=storage,
                cancellation=CancellationToken(),
            )

        self.assertEqual([len(batch) for batch in encoder.batches], [2, 1])
        self.assertEqual(stats["dialogue_phrases"], 3)
        records = [
            record
            for _, group, _ in storage.calls
            for record in group
        ]
        self.assertEqual(len({record.source_id for record in records}), 3)
        self.assertEqual(
            set(records[0].metadata),
            {
                "dataset",
                "split",
                "run_id",
                "video_id",
                "modality",
                "source_id",
                "phrase_id",
                "text",
                "start",
                "end",
            },
        )

    def test_scene_model_and_storage_writes_are_batched_with_full_metadata(self):
        import torch

        config = IndexConfig(
            dataset="didemo",
            split="test",
            run_id="stride-2",
            video_id="video-1",
            enabled_modalities=("scene",),
            frame_stride=2,
            scene_batch_size=2,
        )
        source = VideoSource(video_id="video-1", path="unused.mp4")
        storage = CapturingStorage()
        model = FakeClipModel()
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        batches = [
            [
                FrameSample(0, 0.0, frame),
                FrameSample(2, 0.2, frame),
            ],
            [FrameSample(4, 0.4, frame)],
        ]
        info = VideoInfo(
            fps=10.0,
            frame_count=5,
            duration=0.5,
            width=2,
            height=2,
        )

        with (
            patch("vidxp.core.indexing.probe_video", return_value=info),
            patch(
                "vidxp.core.indexing.iter_frame_batches",
                return_value=iter(batches),
            ),
            patch(
                "vidxp.core.indexing.get_clip_model",
                return_value=(
                    model,
                    lambda _: torch.ones((3, 2, 2), dtype=torch.float32),
                ),
            ),
        ):
            stats = index_scenes(
                source,
                config=config,
                storage=storage,
                cancellation=CancellationToken(),
            )

        self.assertEqual(model.batch_sizes, [2, 1])
        self.assertEqual(stats["scene_frames"], 3)
        records = [
            record
            for _, group, _ in storage.calls
            for record in group
        ]
        self.assertEqual(
            [record.metadata["frame_index"] for record in records],
            [0, 2, 4],
        )
        self.assertEqual(records[-1].metadata["end"], 0.5)
        self.assertEqual(records[0].metadata["fps"], 10.0)
        self.assertEqual(records[0].metadata["duration"], 0.5)

    def test_actor_only_records_have_stable_detection_metadata(self):
        config = IndexConfig(
            dataset="sample",
            split="test",
            run_id="actors",
            video_id="video-1",
            enabled_modalities=("actor",),
            actor_min_detections=2,
            storage_batch_size=2,
        )
        source = VideoSource(video_id="video-1", path="unused.mp4")
        storage = CapturingStorage()
        info = VideoInfo(
            fps=10.0,
            frame_count=4,
            duration=0.4,
            width=2,
            height=2,
        )
        detections = [
            {
                "detection_id": "d000000000000-0000",
                "cluster_id": "1",
                "frame_index": 0,
                "timestamp": 0.0,
                "bbox": (1, 2, 3, 0),
            },
            {
                "detection_id": "d000000000002-0000",
                "cluster_id": "1",
                "frame_index": 2,
                "timestamp": 0.2,
                "bbox": (1, 2, 3, 0),
            },
        ]
        with patch(
            "vidxp.core.indexing._cluster_actor_detections",
            return_value=(info, 2, detections),
        ):
            stats = index_actors(
                source,
                config=config,
                storage=storage,
                cancellation=CancellationToken(),
            )

        self.assertEqual(stats["actor_frames"], 2)
        self.assertEqual(stats["actor_detections"], 2)
        modality, records, options = storage.calls[0]
        self.assertEqual(modality, "actor")
        self.assertEqual(options["batch_size"], 2)
        self.assertEqual(
            [record.metadata["detection_id"] for record in records],
            [
                "d000000000000-0000",
                "d000000000002-0000",
            ],
        )
        self.assertEqual(
            set(records[0].metadata),
            {
                "dataset",
                "split",
                "run_id",
                "video_id",
                "modality",
                "source_id",
                "detection_id",
                "cluster_id",
                "frame_index",
                "timestamp",
                "bbox_top",
                "bbox_right",
                "bbox_bottom",
                "bbox_left",
            },
        )


if __name__ == "__main__":
    unittest.main()
