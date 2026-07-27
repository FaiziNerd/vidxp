import sys
import types
import unittest
from unittest.mock import Mock, patch

from vidxp.capabilities.dialogue import models as dialogue_models
from vidxp.capabilities.registry import (
    dependencies_for,
    dependency_checks,
    runtime_distributions,
)
from vidxp.core.contracts import VideoSource


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
        imported = []

        def record(module_name):
            imported.append(module_name)
            return object()

        with patch(
            "vidxp.capabilities.contracts.import_module",
            side_effect=record,
        ):
            checks = dependency_checks(("scene",))

        self.assertTrue(all(check["ok"] for check in checks))
        self.assertNotIn("whisperx", imported)
        self.assertNotIn("face_recognition", imported)
        self.assertNotIn("sentence_transformers", imported)

    def test_supplied_transcript_only_requires_dialogue_search_dependencies(self):
        source = VideoSource(
            transcript=({"text": "hello", "start": 0, "end": 1},)
        )

        modules = {
            dependency.module
            for dependency in dependencies_for(
                ("dialogue",),
                source=source,
            )
        }

        self.assertIn("sentence_transformers", modules)
        self.assertNotIn("whisperx", modules)
        self.assertNotIn("moviepy.editor", modules)
        self.assertNotIn("cv2", modules)

    def test_runtime_distributions_come_from_capability_registry(self):
        distributions = runtime_distributions()

        self.assertIn("clip-anytorch", distributions)
        self.assertIn("face-recognition", distributions)
        self.assertIn("filelock", distributions)
        self.assertIn("pydantic", distributions)
        self.assertEqual(len(distributions), len(set(distributions)))


if __name__ == "__main__":
    unittest.main()
