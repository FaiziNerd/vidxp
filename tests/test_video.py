import sys
import types
import unittest
from unittest.mock import patch

from vidxp.core.contracts import CancellationToken
from vidxp.core.video import FrameStreamStats, iter_frame_batches


class FakeCapture:
    def __init__(self, frames):
        self.frames = list(frames)
        self.position = 0
        self.read_calls = 0
        self.grab_calls = 0
        self.released = False

    def get(self, _):
        return 10.0

    def read(self):
        self.read_calls += 1
        if self.position >= len(self.frames):
            return False, None
        frame = self.frames[self.position]
        self.position += 1
        return True, frame

    def grab(self):
        self.grab_calls += 1
        if self.position >= len(self.frames):
            return False
        self.position += 1
        return True

    def release(self):
        self.released = True


class VideoFrameStreamTests(unittest.TestCase):
    def test_stride_advances_skipped_frames_without_materializing_them(self):
        capture = FakeCapture(["f0", "f1", "f2", "f3"])
        fake_cv2 = types.SimpleNamespace(
            CAP_PROP_FPS=5,
            VideoCapture=lambda _: capture,
        )
        stats = FrameStreamStats()

        with patch.dict(sys.modules, {"cv2": fake_cv2}):
            batches = list(
                iter_frame_batches(
                    "unused.mp4",
                    frame_stride=2,
                    batch_size=2,
                    cancellation=CancellationToken(),
                    stats=stats,
                )
            )

        self.assertEqual(
            [sample.frame_index for sample in batches[0]],
            [0, 2],
        )
        self.assertEqual(capture.grab_calls, 2)
        self.assertEqual(stats.frames_advanced, 4)
        self.assertEqual(stats.frames_materialized, 2)
        self.assertTrue(capture.released)


if __name__ == "__main__":
    unittest.main()
