import unittest

from recorder_core import (
    classify_failure_reason,
    get_retry_delay_seconds,
    normalize_recorder_config,
    should_rotate_segment,
)


class RecorderCoreTests(unittest.TestCase):
    def test_classify_failure_reason(self):
        self.assertEqual(classify_failure_reason("直播已結束"), "live_ended")
        self.assertEqual(classify_failure_reason("HTTP 404"), "source_404")
        self.assertEqual(classify_failure_reason("有聲無畫"), "video_missing")
        self.assertEqual(classify_failure_reason("開頭無音訊（疑似開場異常）"), "audio_start_missing")
        self.assertEqual(classify_failure_reason("whatever", stalled=True), "network_stall")

    def test_retry_delay(self):
        self.assertEqual(get_retry_delay_seconds(1, 3, 2, 5, 60), 2)
        self.assertEqual(get_retry_delay_seconds(3, 3, 2, 5, 60), 2)
        self.assertEqual(get_retry_delay_seconds(4, 3, 2, 5, 60), 5)
        self.assertEqual(get_retry_delay_seconds(5, 3, 2, 5, 60), 10)
        self.assertEqual(get_retry_delay_seconds(20, 3, 2, 5, 60), 60)

    def test_normalize_config_and_rotate(self):
        cfg = normalize_recorder_config({
            "stall_seconds": 1,
            "max_stall_restarts": -1,
            "backoff_base_seconds": 20,
            "backoff_max_seconds": 10,
        })
        self.assertEqual(cfg["stall_seconds"], 3)
        self.assertEqual(cfg["max_stall_restarts"], 0)
        self.assertEqual(cfg["backoff_base_seconds"], 20)
        self.assertEqual(cfg["backoff_max_seconds"], 20)
        self.assertFalse(should_rotate_segment(50, 120))
        self.assertTrue(should_rotate_segment(120, 120))


if __name__ == "__main__":
    unittest.main()
