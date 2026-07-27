import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock, patch

from vidxp.core.actor_results import (
    ActorClusterNotFoundError,
    actor_detections,
    render_actor_result,
)
from vidxp.core.contracts import IndexConfig


class ActorResultTests(unittest.TestCase):
    def setUp(self):
        self.config = IndexConfig.local(video_id="video-1")

    def test_actor_detection_metadata_is_converted_once(self):
        storage = Mock()
        storage.actor_detections.return_value = [
            {
                "frame_index": 2,
                "bbox_top": 1,
                "bbox_right": 4,
                "bbox_bottom": 5,
                "bbox_left": 0,
            }
        ]

        detections = actor_detections(
            self.config,
            "3",
            storage=storage,
        )

        self.assertEqual(detections[0]["bbox"], (1, 4, 5, 0))
        storage.actor_detections.assert_called_once_with(
            video_id="video-1",
            cluster_id="3",
        )
        storage.close.assert_not_called()

    def test_render_actor_result_rejects_an_empty_cluster(self):
        storage = Mock()
        storage.actor_detections.return_value = []

        with self.assertRaises(ActorClusterNotFoundError):
            render_actor_result(
                self.config,
                "missing",
                "input.mp4",
                "output.mp4",
                storage=storage,
            )

    def test_render_actor_result_returns_output_details(self):
        storage = Mock()
        storage.actor_detections.return_value = [
            {
                "frame_index": 2,
                "bbox_top": 1,
                "bbox_right": 4,
                "bbox_bottom": 5,
                "bbox_left": 0,
            }
        ]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "actor.mp4"
            with patch(
                "vidxp.core.actor_results.render_actor_video"
            ) as renderer:
                result = render_actor_result(
                    self.config,
                    "3",
                    "input.mp4",
                    output,
                    storage=storage,
                )

        renderer.assert_called_once()
        self.assertEqual(result.output_path, output)
        self.assertEqual(result.detection_count, 1)


if __name__ == "__main__":
    unittest.main()
