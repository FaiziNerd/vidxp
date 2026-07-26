import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from vidxp import cli
from vidxp.core.contracts import IndexConfig, SearchHit, SearchResult


def result(modality, starts):
    return SearchResult(
        query_id="q",
        query="example",
        modality=modality,
        hits=tuple(
            SearchHit(
                rank=index + 1,
                video_id="video-1",
                start=start,
                end=start + 1,
                score=-float(index),
                raw_distance=float(index),
                modality=modality,
                source_id=f"source-{index}",
            )
            for index, start in enumerate(starts)
        ),
    )


class CliCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.config = IndexConfig.local(video_id="video-1")

    def test_dialogue_command_returns_first_rich_result_timestamp(self):
        with (
            patch.object(
                cli,
                "_active_config",
                return_value=(self.config, {}),
            ),
            patch.object(
                cli,
                "search_dialogue",
                return_value=result("dialogue", [7.5, 12.0]),
            ) as search,
            patch.object(cli, "print"),
        ):
            timestamp = cli.dialogue("fresh bread")

        self.assertEqual(timestamp, 7.5)
        search.assert_called_once_with(
            "fresh bread",
            config=self.config,
            top_k=1,
            video_id="video-1",
        )

    def test_scene_command_returns_first_rich_result_timestamp(self):
        with (
            patch.object(
                cli,
                "_active_config",
                return_value=(self.config, {}),
            ),
            patch.object(
                cli,
                "search_scene",
                return_value=result("scene", [3.25]),
            ),
            patch.object(cli, "print"),
        ):
            self.assertEqual(cli.scene("yellow taxi"), 3.25)

    def test_typer_dialogue_command_displays_first_timestamp(self):
        with (
            patch.object(
                cli,
                "_active_config",
                return_value=(self.config, {}),
            ),
            patch.object(
                cli,
                "search_dialogue",
                return_value=result("dialogue", [7.5]),
            ),
        ):
            response = CliRunner().invoke(
                cli.app,
                ["dialogue", "fresh bread"],
            )

        self.assertEqual(response.exit_code, 0)
        self.assertIn("7.500 seconds", response.stdout)

    def test_typer_videoindex_command_displays_progress_and_completion(self):
        def fake_index(_, progress_callback, **__):
            progress_callback(
                {
                    "stage": "scene_indexing",
                    "message": "Indexing sampled video frames.",
                    "current": 0,
                    "total": 10,
                }
            )
            progress_callback(
                {
                    "stage": "scene_indexing",
                    "message": "Indexing sampled video frames.",
                    "current": 10,
                    "total": 10,
                }
            )
            return {"scene_frames": 10}

        with patch.object(cli, "index_video", side_effect=fake_index):
            response = CliRunner().invoke(
                cli.app,
                ["videoindex", "sample.mp4", "--modalities", "scene"],
            )

        self.assertEqual(response.exit_code, 0)
        self.assertIn("Indexing sampled video frames.", response.stdout)
        self.assertIn("completed successfully", response.stdout)


if __name__ == "__main__":
    unittest.main()
