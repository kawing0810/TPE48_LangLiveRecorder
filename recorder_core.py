#!/usr/bin/python
# coding=utf-8

import json
import os
import re
import subprocess
from copy import deepcopy


DEFAULT_RECORDER_CONFIG = {
    "stall_seconds": 20,
    "max_stall_restarts": 20,
    "stall_check_after_seconds": 30,
    "min_segment_seconds": 120,
    "fast_retry_limit": 3,
    "fast_retry_delay_seconds": 2,
    "backoff_base_seconds": 5,
    "backoff_max_seconds": 60,
    "output_mode": "remux",
    "max_av_duration_gap_seconds": 30,
    "av_check_interval_seconds": 3,
    "audio_only_probe_fail_count": 1,
    "ffmpeg_loglevel": "error",
    "ffmpeg_reconnect": False,
}

OUTPUT_MODES = ("copy", "remux")
FFMPEG_LOGLEVELS = (
    "quiet", "panic", "fatal", "error", "warning", "info", "verbose", "debug", "trace",
)
FFMPEG_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36"
)
FFMPEG_HEADERS = "Cookie: licenseUID=eF9e9f798fedD28ee49Df472DE957B"


def _to_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def normalize_recorder_config(raw_cfg):
    cfg = deepcopy(DEFAULT_RECORDER_CONFIG)
    source = raw_cfg or {}
    output_mode = source.get("output_mode", cfg["output_mode"])
    for key, default in DEFAULT_RECORDER_CONFIG.items():
        if key in ("output_mode", "ffmpeg_loglevel", "ffmpeg_reconnect"):
            continue
        cfg[key] = _to_int(source.get(key, default), default)

    # Safety bounds: avoid pathological settings that break recorder loops.
    cfg["stall_seconds"] = clamp(cfg["stall_seconds"], 1, 300)
    cfg["max_stall_restarts"] = clamp(cfg["max_stall_restarts"], 0, 200)
    cfg["stall_check_after_seconds"] = clamp(cfg["stall_check_after_seconds"], 0, 600)
    cfg["min_segment_seconds"] = clamp(cfg["min_segment_seconds"], 10, 3600)
    cfg["fast_retry_limit"] = clamp(cfg["fast_retry_limit"], 0, 50)
    cfg["fast_retry_delay_seconds"] = clamp(cfg["fast_retry_delay_seconds"], 1, 120)
    cfg["backoff_base_seconds"] = clamp(cfg["backoff_base_seconds"], 1, 300)
    cfg["backoff_max_seconds"] = clamp(cfg["backoff_max_seconds"], 1, 3600)
    if cfg["backoff_max_seconds"] < cfg["backoff_base_seconds"]:
        cfg["backoff_max_seconds"] = cfg["backoff_base_seconds"]
    cfg["max_av_duration_gap_seconds"] = clamp(
        _to_int(source.get("max_av_duration_gap_seconds", cfg["max_av_duration_gap_seconds"]),
                cfg["max_av_duration_gap_seconds"]),
        5,
        600,
    )
    cfg["av_check_interval_seconds"] = clamp(
        _to_int(source.get("av_check_interval_seconds", cfg["av_check_interval_seconds"]),
                cfg["av_check_interval_seconds"]),
        3,
        1800,
    )
    cfg["audio_only_probe_fail_count"] = clamp(
        _to_int(source.get("audio_only_probe_fail_count", cfg["audio_only_probe_fail_count"]),
                cfg["audio_only_probe_fail_count"]),
        1,
        20,
    )
    cfg["output_mode"] = normalize_output_mode(output_mode)
    cfg["ffmpeg_loglevel"] = normalize_ffmpeg_loglevel(
        source.get("ffmpeg_loglevel", cfg["ffmpeg_loglevel"])
    )
    cfg["ffmpeg_reconnect"] = normalize_ffmpeg_reconnect(
        source.get("ffmpeg_reconnect", cfg["ffmpeg_reconnect"])
    )
    return cfg


