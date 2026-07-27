import sys
import types
import unittest
from importlib.metadata import PackageNotFoundError
from unittest.mock import Mock, patch

from vidxp.capabilities.contracts import CapabilityDefinition
from vidxp.capabilities.dialogue import models as dialogue_models
from vidxp.capabilities.registry import (
    dependency_checks,
    requirements_for,
    runtime_checks_for,
    runtime_distributions,
)
from vidxp.core.contracts import VideoSource
from vidxp.dependencies import inspect_requirement
from packaging.requirements import Requirement


class ModelTests(unittest.TestCase):
    def tearDown(self):
        dialogue_models.clear_model_cache()

    def test_dialogue_model_is_reused_across_videos(self):
        constructor = Mock(return_value=object())
        fake_module = types.SimpleNamespace(SentenceTransformer=constructor)
        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            first = dialogue_models.get_embedder("model-id", "cpu")
            second = dialogue_models.get_embedder("model-id", "cpu")

        self.assertIs(first, second)
        constructor.assert_called_once_with("model-id", device="cpu")

    def test_scene_dependency_check_does_not_touch_other_capabilities(self):
        inspected = []

        versions = {
            "chromadb": "1.0",
            "clip-anytorch": "2.6.0",
            "numpy": "2.1",
            "opencv-python": "4.10",
            "Pillow": "10.0",
            "torch": "2.5",
        }

        with patch(
            "vidxp.dependencies.version",
            side_effect=lambda name: (
                inspected.append(name),
                versions[name],
            )[1],
        ):
            checks = dependency_checks(("scene",))

        self.assertTrue(all(check["ok"] for check in checks))
        self.assertNotIn("whisperx", inspected)
        self.assertNotIn("face-recognition", inspected)
        self.assertNotIn("sentence-transformers", inspected)

    def test_supplied_transcript_only_requires_dialogue_search_dependencies(self):
        source = VideoSource(
            transcript=({"text": "hello", "start": 0, "end": 1},)
        )

        distributions = {
            requirement.name
            for requirement in requirements_for(
                ("dialogue",),
                source=source,
            )
        }

        self.assertIn("sentence-transformers", distributions)
        self.assertNotIn("whisperx", distributions)
        self.assertNotIn("moviepy", distributions)
        self.assertNotIn("opencv-python", distributions)

    def test_runtime_distributions_come_from_capability_registry(self):
        with patch(
            "vidxp.capabilities.registry.installed_base_requirements",
            return_value=(),
        ):
            distributions = runtime_distributions()

        self.assertIn("clip-anytorch", distributions)
        self.assertIn("face-recognition", distributions)
        self.assertEqual(len(distributions), len(set(distributions)))

    def test_requirement_files_are_the_only_python_dependency_contract(self):
        self.assertNotIn("dependencies", CapabilityDefinition.model_fields)
        checks = runtime_checks_for(
            ("dialogue",),
            source=VideoSource(
                transcript=({"text": "hello", "start": 0, "end": 1},)
            ),
        )
        self.assertEqual(checks, ())
        self.assertEqual(
            [check.label for check in runtime_checks_for(
                ("dialogue",),
                source=VideoSource(path="video.mp4"),
            )],
            ["FFmpeg"],
        )

    def test_requirement_check_uses_distribution_metadata_and_specifier(self):
        requirement = Requirement("example>=2,<3")
        with patch("vidxp.dependencies.version", return_value="2.5"):
            self.assertTrue(inspect_requirement(requirement)["ok"])
        with patch("vidxp.dependencies.version", return_value="1.0"):
            self.assertFalse(inspect_requirement(requirement)["ok"])
        with patch(
            "vidxp.dependencies.version",
            side_effect=PackageNotFoundError("example"),
        ):
            self.assertFalse(inspect_requirement(requirement)["ok"])


if __name__ == "__main__":
    unittest.main()
