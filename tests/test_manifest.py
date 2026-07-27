import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from vidxp.core.contracts import IndexConfig, VideoSource
from vidxp.core.manifest import (
    ManifestStore,
    source_checksums,
    write_json_atomic,
)


class ManifestIdentityTests(unittest.TestCase):
    def test_atomic_write_retries_transient_windows_reader_lock(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            with (
                patch.object(
                    Path,
                    "replace",
                    side_effect=[
                        PermissionError("reader lock"),
                        PermissionError("reader lock"),
                        None,
                    ],
                ) as replace,
                patch("vidxp.core.manifest.time.sleep") as sleep,
            ):
                write_json_atomic(path, {"state": "running"})

            self.assertEqual(replace.call_count, 3)
            self.assertEqual(sleep.call_count, 2)

    def test_declared_video_checksum_does_not_suppress_transcript_hash(self):
        transcript = ({"text": "hello", "start": 0.0, "end": 1.0},)
        checksums = source_checksums(
            VideoSource(
                path="not-read-when-checksum-is-declared.mp4",
                transcript=transcript,
                checksum="a" * 64,
            )
        )

        self.assertEqual(checksums["video"], "a" * 64)
        self.assertIn("transcript", checksums)

    def test_checkpoint_filenames_do_not_embed_dataset_video_ids(self):
        with TemporaryDirectory() as directory:
            config = IndexConfig(
                dataset="sample",
                split="test",
                run_id="run-1",
                output_root=directory,
                enabled_modalities=("scene",),
            )
            store = ManifestStore(config)
            video_id = "folder/name:video"
            expected = hashlib.sha256(video_id.encode("utf-8")).hexdigest()

            self.assertEqual(
                store._checkpoint_path(video_id),
                Path(directory)
                / "sample"
                / "run-1"
                / "checkpoints"
                / f"{expected}.json",
            )


if __name__ == "__main__":
    unittest.main()
