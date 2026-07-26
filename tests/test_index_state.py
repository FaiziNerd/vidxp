import json
import tempfile
import unittest
from pathlib import Path

from vidxp.index_state import (
    IndexNotReadyError,
    fingerprint_file,
    read_index_status,
    require_ready_index,
    write_index_status,
)


class IndexStateTests(unittest.TestCase):
    def test_missing_status_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                IndexNotReadyError,
                "Index a video before searching",
            ):
                require_ready_index(directory)

    def test_status_round_trip_and_readiness_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            write_index_status(
                state="indexing",
                stage="scene_indexing",
                message="Indexing video scenes.",
                current=5,
                total=10,
                index_directory=directory,
            )

            status = read_index_status(directory)
            self.assertEqual(status["state"], "indexing")
            self.assertEqual(status["current"], 5)
            with self.assertRaises(IndexNotReadyError):
                require_ready_index(directory)

            write_index_status(
                state="ready",
                stage="complete",
                message="Video indexing completed successfully.",
                summary={"scene_frames": 10},
                index_directory=directory,
            )
            self.assertEqual(require_ready_index(directory)["state"], "ready")

    def test_unreadable_status_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "index_status.json"
            status_path.write_text("{not-json", encoding="utf-8")

            status = read_index_status(directory)
            self.assertEqual(status["state"], "failed")
            with self.assertRaises(IndexNotReadyError):
                require_ready_index(directory)

    def test_file_fingerprint_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "sample.mp4"
            video_path.write_bytes(b"vidxp-test-video")

            first = fingerprint_file(video_path)
            second = fingerprint_file(video_path)

            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["size"], len(b"vidxp-test-video"))
            self.assertEqual(first["path"], str(video_path.resolve()))

    def test_status_write_replaces_previous_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            write_index_status(
                state="failed",
                stage="audio",
                message="Failed.",
                error="example",
                index_directory=directory,
            )
            write_index_status(
                state="ready",
                stage="complete",
                message="Ready.",
                index_directory=directory,
            )

            status_path = Path(directory) / "index_status.json"
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "ready")
            self.assertNotIn("error", payload)


if __name__ == "__main__":
    unittest.main()
