import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from vidxp import cli
from vidxp.core.actor_results import ActorClusterSummary, ActorRenderResult
from vidxp.core.contracts import SearchHit, SearchResult


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
        self.service = Mock()
        self.service.index_directory = Path("chroma_data")
        self.service.device = None

    def invoke(self, arguments):
        with patch.object(
            cli,
            "VidXPService",
            return_value=self.service,
        ):
            return self.runner.invoke(cli.app, arguments)

    def test_grouped_commands_are_exposed_and_compatibility_aliases_are_hidden(self):
        response = self.invoke(["--help"])

        self.assertEqual(response.exit_code, 0)
        for command in ("index", "search", "actors", "benchmark"):
            self.assertIn(command, response.stdout)
        for alias in ("videoindex", "dialogue", "scene", "actor"):
            self.assertFalse(
                any(
                    line.lstrip("│ ").startswith(f"{alias} ")
                    for line in response.stdout.splitlines()
                )
            )

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

    def test_actor_commands_expose_clusters_detections_and_rendering(self):
        cluster = ActorClusterSummary("3", "video-1", 4, 1.0, 8.0)
        self.service.actor_clusters.return_value = (cluster,)
        self.service.actor_detections.return_value = [
            {
                "frame_index": 2,
                "timestamp": 1.5,
                "detection_id": "d2",
            }
        ]
        self.service.render_actor.return_value = ActorRenderResult(
            Path("actor.mp4"),
            4,
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

    def test_legacy_search_alias_still_works(self):
        self.service.search.return_value = result("scene", [3.25])

        response = self.invoke(["scene", "yellow taxi"])

        self.assertEqual(response.exit_code, 0, response.output)
        self.assertIn("3.250 seconds", response.stdout)
        self.service.search.assert_called_once_with(
            "scene",
            "yellow taxi",
            top_k=1,
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


if __name__ == "__main__":
    unittest.main()
