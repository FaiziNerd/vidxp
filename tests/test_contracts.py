import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from vidxp.core.contracts import (
    CancellationToken,
    IndexCancelledError,
    IndexConfig,
    SearchHit,
    SearchResult,
    VideoSource,
    stable_source_id,
)


class ContractTests(unittest.TestCase):
    def test_stable_source_ids_escape_delimiters_without_collisions(self):
        first = stable_source_id("run:a", "video", "scene", "1")
        second = stable_source_id("run", "a:video", "scene", "1")

        self.assertNotEqual(first, second)
        self.assertEqual(
            stable_source_id("r", "فيديو:1", "scene", "0"),
            stable_source_id("r", "فيديو:1", "scene", "0"),
        )
        self.assertEqual(first.count(":"), 3)

    def test_config_is_validated_and_run_paths_are_isolated(self):
        with TemporaryDirectory() as directory:
            first = IndexConfig(
                dataset="didemo",
                split="test",
                run_id="stride-1",
                output_root=directory,
                enabled_modalities=("scene",),
            )
            second = IndexConfig(
                dataset="didemo",
                split="test",
                run_id="stride-2",
                output_root=directory,
                enabled_modalities=("scene",),
            )

            self.assertNotEqual(first.run_directory, second.run_directory)
            self.assertEqual(
                first.index_directory,
                Path(directory) / "didemo" / "stride-1" / "index",
            )
            self.assertEqual(
                first.fingerprint(),
                first.for_video("video-1").fingerprint(),
            )
            relocated = IndexConfig(
                dataset="didemo",
                split="test",
                run_id="stride-1",
                output_root=str(Path(directory) / "relocated"),
                storage_directory=str(Path(directory) / "custom-index"),
                enabled_modalities=("scene",),
            )
            self.assertEqual(first.fingerprint(), relocated.fingerprint())

    def test_path_objects_are_normalized_for_manifest_serialization(self):
        config = IndexConfig(
            output_root=Path("benchmark-output"),
            storage_directory=Path("benchmark-index"),
        )

        self.assertEqual(config.output_root, "benchmark-output")
        self.assertEqual(config.storage_directory, "benchmark-index")
        self.assertEqual(config.to_dict()["run_directory"], "benchmark-index")

    def test_invalid_config_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "At least one"):
            IndexConfig(enabled_modalities=())
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            IndexConfig(enabled_modalities=("ocr",))
        with self.assertRaisesRegex(ValueError, "frame_stride"):
            IndexConfig(frame_stride=0)
        with self.assertRaisesRegex(ValueError, "cannot be"):
            IndexConfig(dataset="..").run_directory
        with self.assertRaisesRegex(ValueError, "reserved on Windows"):
            IndexConfig(dataset="CON.txt").run_directory
        with self.assertRaisesRegex(ValueError, "distinct"):
            IndexConfig(collection_names=("shared", "shared", "actor"))
        with self.assertRaisesRegex(ValueError, "3-512"):
            IndexConfig(collection_names=("a", "scene", "actor"))
        with self.assertRaisesRegex(ValueError, "vector_distance"):
            IndexConfig(vector_distance="unknown")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            VideoSource(path="video.mp4", checksum="not-a-checksum")

    def test_result_contract_serializes_complete_ranked_hits(self):
        hit = SearchHit(
            rank=1,
            video_id="video-1",
            start=1.0,
            end=2.0,
            score=-0.2,
            raw_distance=0.2,
            modality="scene",
            source_id="run:video-1:scene:f1",
            metadata={"frame_index": 1},
        )
        result = SearchResult(
            query_id="q1",
            query="yellow taxi",
            modality="scene",
            hits=(hit,),
        )

        self.assertEqual(result.to_prediction()["q1"][0]["video_id"], "video-1")
        self.assertEqual(result.to_dict()["hits"][0]["raw_distance"], 0.2)

    def test_cancellation_is_cooperative(self):
        token = CancellationToken()
        token.raise_if_cancelled()
        token.cancel()
        with self.assertRaises(IndexCancelledError):
            token.raise_if_cancelled()


if __name__ == "__main__":
    unittest.main()
