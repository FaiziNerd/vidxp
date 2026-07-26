import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    StorageRecord,
)
from vidxp.core.storage import IndexStorage, directory_size, metadata_filter


class FakeCollection:
    def __init__(self):
        self.upserts = []
        self.deletes = []
        self.query_options = None
        self.get_options = None

    def upsert(self, **options):
        self.upserts.append(options)

    def delete(self, **options):
        self.deletes.append(options)

    def query(self, **options):
        self.query_options = options
        return {
            "ids": [["source-1"]],
            "metadatas": [[{"video_id": "video-1"}]],
            "distances": [[0.25]],
        }

    def get(self, **options):
        self.get_options = options
        return {
            "metadatas": [
                {
                    "frame_index": 3,
                    "detection_id": "d3",
                    "cluster_id": "1",
                },
                {
                    "frame_index": 1,
                    "detection_id": "d1",
                    "cluster_id": "1",
                },
            ]
        }


class FakeClient:
    def __init__(self, collection):
        self.value = collection
        self.collection_options = None
        self.collection_calls = 0

    def get_or_create_collection(self, **options):
        self.collection_calls += 1
        self.collection_options = options
        return self.value


def fake_storage(config, collection):
    storage = object.__new__(IndexStorage)
    storage.config = config
    storage.path = config.index_directory
    storage.client = FakeClient(collection)
    storage._collections = {}
    storage._names = {
        "dialogue": "dialogue",
        "scene": "scene",
        "actor": "actor",
    }
    return storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.config = IndexConfig(
            dataset="didemo",
            split="test",
            run_id="run-1",
            enabled_modalities=("scene",),
        )

    def test_upserts_are_split_into_declared_write_batches(self):
        collection = FakeCollection()
        storage = fake_storage(self.config, collection)
        records = [
            StorageRecord(
                source_id=f"source-{index}",
                embedding=[float(index)],
                metadata={"index": index},
            )
            for index in range(5)
        ]

        stored = storage.upsert(
            "scene",
            records,
            batch_size=2,
            cancellation=CancellationToken(),
        )

        self.assertEqual(stored, 5)
        self.assertEqual(
            [len(call["ids"]) for call in collection.upserts],
            [2, 2, 1],
        )
        self.assertEqual(
            storage.client.collection_options["metadata"],
            {"hnsw:space": "l2"},
        )

        storage.upsert(
            "scene",
            records[:1],
            batch_size=1,
            cancellation=CancellationToken(),
        )
        self.assertEqual(storage.client.collection_calls, 1)

    def test_query_requests_distances_and_applies_run_and_video_filter(self):
        collection = FakeCollection()
        storage = fake_storage(self.config, collection)

        rows = storage.query(
            "scene",
            [0.1, 0.2],
            top_k=7,
            video_id="video-1",
        )

        self.assertEqual(rows[0]["raw_distance"], 0.25)
        self.assertEqual(
            collection.query_options["include"],
            ["metadatas", "distances"],
        )
        self.assertEqual(collection.query_options["n_results"], 7)
        clauses = collection.query_options["where"]["$and"]
        self.assertIn({"video_id": "video-1"}, clauses)
        self.assertIn({"run_id": "run-1"}, clauses)

    def test_actor_detections_are_chronologically_ordered(self):
        collection = FakeCollection()
        storage = fake_storage(self.config, collection)

        detections = storage.actor_detections(
            video_id="video-1",
            cluster_id="1",
        )

        self.assertEqual(
            [item["detection_id"] for item in detections],
            ["d1", "d3"],
        )

    def test_actor_cluster_cleanup_remains_scoped_to_video_and_run(self):
        collection = FakeCollection()
        storage = fake_storage(self.config, collection)

        storage.delete_actor_cluster("video-1", "3")

        clauses = collection.deletes[0]["where"]["$and"]
        self.assertIn({"run_id": "run-1"}, clauses)
        self.assertIn({"video_id": "video-1"}, clauses)
        self.assertIn({"cluster_id": "3"}, clauses)

    def test_directory_size_only_counts_files_under_requested_path(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / "a.bin").write_bytes(b"12")
            (root / "nested" / "b.bin").write_bytes(b"345")

            self.assertEqual(directory_size(root), 5)

    def test_metadata_filter_keeps_run_identity_without_video_filter(self):
        where = metadata_filter(self.config)
        self.assertNotIn({"video_id": None}, where["$and"])


if __name__ == "__main__":
    unittest.main()