def normalize_ffmpeg_loglevel(value):
    level = str(value or "error").strip().lower()
    if level not in FFMPEG_LOGLEVELS:
        return "error"
    return level


def normalize_ffmpeg_reconnect(value):
    if isinstance(value, bool):
        return value
    text = str(value or "true").strip().lower()
    return text not in ("0", "false", "no", "off")


def normalize_output_mode(value):
    mode = str(value or "remux").strip().lower()
    if mode not in OUTPUT_MODES:
        return "remux"
    return mode


def build_ffmpeg_record_cmd(
    ffmpeg_bin,
    live_url,
    output_file,
    output_mode="remux",
    ffmpeg_loglevel="error",
    ffmpeg_reconnect=False,
):
    mode = normalize_output_mode(output_mode)
    loglevel = normalize_ffmpeg_loglevel(ffmpeg_loglevel)
    cmd = [ffmpeg_bin]
    if mode == "remux":
        cmd.extend(["-fflags", "+genpts+discardcorrupt"])
    cmd.extend([
        "-m3u8_hold_counters", "100",
        "-hide_banner",
        "-loglevel", loglevel,
        "-stats",
    ])
    if normalize_ffmpeg_reconnect(ffmpeg_reconnect):
        cmd.extend([
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
        ])
    cmd.extend([
        "-user_agent", FFMPEG_USER_AGENT,
        "-headers", FFMPEG_HEADERS,
        "-i", live_url,
    ])
    if mode == "remux":
        # Muxer/output options must come after -i (otherwise ffmpeg exits immediately).
        cmd.extend([
            "-avoid_negative_ts", "make_zero",
            "-max_muxing_queue_size", "1024",
            "-map", "0:v:0?",
            "-map", "0:a:0?",
        ])
    cmd.extend(["-c", "copy", "-y", "-report", output_file])
    return cmd


def classify_failure_reason(reason_text, stalled=False):
    text = (reason_text or "").lower()
    reason = reason_text or ""
    if stalled:
        return "network_stall"
    if "直播已結束" in reason:
        return "live_ended"
    if "404" in text or "not found" in text:
        return "source_404"
    if "開頭無音訊" in reason or "無音訊串流" in reason:
        return "audio_start_missing"
    if "有聲無畫" in reason or "缺少視訊串流" in reason:
        return "video_missing"
    if "聲畫時長差異" in reason:
        return "av_duration_mismatch"
    if "輸出檔案過小" in reason or "找不到輸出檔案" in reason:
        return "output_small_or_missing"
    if "ffprobe" in reason:
        return "probe_failed"
    return "other"


def get_retry_delay_seconds(restart_count, fast_retry_limit, fast_retry_delay_seconds, backoff_base_seconds, backoff_max_seconds):
    if restart_count <= fast_retry_limit:
        return fast_retry_delay_seconds
    backoff_step = restart_count - fast_retry_limit
    delay = backoff_base_seconds * (2 ** (backoff_step - 1))
    return min(delay, backoff_max_seconds)


def should_rotate_segment(elapsed_seconds, min_segment_seconds):
    return int(elapsed_seconds) >= int(min_segment_seconds)


def stream_duration_seconds(stream):
    if not isinstance(stream, dict):
        return None
    duration = stream.get("duration")
    if duration is None:
        return None
    try:
        value = float(duration)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def check_av_duration_gap(streams, max_gap_seconds=30):
    video_duration = None
    audio_duration = None
    for stream in streams or []:
        codec = stream.get("codec_type")
        duration = stream_duration_seconds(stream)
        if duration is None:
            continue
        if codec == "video":
            video_duration = duration
        elif codec == "audio":
            audio_duration = duration
    return check_av_duration_gap_values(video_duration, audio_duration, max_gap_seconds)


def check_av_duration_gap_values(video_duration, audio_duration, max_gap_seconds=30):
    if video_duration is None or audio_duration is None:
        return True, None, video_duration, audio_duration
    gap = abs(float(video_duration) - float(audio_duration))
    return gap <= float(max_gap_seconds), gap, video_duration, audio_duration


