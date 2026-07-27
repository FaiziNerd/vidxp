import sys
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

from vidxp.core import indexing_visual as indexing_visual_module
from vidxp.core.contracts import CancellationToken, IndexConfig, VideoSource
from vidxp.core.indexing import (
    build_dialogue_phrases,
    index_actors,
    index_dialogue,
    index_scenes,
    index_visuals,
)
from vidxp.core.video import FrameSample, VideoInfo


class CapturingStorage:
    def __init__(self):
        self.calls = []
        self.deleted_actor_clusters = []

    def upsert(self, modality, records, **options):
        self.calls.append((modality, list(records), options))
        return len(records)

    def delete_actor_cluster(self, video_id, cluster_id):
        self.deleted_actor_clusters.append((video_id, cluster_id))


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
                ("released ASR", 2.0, 2.0 + 4.0 / 3.0),
                ("span", 2.0 + 4.0 / 3.0, 4.0),
            ],
        )

    def test_segment_text_is_rechunked_with_interpolated_timestamps(self):
        phrases = build_dialogue_phrases(
            [
                {
                    "text": "one two three four five six seven",
                    "start": 0.0,
                    "end": 7.0,
                }
            ],
            words_per_phrase=5,
        )

        self.assertEqual(
            [(item.text, item.start, item.end) for item in phrases],
            [
                ("one two three four five", 0.0, 5.0),
                ("six seven", 5.0, 7.0),
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
                "vidxp.core.indexing_dialogue.get_embedder",
                return_value=encoder,
            ),
            patch(
                "vidxp.core.indexing_dialogue.transcribe_video",
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
            patch("vidxp.core.indexing_visual.probe_video", return_value=info),
            patch(
                "vidxp.core.indexing_visual.iter_frame_batches",
                return_value=iter(batches),
            ),
            patch(
                "vidxp.core.indexing_visual.get_clip_model",
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
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        batches = [[
            FrameSample(0, 0.0, frame),
            FrameSample(2, 0.2, frame),
        ]]
        fake_faces = types.SimpleNamespace(
            face_locations=lambda _: [(1, 2, 3, 0)],
            face_encodings=lambda *_args, **_kwargs: [
                np.asarray([1.0, 0.0])
            ],
            face_distance=lambda known, _: np.asarray(
                [0.0 for _ in known]
            ),
        )
        with (
            patch("vidxp.core.indexing_visual.probe_video", return_value=info),
            patch(
                "vidxp.core.indexing_visual.iter_frame_batches",
                return_value=iter(batches),
            ),
            patch.dict(sys.modules, {"face_recognition": fake_faces}),
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

    def test_scene_and_actor_share_one_probe_and_frame_stream(self):
        import torch

        config = IndexConfig(
            dataset="sample",
            split="test",
            run_id="shared",
            video_id="video-1",
            enabled_modalities=("scene", "actor"),
            frame_stride=2,
            scene_batch_size=2,
            actor_batch_size=1,
            actor_min_detections=1,
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
        frame_stream = Mock()

        def stream(*_, **options):
            options["stats"].frames_advanced = 5
            options["stats"].frames_materialized = 3
            return iter(batches)

        frame_stream.side_effect = stream

        def consume_actor(samples, *, state, **_):
            state.processed_frames += len(samples)

        with (
            patch(
                "vidxp.core.indexing_visual.probe_video",
                return_value=info,
            ) as probe,
            patch(
                "vidxp.core.indexing_visual.iter_frame_batches",
                frame_stream,
            ),
            patch(
                "vidxp.core.indexing_visual.get_clip_model",
                return_value=(
                    model,
                    lambda _: torch.ones((3, 2, 2), dtype=torch.float32),
                ),
            ),
            patch(
                "vidxp.core.indexing_visual.process_actor_samples",
                side_effect=consume_actor,
            ) as actor_consumer,
            patch(
                "vidxp.core.indexing_visual._rgb_samples",
                wraps=indexing_visual_module._rgb_samples,
            ) as rgb_conversion,
        ):
            result = index_visuals(
                source,
                config=config,
                storage=storage,
                cancellation=CancellationToken(),
            )

        probe.assert_called_once_with("unused.mp4")
        frame_stream.assert_called_once()
        self.assertEqual(frame_stream.call_args.kwargs["batch_size"], 2)
        self.assertEqual(model.batch_sizes, [2, 1])
        self.assertEqual(actor_consumer.call_count, 2)
        self.assertEqual(rgb_conversion.call_count, 2)
        self.assertEqual(result.summary["source_frames_advanced"], 5)
        self.assertEqual(result.summary["sampled_frames"], 3)
        self.assertEqual(result.summary["frame_operations"], 6)


if __name__ == "__main__":
    unittest.main()
