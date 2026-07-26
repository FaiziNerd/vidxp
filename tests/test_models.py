import sys
import types
import unittest
from unittest.mock import Mock, patch

from vidxp.core import models


class ModelTests(unittest.TestCase):
    def tearDown(self):
        models.get_embedder.cache_clear()

    def test_dialogue_model_is_reused_across_videos(self):
        constructor = Mock(return_value=object())
        fake_module = types.SimpleNamespace(SentenceTransformer=constructor)
        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            first = models.get_embedder("model-id", "cpu")
            second = models.get_embedder("model-id", "cpu")

        self.assertIs(first, second)
        constructor.assert_called_once_with("model-id", device="cpu")

    def test_scene_only_dependency_check_does_not_touch_other_modalities(self):
        imported = []

        def record(module_name):
            imported.append(module_name)
            return object()

        with patch.object(models, "import_module", side_effect=record):
            failures = models.dependency_failures(
                ("scene",),
                needs_transcription=False,
            )

        self.assertEqual(failures, [])
        self.assertNotIn("whisperx", imported)
        self.assertNotIn("face_recognition", imported)
        self.assertNotIn("sentence_transformers", imported)

    def test_supplied_transcript_only_checks_the_dialogue_encoder(self):
        imported = []
        with patch.object(
            models,
            "import_module",
            side_effect=lambda name: imported.append(name) or object(),
        ):
            models.dependency_failures(
                ("dialogue",),
                needs_transcription=False,
            )

        self.assertIn("sentence_transformers", imported)
        self.assertNotIn("whisperx", imported)
        self.assertNotIn("moviepy.editor", imported)
        self.assertNotIn("cv2", imported)


if __name__ == "__main__":
    unittest.main()
