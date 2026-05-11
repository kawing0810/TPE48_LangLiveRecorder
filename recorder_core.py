#!/usr/bin/python
# coding=utf-8

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
}


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
    for key, default in DEFAULT_RECORDER_CONFIG.items():
        cfg[key] = _to_int(source.get(key, default), default)

    # Safety bounds: avoid pathological settings that break recorder loops.
    cfg["stall_seconds"] = clamp(cfg["stall_seconds"], 3, 300)
    cfg["max_stall_restarts"] = clamp(cfg["max_stall_restarts"], 0, 200)
    cfg["stall_check_after_seconds"] = clamp(cfg["stall_check_after_seconds"], 0, 600)
    cfg["min_segment_seconds"] = clamp(cfg["min_segment_seconds"], 10, 3600)
    cfg["fast_retry_limit"] = clamp(cfg["fast_retry_limit"], 0, 50)
    cfg["fast_retry_delay_seconds"] = clamp(cfg["fast_retry_delay_seconds"], 1, 120)
    cfg["backoff_base_seconds"] = clamp(cfg["backoff_base_seconds"], 1, 300)
    cfg["backoff_max_seconds"] = clamp(cfg["backoff_max_seconds"], 1, 3600)
    if cfg["backoff_max_seconds"] < cfg["backoff_base_seconds"]:
        cfg["backoff_max_seconds"] = cfg["backoff_base_seconds"]
    return cfg


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
