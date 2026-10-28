import unittest
from unittest.mock import Mock
from ai_vision.safety.shared_review_probe import probe_latest


class SharedReviewProbeTests(unittest.TestCase):
    def test_temporary_lock_retries_then_returns_new_sample(self):
        sample=object();reader=Mock(side_effect=[PermissionError(),sample]);pause=Mock()
        self.assertIs(probe_latest('frame',reader=reader,pause=pause),sample)
        self.assertEqual(reader.call_count,2);pause.assert_called_once_with(.05)

    def test_persistent_lock_is_bounded_and_never_returns_cached_image(self):
        reader=Mock(side_effect=PermissionError());pause=Mock()
        self.assertIsNone(probe_latest('frame',reader=reader,pause=pause))
        self.assertEqual(reader.call_count,5);self.assertEqual(pause.call_count,4)

    def test_corrupt_frame_is_not_disguised_as_lock_contention(self):
        with self.assertRaises(ValueError):probe_latest('frame',reader=Mock(side_effect=ValueError('broken')))
