import unittest
from unittest.mock import patch

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

    def tearDown(self):
        index_worker._process = None
        index_worker._cancel_event = None

    @patch.object(index_worker, "in_process_indexing", return_value=False)
    def test_worker_starts_indexing_in_a_separate_process(self, _):
        context = FakeContext()

        with patch.object(index_worker, "get_context", return_value=context):
            index_worker.start_indexing("video.mp4", "source.mp4")

        self.assertTrue(context.process.is_alive())
        self.assertEqual(context.process.options["name"], "vidxp-indexer")
        self.assertTrue(context.process.options["daemon"])
        self.assertEqual(
            context.process.options["args"],
            ("video.mp4", "source.mp4", context.event),
        )
        self.assertIs(context.process.options["target"], index_worker._run_indexing)

    @patch.object(index_worker, "in_process_indexing", return_value=False)
    def test_worker_rejects_a_second_indexing_run(self, _):
        context = FakeContext()

        with patch.object(index_worker, "get_context", return_value=context):
            index_worker.start_indexing("video.mp4", "source.mp4")
            with self.assertRaises(IndexingInProgressError):
                index_worker.start_indexing("video.mp4", "source.mp4")

    @patch.object(index_worker, "in_process_indexing", return_value=True)
    def test_existing_in_process_run_remains_visible(self, _):
        self.assertTrue(index_worker.indexing_in_progress())

    @patch.object(index_worker, "in_process_indexing", return_value=False)
    def test_cancellation_requests_are_cooperative(self, _):
        context = FakeContext()
        with patch.object(index_worker, "get_context", return_value=context):
            index_worker.start_indexing("video.mp4", "source.mp4")

        self.assertTrue(index_worker.cancel_indexing())
        self.assertTrue(context.event.set_called)


if __name__ == "__main__":
    unittest.main()
