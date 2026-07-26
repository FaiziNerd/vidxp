import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from vidxp import frontend
from vidxp.index_state import IndexNotReadyError


def frontend_harness(video_path, actor_output_path):
    from pathlib import Path
    from shutil import copyfile
    from unittest.mock import patch

    from vidxp import frontend

    ready_status = {
        "state": "ready",
        "message": "Video indexing completed successfully.",
    }
    video_path = Path(video_path)
    actor_output_path = Path(actor_output_path)

    def generate_actor_result(*_):
        copyfile(video_path, actor_output_path)

    with (
        patch.object(frontend, "SAVED_VIDEO_PATH", video_path),
        patch.object(frontend, "ACTOR_OUTPUT_PATH", actor_output_path),
        patch.object(frontend, "indexing_in_progress", return_value=False),
        patch.object(frontend, "read_index_status", return_value=ready_status),
        patch.object(frontend, "scene", return_value=42.5),
        patch.object(frontend, "dialogue", return_value=17.25),
        patch.object(frontend, "actor", side_effect=generate_actor_result),
    ):
        frontend.run()


class FrontendSearchTests(unittest.TestCase):
    def test_scene_search_returns_a_renderable_result(self):
        with patch.object(frontend, "scene", return_value=12.5):
            result = frontend._run_search("scene", "yellow taxi")

        self.assertEqual(
            result,
            {
                "type": "scene",
                "query": "yellow taxi",
                "timestamp": 12.5,
                "video_path": str(frontend.SAVED_VIDEO_PATH),
            },
        )

    def test_dialogue_search_returns_a_renderable_result(self):
        with patch.object(frontend, "dialogue", return_value=8):
            result = frontend._run_search("dialogue", "fresh bread")

        self.assertEqual(result["type"], "dialogue")
        self.assertEqual(result["timestamp"], 8.0)

    def test_actor_search_returns_the_generated_video(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "actor.mp4"

            def generate_actor_result(*_):
                output_path.write_bytes(b"video")

            with (
                patch.object(frontend, "ACTOR_OUTPUT_PATH", output_path),
                patch.object(
                    frontend,
                    "actor",
                    side_effect=generate_actor_result,
                ) as actor,
            ):
                result = frontend._run_search("actor", "3")

            actor.assert_called_once_with(
                "3",
                str(frontend.SAVED_VIDEO_PATH),
                str(output_path),
            )
            self.assertEqual(
                result,
                {
                    "type": "actor",
                    "query": "3",
                    "video_path": str(output_path),
                },
            )

    def test_actor_search_reports_a_missing_output(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "actor.mp4"
            with (
                patch.object(frontend, "ACTOR_OUTPUT_PATH", output_path),
                patch.object(frontend, "actor"),
            ):
                result = frontend._run_search("actor", "3")

        self.assertEqual(
            result,
            {"error": "Actor result video could not be generated."},
        )

    def test_search_error_is_returned_for_persistent_rendering(self):
        with patch.object(
            frontend,
            "scene",
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

            app.selectbox[0].select("actor").run()
            app.text_input[0].set_value("2").run()
            app.button[1].click().run()
            self.assertEqual(list(app.exception), [])
            self.assertEqual(len(app.get("video")), 2)
            self.assertEqual(
                app.session_state[frontend.SEARCH_RESULT_KEY]["type"],
                "actor",
            )


if __name__ == "__main__":
    unittest.main()
