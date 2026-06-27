import unittest

from recorder_core import (
    build_ffmpeg_record_cmd,
    check_av_duration_gap,
    check_av_duration_gap_values,
    classify_failure_reason,
    get_retry_delay_seconds,
    normalize_recorder_config,
    is_audio_only_partial_probe,
    next_audio_only_probe_streak,
    normalize_output_mode,
    parse_timestamp_seconds,
    probe_av_durations_ffprobe,
    should_rotate_segment,
)


class RecorderCoreTests(unittest.TestCase):
    def test_classify_failure_reason(self):
        self.assertEqual(classify_failure_reason("直播已結束"), "live_ended")
        self.assertEqual(classify_failure_reason("HTTP 404"), "source_404")
        self.assertEqual(classify_failure_reason("有聲無畫"), "video_missing")
        self.assertEqual(classify_failure_reason("開頭無音訊（疑似開場異常）"), "audio_start_missing")
        self.assertEqual(classify_failure_reason("聲畫時長差異過大（120.0s）"), "av_duration_mismatch")
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
        self.assertEqual(cfg["stall_seconds"], 1)
        self.assertEqual(cfg["max_stall_restarts"], 0)
        self.assertEqual(cfg["backoff_base_seconds"], 20)
        self.assertEqual(cfg["backoff_max_seconds"], 20)
        self.assertFalse(should_rotate_segment(50, 120))
        self.assertTrue(should_rotate_segment(120, 120))

    def test_output_mode_and_ffmpeg_cmd(self):
        self.assertEqual(normalize_output_mode("remux"), "remux")
        self.assertEqual(normalize_output_mode("copy"), "copy")
        self.assertEqual(normalize_output_mode("invalid"), "remux")
        cfg = normalize_recorder_config({"output_mode": "copy"})
        self.assertEqual(cfg["output_mode"], "copy")

        remux_cmd = build_ffmpeg_record_cmd("ffmpeg", "http://example/live.m3u8", "out.ts", "remux")
        self.assertIn("-loglevel", remux_cmd)
        self.assertIn("error", remux_cmd)
        self.assertNotIn("-reconnect", remux_cmd)
        self.assertIn("+genpts+discardcorrupt", remux_cmd)

        reconnect_cmd = build_ffmpeg_record_cmd(
            "ffmpeg", "http://example/live.m3u8", "out.ts", "remux", ffmpeg_reconnect=True
        )
        self.assertIn("-reconnect", reconnect_cmd)
        self.assertIn("-map", remux_cmd)
        self.assertIn("0:v:0?", remux_cmd)
        self.assertIn("0:a:0?", remux_cmd)
        i_idx = remux_cmd.index("-i")
        mux_idx = remux_cmd.index("-max_muxing_queue_size")
        self.assertLess(i_idx, mux_idx)

        copy_cmd = build_ffmpeg_record_cmd("ffmpeg", "http://example/live.m3u8", "out.ts", "copy")
        self.assertNotIn("+genpts+discardcorrupt", copy_cmd)
        self.assertNotIn("0:v:0?", copy_cmd)

    def test_check_av_duration_gap(self):
        streams = [
            {"codec_type": "video", "duration": "100.0"},
            {"codec_type": "audio", "duration": "200.0"},
        ]
        ok, gap, video_duration, audio_duration = check_av_duration_gap(streams, 30)
        self.assertFalse(ok)
        self.assertAlmostEqual(gap, 100.0)
        self.assertAlmostEqual(video_duration, 100.0)
        self.assertAlmostEqual(audio_duration, 200.0)

        ok, gap, _, _ = check_av_duration_gap(
            [{"codec_type": "video", "duration": "100.0"}, {"codec_type": "audio", "duration": "110.0"}],
            30,
        )
        self.assertTrue(ok)
        self.assertAlmostEqual(gap, 10.0)

    def test_parse_timestamp_seconds(self):
        self.assertAlmostEqual(parse_timestamp_seconds("01:12:45.91"), 4365.91, places=1)
        self.assertAlmostEqual(parse_timestamp_seconds("12:45.5"), 765.5)

    def test_check_av_duration_gap_values(self):
        ok, gap, _, _ = check_av_duration_gap_values(100.0, 200.0, 30)
        self.assertFalse(ok)
        self.assertAlmostEqual(gap, 100.0)
        ok, gap, _, _ = check_av_duration_gap_values(None, 200.0, 30)
        self.assertTrue(ok)
        self.assertIsNone(gap)

    def test_audio_only_probe_streak(self):
        self.assertTrue(is_audio_only_partial_probe(None, 10.0))
        self.assertFalse(is_audio_only_partial_probe(10.0, 10.0))
        self.assertFalse(is_audio_only_partial_probe(None, 10.0, "ffprobe failed"))

        streak = 0
        streak = next_audio_only_probe_streak(streak, None, 10.0)
        self.assertEqual(streak, 1)
        streak = next_audio_only_probe_streak(streak, None, 12.0)
        self.assertEqual(streak, 2)
        self.assertGreaterEqual(
            next_audio_only_probe_streak(0, None, 10.0),
            1,
        )
        streak = next_audio_only_probe_streak(streak, 10.0, 12.0)
        self.assertEqual(streak, 0)
        streak = next_audio_only_probe_streak(1, None, None)
        self.assertEqual(streak, 0)

    def test_probe_av_durations_ffprobe_missing(self):
        video_duration, audio_duration, method, error = probe_av_durations_ffprobe(
            "E:/missing_dir_only",
            "missing.ts",
            ffprobe_bin=None,
        )
        self.assertIsNone(video_duration)
        self.assertEqual(method, "none")
        self.assertEqual(error, "ffprobe_missing")


if __name__ == "__main__":
    unittest.main()
