import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from vidxp import index_worker
from vidxp.index_state import IndexingInProgressError


class FakeProcess:
    def __init__(self, **options):
        self.options = options
        self.alive = False

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive


class FakeEvent:
    def __init__(self):
        self.set_called = False

    def set(self):
        self.set_called = True

    def is_set(self):
        return self.set_called


class FakeContext:
    def __init__(self):
        self.process = None
        self.event = FakeEvent()

    def Event(self):
        return self.event

    def Process(self, **options):
        self.process = FakeProcess(**options)
        return self.process


class IndexWorkerTests(unittest.TestCase):
    def setUp(self):
        index_worker._process = None
        index_worker._cancel_event = None
        self.service = Mock()
        self.service.index_directory = Path("selected-index")
        self.service.device = "cuda"
        self.service.indexing_in_progress.return_value = False

    def tearDown(self):
        index_worker._process = None
        index_worker._cancel_event = None

    def test_worker_starts_indexing_in_a_separate_process(self):
        context = FakeContext()

        with patch.object(index_worker, "get_context", return_value=context):
            index_worker.start_indexing(
                "video.mp4",
                "source.mp4",
                self.service,
                modalities=("scene",),
            )

        self.assertTrue(context.process.is_alive())
        self.assertEqual(context.process.options["name"], "vidxp-indexer")
        self.assertTrue(context.process.options["daemon"])
        self.assertEqual(
            context.process.options["args"],
            (
                "video.mp4",
                "source.mp4",
                context.event,
                "selected-index",
                "cuda",
                ("scene",),
            ),
        )
        self.assertIs(context.process.options["target"], index_worker._run_indexing)

    def test_worker_process_reconstructs_the_selected_service(self):
        service = Mock()
        with patch.object(
            index_worker,
            "VidXPService",
            return_value=service,
        ) as service_type:
            index_worker._run_indexing(
                "video.mp4",
                "source.mp4",
                FakeEvent(),
                "selected-index",
                "cuda",
                ("scene",),
            )

        service_type.assert_called_once_with("selected-index", device="cuda")
        service.create_index.assert_called_once()
        self.assertEqual(
            service.create_index.call_args.kwargs["source_name"],
            "source.mp4",
        )
        self.assertEqual(
            service.create_index.call_args.kwargs["modalities"],
            ("scene",),
        )

    def test_worker_rejects_a_second_indexing_run(self):
        context = FakeContext()

        with patch.object(index_worker, "get_context", return_value=context):
            index_worker.start_indexing(
                "video.mp4",
                "source.mp4",
                self.service,
                modalities=("scene",),
            )
            with self.assertRaises(IndexingInProgressError):
                index_worker.start_indexing(
                    "video.mp4",
                    "source.mp4",
                    self.service,
                    modalities=("scene",),
                )

    def test_existing_service_run_remains_visible(self):
        self.service.indexing_in_progress.return_value = True

        self.assertTrue(index_worker.indexing_in_progress(self.service))

    def test_cancellation_requests_are_cooperative(self):
        context = FakeContext()
        with patch.object(index_worker, "get_context", return_value=context):
            index_worker.start_indexing(
                "video.mp4",
                "source.mp4",
                self.service,
                modalities=("scene",),
            )

        self.assertTrue(index_worker.cancel_indexing())
        self.assertTrue(context.event.set_called)


if __name__ == "__main__":
    unittest.main()