def is_audio_only_partial_probe(video_duration, audio_duration, probe_error=""):
    if probe_error:
        return False
    return audio_duration is not None and video_duration is None


def next_audio_only_probe_streak(streak, video_duration, audio_duration, probe_error=""):
    if is_audio_only_partial_probe(video_duration, audio_duration, probe_error):
        return streak + 1
    return 0


def resolve_ffprobe_bin(base_path):
    candidates = [
        os.path.join(base_path, "ffprobe"),
        os.path.join(base_path, "ffprobe.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def resolve_ffmpeg_bin(base_path):
    candidates = [
        os.path.join(base_path, "ffmpeg"),
        os.path.join(base_path, "ffmpeg.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_timestamp_seconds(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if ":" not in text:
            seconds = float(text)
            return seconds if seconds >= 0 else None
        parts = text.split(":")
        parts = [float(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
    except (TypeError, ValueError):
        return None
    return None


def probe_stream_duration_via_ffmpeg(ffmpeg_bin, output_file, map_spec, timeout_seconds=600):
    if not ffmpeg_bin or not os.path.exists(output_file):
        return None
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-i", output_file,
        "-map", map_spec,
        "-c", "copy",
        "-f", "null",
        "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    times = re.findall(r"time=\s*([\d:.]+)", result.stderr or "")
    if not times:
        return None
    return parse_timestamp_seconds(times[-1])


def probe_av_durations(base_path, output_file, ffmpeg_bin=None, ffprobe_bin=None):
    ffmpeg_bin = ffmpeg_bin or resolve_ffmpeg_bin(base_path)
    ffprobe_bin = ffprobe_bin or resolve_ffprobe_bin(base_path)
    method = "none"
    error = ""

    if ffprobe_bin:
        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_streams",
            "-of", "json",
            output_file,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False, timeout=120)
            if result.returncode == 0 and result.stdout:
                streams = json.loads(result.stdout).get("streams", [])
                ok, gap, video_duration, audio_duration = check_av_duration_gap(streams, 30)
                if video_duration is not None and audio_duration is not None:
                    return video_duration, audio_duration, "ffprobe", ""
                method = "ffprobe_partial"
            else:
                error = (result.stderr or "ffprobe failed").strip()[:200]
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
            error = str(exc)

    if ffmpeg_bin:
        video_duration = probe_stream_duration_via_ffmpeg(ffmpeg_bin, output_file, "0:v:0")
        audio_duration = probe_stream_duration_via_ffmpeg(ffmpeg_bin, output_file, "0:a:0")
        if video_duration is not None and audio_duration is not None:
            return video_duration, audio_duration, "ffmpeg_decode", error
        if not error:
            error = "ffmpeg decode probe missing stream durations"

    return None, None, method, error


def probe_av_durations_ffprobe(base_path, output_file, ffprobe_bin=None, timeout_seconds=8):
    """Fast in-recording probe; requires ffprobe (typically one TS segment interval)."""
    ffprobe_bin = ffprobe_bin or resolve_ffprobe_bin(base_path)
    if not ffprobe_bin:
        return None, None, "none", "ffprobe_missing"
    if not os.path.exists(output_file):
        return None, None, "none", "file_missing"
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "stream=codec_type,duration",
        "-of", "json",
        output_file,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            return None, None, "ffprobe", (result.stderr or "ffprobe failed").strip()[:200]
        streams = json.loads(result.stdout or "{}").get("streams", [])
        video_duration = None
        audio_duration = None
        for stream in streams:
            codec = stream.get("codec_type")
            duration = stream_duration_seconds(stream)
            if duration is None:
                continue
            if codec == "video":
                video_duration = duration
            elif codec == "audio":
                audio_duration = duration
        if video_duration is None or audio_duration is None:
            return video_duration, audio_duration, "ffprobe_partial", ""
        return video_duration, audio_duration, "ffprobe", ""
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
        return None, None, "ffprobe", str(exc)
