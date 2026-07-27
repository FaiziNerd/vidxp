import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from vidxp.application import VidXPService
from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    OperationDefinition,
)
from vidxp.capabilities.schemas import SearchInput, SearchResult
from vidxp.core.contracts import IndexConfig


class ApplicationServiceTests(unittest.TestCase):
    def test_execute_supports_validated_operation_without_an_index(self):
        capability = CapabilityDefinition(
            name="export",
            description="Export results.",
            extra="export",
            operations={
                "run": OperationDefinition(
                    input_model=SearchInput,
                    output_model=SearchResult,
                    handler=lambda context, request: {
                        "query_id": "export:1",
                        "query": request.query,
                        "modality": "export",
                        "hits": (),
                    },
                    requires_index=False,
                )
            },
        )
        service = VidXPService()
        with (
            patch(
                "vidxp.application.get_capability",
                return_value=capability,
            ),
            patch.object(
                service,
                "active_config",
                side_effect=AssertionError("index should not be loaded"),
            ),
        ):
            result = service.execute(
                "export",
                "run",
                {"query": "result bundle"},
            )

        self.assertEqual(result.query, "result bundle")

    def test_missing_index_has_a_stable_status_contract(self):
        service = VidXPService("missing-index")
        with patch(
            "vidxp.application.read_index_status",
            return_value=None,
        ):
            status = service.index_status()

        self.assertEqual(status["state"], "missing")
        self.assertEqual(status["schema_version"], 1)

    def test_active_config_uses_selected_directory_and_device(self):
        service = VidXPService("selected-index", device="cuda")
        ready = {"state": "ready"}
        stored_config = IndexConfig.local(
            video_id="video-1",
            storage_directory="selected-index",
        )
        with (
            patch(
                "vidxp.application.require_ready_index",
                return_value=ready,
            ) as require,
            patch(
                "vidxp.application.local_config_from_status",
                return_value=stored_config,
            ) as restore,
        ):
            config, status = service.active_config()

        require.assert_called_once_with(Path("selected-index"))
        restore.assert_called_once_with(
            ready,
            storage_directory=Path("selected-index"),
        )
        self.assertEqual(config.device, "cuda")
        self.assertIs(status, ready)

    def test_search_is_a_thin_adapter_over_the_core(self):
        service = VidXPService()
        expected = SearchResult(
            query_id="scene:1",
            query="yellow taxi",
            modality="scene",
        )
        with patch.object(
            service,
            "execute",
            return_value=expected,
        ) as execute:
            result = service.search("scene", "yellow taxi", top_k=7)

        self.assertIs(result, expected)
        execute.assert_called_once_with(
            "scene",
            "search",
            {"query": "yellow taxi", "top_k": 7},
        )

    def test_create_index_centralizes_storage_and_runtime_configuration(self):
        service = VidXPService("selected-index", device="cuda")
        with patch(
            "vidxp.application.index_video",
            return_value={"scene_frames": 1},
        ) as index:
            summary = service.create_index(
                "video.mp4",
                modalities=("scene",),
                frame_stride=5,
            )

        self.assertEqual(summary, {"scene_frames": 1})
        config = index.call_args.kwargs["config"]
        self.assertEqual(config.storage_directory, "selected-index")
        self.assertEqual(config.device, "cuda")
        self.assertEqual(config.enabled_modalities, ("scene",))
        self.assertEqual(config.frame_stride, 5)

    def test_dependency_checks_return_a_transport_neutral_contract(self):
        service = VidXPService()
        with patch(
            "vidxp.application.dependency_checks",
            return_value=(
                {"name": "CLIP", "ok": False, "error": "missing"},
            ),
        ):
            result = service.check_dependencies(("scene",))

        self.assertFalse(result["ok"])
        failed = [check for check in result["checks"] if not check["ok"]]
        self.assertEqual(failed, [
            {"name": "CLIP", "ok": False, "error": "missing"}
        ])

    def test_model_preparation_reports_progress_without_cli_dependencies(self):
        service = VidXPService(device="cuda")
        events = []
        prepare = Mock(
            side_effect=lambda config, _language, progress: (
                progress(
                    {
                        "state": "preparing",
                        "stage": "scene_model",
                        "message": "Preparing scene model",
                    }
                ),
                (config.clip_model,),
            )[1]
        )
        capability = Mock(prepare=prepare)
        with (
            patch(
                "vidxp.application.dependency_checks",
                return_value=(),
            ),
            patch(
                "vidxp.application.get_capability",
                return_value=capability,
            ),
        ):
            result = service.prepare_models(
                ("scene",),
                progress_callback=events.append,
            )

        prepare.assert_called_once()
        self.assertEqual(result["device"], "cuda")
        self.assertEqual(events[0]["stage"], "scene_model")

    def test_clear_removes_only_known_run_state_after_clearing_collections(self):
        with TemporaryDirectory() as directory:
            index_directory = Path(directory) / "index"
            index_directory.mkdir()
            for name in (
                "index_status.json",
                "manifest.json",
                "timings.jsonl",
                "failures.jsonl",
                "run.complete.json",
            ):
                (index_directory / name).write_text("{}", encoding="utf-8")
            unrelated = index_directory / "keep.txt"
            unrelated.write_text("keep", encoding="utf-8")
            checkpoint_directory = index_directory / "checkpoints"
            checkpoint_directory.mkdir()
            (checkpoint_directory / "one.json").write_text(
                "{}",
                encoding="utf-8",
            )

            storage = Mock()
            storage.__enter__ = Mock(return_value=storage)
            storage.__exit__ = Mock(return_value=None)
            service = VidXPService(index_directory)
            with (
                patch(
                    "vidxp.application.indexing_in_progress",
                    return_value=False,
                ),
                patch(
                    "vidxp.application.read_index_status",
                    return_value=None,
                ),
                patch(
                    "vidxp.application.IndexStorage",
                    return_value=storage,
                ),
            ):
                cleared = service.clear_index()

            self.assertTrue(cleared)
            storage.clear.assert_called_once_with()
            self.assertTrue(unrelated.is_file())
            self.assertFalse(
                (index_directory / "index_status.json").exists()
            )
            self.assertFalse(checkpoint_directory.exists())


if __name__ == "__main__":
    unittest.main()
