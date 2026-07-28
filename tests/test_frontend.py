import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from vidxp import frontend
from vidxp.capabilities.schemas import SearchHit, SearchResult
from vidxp.core.contracts import INDEX_SCHEMA_VERSION
from vidxp.index_state import IndexNotReadyError


READY_STATUS = {
    "state": "ready",
    "message": "Video indexing completed successfully.",
    "summary": {
        "index_schema_version": INDEX_SCHEMA_VERSION,
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
    from unittest.mock import Mock, patch

    from vidxp import frontend
    from vidxp.capabilities.schemas import SearchHit, SearchResult
    from vidxp.core.contracts import INDEX_SCHEMA_VERSION

    video_path = Path(video_path)
    actor_output_path = Path(actor_output_path)
    service = Mock()
    service.check_dependencies.return_value = {"ok": True}
    service.index_status.return_value = {
        "state": "ready",
        "message": "Video indexing completed successfully.",
        "summary": {
            "index_schema_version": INDEX_SCHEMA_VERSION,
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

    def search(modality, *_args, **_kwargs):
        return search_result(
            modality,
            17.25 if modality == "dialogue" else 42.5,
        )

    def generate_actor_result(*_):
        copyfile(video_path, actor_output_path)

    service.search.side_effect = search
    service.render_actor.side_effect = generate_actor_result
    with (
        patch.object(frontend, "SERVICE", service),
        patch.object(frontend, "SAVED_VIDEO_PATH", video_path),
        patch.object(frontend, "ACTOR_OUTPUT_PATH", actor_output_path),
        patch.object(frontend, "indexing_in_progress", return_value=False),
    ):
        frontend.run()


class FrontendSearchTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.index_status.return_value = READY_STATUS

    def test_scene_search_uses_shared_service(self):
        self.service.search.return_value = result_for("scene", 12.5)
        with patch.object(frontend, "SERVICE", self.service):
            result = frontend._run_search("scene", "yellow taxi")

        self.assertEqual(result["timestamp"], 12.5)
        self.assertEqual(result["hit"]["video_id"], "video-1")
        self.service.search.assert_called_once_with(
            "scene",
            "yellow taxi",
            top_k=1,
        )

    def test_dialogue_search_returns_a_renderable_result(self):
        self.service.search.return_value = result_for("dialogue", 8)
        with patch.object(frontend, "SERVICE", self.service):
            result = frontend._run_search("dialogue", "fresh bread")

        self.assertEqual(result["type"], "dialogue")
        self.assertEqual(result["timestamp"], 8.0)

    def test_actor_search_uses_shared_service(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "actor.mp4"

            def generate_result(*_):
                output_path.write_bytes(b"video")

            self.service.render_actor.side_effect = generate_result
            with (
                patch.object(frontend, "SERVICE", self.service),
                patch.object(frontend, "ACTOR_OUTPUT_PATH", output_path),
            ):
                result = frontend._run_search("actor", "3")

        self.service.render_actor.assert_called_once()
        self.assertEqual(result["type"], "actor")

    def test_search_error_is_returned_for_persistent_rendering(self):
        self.service.index_status.side_effect = IndexNotReadyError(
            "Index is not ready."
        )
        with patch.object(frontend, "SERVICE", self.service):
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

    def test_available_index_modalities_excludes_missing_extras(self):
        def dependency_status(modalities):
            return {"ok": modalities == ("scene",)}

        self.service.check_dependencies.side_effect = dependency_status
        with patch.object(frontend, "SERVICE", self.service):
            available = frontend._available_index_modalities()

        self.assertEqual(available, ("scene",))

    def test_indexing_passes_selected_modalities_to_the_worker(self):
        uploaded_video = Mock()
        uploaded_video.name = "source.mp4"
        uploaded_video.getvalue.return_value = b"video"
        with TemporaryDirectory() as directory:
            saved_video = Path(directory) / "source-video.mp4"
            with (
                patch.object(frontend, "SAVED_VIDEO_PATH", saved_video),
                patch.object(frontend, "start_indexing") as start,
                patch.object(frontend.st, "rerun"),
            ):
                frontend._run_indexing(
                    uploaded_video,
                    {},
                    ("scene",),
                )

        start.assert_called_once_with(
            str(saved_video),
            "source.mp4",
            frontend.SERVICE,
            modalities=("scene",),
        )

    def test_cancellation_request_uses_the_worker_token(self):
        state = {}
        with (
            patch.object(frontend.st, "session_state", state),
            patch.object(frontend, "cancel_indexing", return_value=True),
        ):
            frontend._request_cancellation()

        self.assertTrue(state[frontend.CANCEL_REQUESTED_KEY])

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
