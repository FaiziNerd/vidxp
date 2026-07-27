import json
import os
import sys
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from vidxp import cli
from vidxp.capabilities.schemas import (
    ActorClusterSummary,
    ActorDetection,
    ActorRenderResult,
    SearchHit,
    SearchResult,
)
from vidxp.index_state import IndexNotReadyError


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


class CliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.config_file = (
            Path(self.temporary_directory.name) / "repositories.json"
        )
        self.service = Mock()
        self.service.index_directory = Path("chroma_data")
        self.service.device = None

    def invoke(self, arguments):
        with patch.object(
            cli,
            "VidXPService",
            return_value=self.service,
        ):
            return self.runner.invoke(
                cli.app,
                ["--config", str(self.config_file), *arguments],
            )

    def test_grouped_commands_are_exposed(self):
        response = self.invoke(["--help"])

        self.assertEqual(response.exit_code, 0)
        for command in (
            "index",
            "search",
            "actors",
            "repositories",
            "benchmark",
            "ui",
        ):
            self.assertIn(command, response.stdout)

    def test_removed_legacy_commands_are_rejected(self):
        for command in ("videoindex", "dialogue", "scene", "actor"):
            with self.subTest(command=command):
                response = self.invoke([command])

                self.assertEqual(response.exit_code, 2)
                self.assertIn("No such command", response.output)

    def test_search_returns_ranked_json_and_passes_top_k(self):
        self.service.search.return_value = result(
            "dialogue",
            [7.5, 12.0],
        )

        response = self.invoke(
            [
                "search",
                "dialogue",
                "fresh bread",
                "--top-k",
                "2",
                "--json",
            ]
        )

        self.assertEqual(response.exit_code, 0, response.output)
        payload = json.loads(response.stdout)
        self.assertEqual(
            [hit["start"] for hit in payload["hits"]],
            [7.5, 12.0],
        )
        self.service.search.assert_called_once_with(
            "dialogue",
            "fresh bread",
            top_k=2,
        )

    def test_global_index_directory_and_device_configure_service(self):
        with patch.object(cli, "VidXPService") as service_type:
            service_type.return_value.index_status.return_value = {
                "state": "missing",
            }
            response = self.runner.invoke(
                cli.app,
                [
                    "--config",
                    str(self.config_file),
                    "--index-dir",
                    "custom-index",
                    "--device",
                    "cuda",
                    "index",
                    "status",
                    "--json",
                ],
            )

        self.assertEqual(response.exit_code, 0, response.output)
        service_type.assert_called_once_with(Path("custom-index"), device="cuda")

    def test_repository_commands_persist_and_select_named_indexes(self):
        index_directory = (
            Path(self.temporary_directory.name) / "team-index"
        )
        added = self.invoke(
            [
                "repositories",
                "add",
                "team",
                "--index-dir",
                str(index_directory),
                "--device",
                "cuda",
                "--use",
                "--json",
            ]
        )
        listed = self.invoke(["repositories", "list", "--json"])

        self.assertEqual(added.exit_code, 0, added.output)
        self.assertEqual(json.loads(added.stdout)["name"], "team")
        payload = json.loads(listed.stdout)
        self.assertEqual(payload["active_repository"], "team")
        configured = {
            item["name"]: item for item in payload["repositories"]
        }
        self.assertEqual(
            configured["team"]["index_directory"],
            str(index_directory.resolve()),
        )

    def test_repository_removal_leaves_index_data_untouched(self):
        index_directory = (
            Path(self.temporary_directory.name) / "team-index"
        )
        index_directory.mkdir()
        marker = index_directory / "keep"
        marker.write_text("data", encoding="utf-8")
        self.invoke(
            [
                "repositories",
                "add",
                "team",
                "--index-dir",
                str(index_directory),
            ]
        )

        removed = self.invoke(
            ["repositories", "remove", "team", "--yes", "--json"]
        )

        self.assertEqual(removed.exit_code, 0, removed.output)
        self.assertFalse(json.loads(removed.stdout)["index_deleted"])
        self.assertTrue(marker.is_file())

    def test_index_create_uses_repeated_typed_modalities(self):
        self.service.create_index.return_value = {"scene_frames": 10}
        with TemporaryDirectory() as directory:
            video = Path(directory) / "sample.mp4"
            video.write_bytes(b"video")
            response = self.invoke(
                [
                    "--format",
                    "json",
                    "index",
                    "create",
                    str(video),
                    "--modality",
                    "scene",
                    "--frame-stride",
                    "5",
                ]
            )

        self.assertEqual(response.exit_code, 0, response.output)
        self.assertEqual(json.loads(response.stdout), {"scene_frames": 10})
        self.service.create_index.assert_called_once()
        call = self.service.create_index.call_args
        self.assertEqual(call.kwargs["modalities"], ("scene",))
        self.assertEqual(call.kwargs["frame_stride"], 5)

    def test_index_status_reports_missing_index_as_json(self):
        self.service.index_status.return_value = {
            "state": "missing",
            "message": "No local video index was found.",
        }

        response = self.invoke(["index", "status", "--json"])

        self.assertEqual(response.exit_code, 0, response.output)
        self.assertEqual(json.loads(response.stdout)["state"], "missing")

    def test_index_clear_requires_explicit_confirmation_for_automation(self):
        self.service.clear_index.return_value = True

        response = self.invoke(["index", "clear", "--yes", "--json"])

        self.assertEqual(response.exit_code, 0, response.output)
        self.assertTrue(json.loads(response.stdout)["cleared"])
        self.service.clear_index.assert_called_once_with()

    def test_doctor_and_prepare_use_the_reusable_service(self):
        self.service.check_dependencies.return_value = {
            "ok": True,
            "modalities": ["scene"],
            "checks": [{"name": "CLIP", "ok": True, "error": None}],
        }
        self.service.prepare_models.return_value = {
            "prepared": ["ViT-B/32"],
            "modalities": ["scene"],
            "device": "cpu",
            "language": None,
        }

        checked = self.invoke(
            ["doctor", "--modalities", "scene", "--json"]
        )
        prepared = self.invoke(
            ["prepare", "--modalities", "scene", "--json"]
        )

        self.assertTrue(json.loads(checked.stdout)["ok"])
        self.assertEqual(
            json.loads(prepared.stdout)["prepared"],
            ["ViT-B/32"],
        )
        self.service.check_dependencies.assert_called_once_with(("scene",))
        self.service.prepare_models.assert_called_once()

    def test_ui_receives_the_selected_service_configuration(self):
        self.service.index_directory = Path("selected-index")
        self.service.device = "cuda"
        from vidxp import frontend

        with (
            patch.dict(os.environ, {}, clear=False),
            patch.object(frontend, "SERVICE"),
            patch.object(frontend, "SAVED_VIDEO_PATH"),
            patch.object(frontend, "ACTOR_OUTPUT_PATH"),
            patch.object(frontend, "main") as launch,
        ):
            response = self.invoke(
                ["ui", "--host", "0.0.0.0", "--port", "8501"]
            )

            self.assertEqual(response.exit_code, 0, response.output)
            launch.assert_called_once_with(
                ["--server.address=0.0.0.0", "--server.port=8501"]
            )
            self.assertEqual(os.environ["VIDXP_DEVICE"], "cuda")
            self.assertEqual(
                os.environ["VIDXP_INDEX_DIR"],
                "selected-index",
            )

    def test_actor_commands_expose_clusters_detections_and_rendering(self):
        cluster = ActorClusterSummary(
            cluster_id="3",
            video_id="video-1",
            detection_count=4,
            first_timestamp=1.0,
            last_timestamp=8.0,
        )
        self.service.actor_clusters.return_value = (cluster,)
        self.service.actor_detections.return_value = [
            ActorDetection(
                detection_id="d2",
                cluster_id="3",
                frame_index=2,
                timestamp=1.5,
                bbox=(1, 2, 3, 0),
                dataset="local",
                split="local",
                run_id="default",
                video_id="video-1",
                modality="actor",
                source_id="actor:d2",
            )
        ]
        self.service.render_actor.return_value = ActorRenderResult(
            output_path=Path("actor.mp4"),
            detection_count=4,
        )

        listed = self.invoke(["actors", "list", "--json"])
        inspected = self.invoke(["actors", "inspect", "3", "--json"])
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"video")
            rendered = self.invoke(
                [
                    "actors",
                    "render",
                    "3",
                    str(source),
                    "--output",
                    "actor.mp4",
                    "--json",
                ]
            )

        self.assertEqual(json.loads(listed.stdout)["count"], 1)
        self.assertEqual(
            json.loads(inspected.stdout)["detection_count"],
            1,
        )
        self.assertEqual(
            json.loads(rendered.stdout)["output_path"],
            "actor.mp4",
        )

    def test_benchmark_commands_are_exposed(self):
        response = self.invoke(["benchmark", "--help"])

        self.assertEqual(response.exit_code, 0)
        self.assertIn("didemo", response.stdout)
        self.assertIn("hirest", response.stdout)

    def test_version_options_report_installed_package_version(self):
        for option in ("--version", "-V"):
            with self.subTest(option=option):
                response = self.invoke([option])

                self.assertEqual(response.exit_code, 0)
                self.assertEqual(
                    response.stdout.strip(),
                    f"VidXP {cli.__version__}",
                )

    def test_main_emits_uniform_json_for_runtime_errors(self):
        self.service.search.side_effect = IndexNotReadyError(
            "Index is not ready."
        )
        stderr = StringIO()
        arguments = [
            "vidxp",
            "--config",
            str(self.config_file),
            "--format",
            "json",
            "search",
            "scene",
            "yellow taxi",
        ]
        with (
            patch.object(sys, "argv", arguments),
            patch.object(
                cli,
                "VidXPService",
                return_value=self.service,
            ),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            cli.main()

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["error"]["message"],
            "Index is not ready.",
        )
        self.assertEqual(payload["error"]["exit_code"], 1)


if __name__ == "__main__":
    unittest.main()
