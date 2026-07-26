import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from vidxp import frontend
from vidxp.core.contracts import IndexConfig, SearchHit, SearchResult
from vidxp.index_state import IndexNotReadyError


READY_STATUS = {
    "state": "ready",
    "message": "Video indexing completed successfully.",
    "summary": {
        "index_schema_version": 2,
        "dataset": "local",
        "split": "local",
        "run_id": "default",
        "video_id": "video-1",
    },
}


def result_for(modality, timestamp):
    return SearchResult(
        query_id="query-1",
        query="example",
        modality=modality,
        hits=(
            SearchHit(
                rank=1,
                video_id="video-1",
                start=timestamp,
                end=timestamp + 1,
                score=-0.1,
                raw_distance=0.1,
                modality=modality,
                source_id=f"run:video-1:{modality}:1",
                metadata={},
            ),
        ),
    )


def frontend_harness(video_path, actor_output_path):
    from pathlib import Path
    from shutil import copyfile
    from unittest.mock import patch

    from vidxp import frontend
    from vidxp.core.contracts import IndexConfig, SearchHit, SearchResult

    video_path = Path(video_path)
    actor_output_path = Path(actor_output_path)
    config = IndexConfig.local(video_id="video-1")
    ready_status = {
        "state": "ready",
        "message": "Video indexing completed successfully.",
        "summary": {
            "index_schema_version": 2,
            "dataset": "local",
            "split": "local",
            "run_id": "default",
            "video_id": "video-1",
        },
    }

    def search_result(modality, timestamp):
        return SearchResult(
            query_id="q",
            query="example",
            modality=modality,
            hits=(
                SearchHit(
                    rank=1,
                    video_id="video-1",
                    start=timestamp,
                    end=timestamp + 1,
                    score=-0.1,
                    raw_distance=0.1,
                    modality=modality,
                    source_id=f"run:video-1:{modality}:1",
                ),
            ),
        )

    def generate_actor_result(*_):
        copyfile(video_path, actor_output_path)

    with (
        patch.object(frontend, "SAVED_VIDEO_PATH", video_path),
        patch.object(frontend, "ACTOR_OUTPUT_PATH", actor_output_path),
        patch.object(frontend, "indexing_in_progress", return_value=False),
        patch.object(frontend, "read_index_status", return_value=ready_status),
        patch.object(frontend, "local_config_from_status", return_value=config),
        patch.object(
            frontend,
            "search_scene",
            return_value=search_result("scene", 42.5),
        ),
        patch.object(
            frontend,
            "search_dialogue",
            return_value=search_result("dialogue", 17.25),
        ),
        patch.object(
            frontend,
            "render_actor_result",
            side_effect=generate_actor_result,
        ),
    ):
        frontend.run()


class FrontendSearchTests(unittest.TestCase):
    def setUp(self):
        self.config = IndexConfig.local(video_id="video-1")
        self.status_patches = (
            patch.object(frontend, "read_index_status", return_value=READY_STATUS),
            patch.object(
                frontend,
                "local_config_from_status",
                return_value=self.config,
            ),
        )

    def test_scene_search_returns_a_renderable_rich_result(self):
        with (
            self.status_patches[0],
            self.status_patches[1],
            patch.object(
                frontend,
                "search_scene",
                return_value=result_for("scene", 12.5),
            ),
        ):
            result = frontend._run_search("scene", "yellow taxi")

        self.assertEqual(result["timestamp"], 12.5)
        self.assertEqual(result["hit"]["video_id"], "video-1")

    def test_dialogue_search_returns_a_renderable_result(self):
        with (
            patch.object(frontend, "read_index_status", return_value=READY_STATUS),
            patch.object(
                frontend,
                "local_config_from_status",
                return_value=self.config,
            ),
            patch.object(
                frontend,
                "search_dialogue",
                return_value=result_for("dialogue", 8),
            ),
        ):
            result = frontend._run_search("dialogue", "fresh bread")

        self.assertEqual(result["type"], "dialogue")
        self.assertEqual(result["timestamp"], 8.0)

    def test_actor_search_uses_structured_detections(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "actor.mp4"

            def generate_result(*_):
                output_path.write_bytes(b"video")

            with (
                patch.object(frontend, "ACTOR_OUTPUT_PATH", output_path),
                patch.object(
                    frontend,
                    "read_index_status",
                    return_value=READY_STATUS,
                ),
                patch.object(
                    frontend,
                    "local_config_from_status",
                    return_value=self.config,
                ),
                patch.object(
                    frontend,
                    "render_actor_result",
                    side_effect=generate_result,
                ) as renderer,
            ):
                result = frontend._run_search("actor", "3")

        renderer.assert_called_once()
        self.assertEqual(result["type"], "actor")

    def test_search_error_is_returned_for_persistent_rendering(self):
        with patch.object(
            frontend,
            "read_index_status",
            side_effect=IndexNotReadyError("Index is not ready."),
        ):
            result = frontend._run_search("scene", "yellow taxi")

        self.assertEqual(result, {"error": "Index is not ready."})

    def test_starting_a_new_index_clears_the_previous_result(self):
        state = {
            frontend.SEARCH_RESULT_KEY: {
                "type": "scene",
                "timestamp": 12.5,
            },
            frontend.INDEX_ERROR_KEY: "old error",
        }
        with patch.object(frontend.st, "session_state", state):
            frontend._request_indexing()

        self.assertTrue(state[frontend.INDEX_REQUESTED_KEY])
        self.assertNotIn(frontend.SEARCH_RESULT_KEY, state)
        self.assertNotIn(frontend.INDEX_ERROR_KEY, state)

    def test_search_results_render_and_survive_widget_reruns(self):
        with TemporaryDirectory() as directory:
            video_path = Path(directory) / "video.mp4"
            actor_output_path = Path(directory) / "actor.mp4"
            video_path.write_bytes(b"video")
            app = AppTest.from_function(
                frontend_harness,
                args=(str(video_path), str(actor_output_path)),
            ).run()

            app.text_input[0].set_value("yellow taxi").run()
            app.button[1].click().run()
            self.assertEqual(list(app.exception), [])
            self.assertEqual(len(app.get("video")), 2)
            self.assertEqual(
                app.session_state[frontend.SEARCH_RESULT_KEY]["type"],
                "scene",
            )

            app.selectbox[0].select("dialogue").run()
            self.assertEqual(len(app.get("video")), 2)
            self.assertEqual(
                app.session_state[frontend.SEARCH_RESULT_KEY]["type"],
                "scene",
            )

            app.text_input[0].set_value("fresh bread").run()
            app.button[1].click().run()
            self.assertEqual(
                app.session_state[frontend.SEARCH_RESULT_KEY]["type"],
                "dialogue",
            )


if __name__ == "__main__":
    unittest.main()
