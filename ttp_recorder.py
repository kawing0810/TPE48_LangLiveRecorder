#!/usr/bin/python
#coding=utf-8

import urllib.request
import json
import ssl
from datetime import datetime
import time
from time import gmtime
from time import strftime
import os
import sys
import subprocess
import argparse
import ctypes
import re
import hashlib
from urllib.parse import urlparse


from ttp_langLiveRecorder import ttpLangLiveRecorder
from recorder_core import (
    classify_failure_reason,
    get_retry_delay_seconds,
    normalize_recorder_config,
    should_rotate_segment,
)

sys.stdout.reconfigure(encoding='utf-8')

current_path = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(current_path, "data")
os.makedirs(DATA_DIR, exist_ok=True)
COVER_CACHE_FILE = os.path.join(DATA_DIR, "liveimg_cache.json")
COVER_DIR = os.path.join(current_path, "liveimg")
ACTIVE_RECORDINGS_FILE = os.path.join(DATA_DIR, "active_recordings.json")
RECORDING_HISTORY_FILE = os.path.join(DATA_DIR, "recording_history.json")
CONFIG_FILE = os.path.join(current_path, "config.json")
STALL_SECONDS = 20
MAX_STALL_RESTARTS = 20
STALL_CHECK_AFTER_SECONDS = 30
MIN_SEGMENT_SECONDS = 120
FAST_RETRY_LIMIT = 3
FAST_RETRY_DELAY_SECONDS = 2
BACKOFF_BASE_SECONDS = 5
BACKOFF_MAX_SECONDS = 60

langlive_id = "3650734"
label = "TTP"
os.chdir(current_path)

parser = argparse.ArgumentParser()
parser.add_argument('uid', type=str, help="lang live id")
parser.add_argument('--label', type=str, help="label", default="TTP")

args = parser.parse_args()

# print(parser.format_help())

langlive_id = args.uid
label = args.label


def loadConfig():
    default_cfg = {}
    if not os.path.exists(CONFIG_FILE):
        return default_cfg
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_cfg


def applyRecorderConfig():
    global STALL_SECONDS
    global MAX_STALL_RESTARTS
    global STALL_CHECK_AFTER_SECONDS
    global MIN_SEGMENT_SECONDS
    global FAST_RETRY_LIMIT
    global FAST_RETRY_DELAY_SECONDS
    global BACKOFF_BASE_SECONDS
    global BACKOFF_MAX_SECONDS

    cfg = normalize_recorder_config(loadConfig().get("recorder", {}))
    STALL_SECONDS = cfg["stall_seconds"]
    MAX_STALL_RESTARTS = cfg["max_stall_restarts"]
    STALL_CHECK_AFTER_SECONDS = cfg["stall_check_after_seconds"]
    MIN_SEGMENT_SECONDS = cfg["min_segment_seconds"]
    FAST_RETRY_LIMIT = cfg["fast_retry_limit"]
    FAST_RETRY_DELAY_SECONDS = cfg["fast_retry_delay_seconds"]
    BACKOFF_BASE_SECONDS = cfg["backoff_base_seconds"]
    BACKOFF_MAX_SECONDS = cfg["backoff_max_seconds"]

def doLiveRecording(live_url, output_file):
    tstart = time.time()
    success = False
    stalled = False
    try:
        ffmpg_bin = os.path.join("./", current_path, "ffmpeg")
        cmd = [
            ffmpg_bin,
            "-m3u8_hold_counters", "100",
            "-hide_banner",
            "-loglevel", "warning",
            "-stats",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36",
            "-headers", "Cookie: licenseUID=eF9e9f798fedD28ee49Df472DE957B",
            "-i", live_url,
            "-c", "copy",
            "-y",
            "-report",
            output_file
        ]

        message = "START@ %s (%s)" % (nickname, langlive_id)
        print(message)
        process = subprocess.Popen(cmd)

        last_size = -1
        last_grow_ts = time.time()
        check_start_ts = time.time()
        while process.poll() is None:
            time.sleep(1)
            size_now = os.path.getsize(output_file) if os.path.exists(output_file) else 0
            if size_now > last_size:
                last_size = size_now
                last_grow_ts = time.time()
                continue

            # 剛開錄前幾秒常有切片等待，避免太早誤判卡住
            if time.time() - check_start_ts < STALL_CHECK_AFTER_SECONDS:
                continue

            if time.time() - last_grow_ts >= STALL_SECONDS:
                stalled = True
                print("** stalled for %ss (after %ss grace), restarting recorder..." % (STALL_SECONDS, STALL_CHECK_AFTER_SECONDS))
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                break

        if not stalled:
            success = (process.returncode == 0)

    except Exception as e:
        print("An exception occurred", e)
		
    #calculate elapsed time
    tend = time.time()
    elapsed = tend - tstart
    hms = strftime("%H:%M:%S", gmtime(elapsed))
    message = "END@ %s (%s) -elapsed %s" % (nickname, langlive_id, hms)
    print(message)
    return success, int(elapsed), stalled


def hasAudioPacketsAtStart(output_file, window_seconds):
    ffprobe_bin = os.path.join("./", current_path, "ffprobe")
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "a",
        "-show_packets",
        "-show_entries", "packet=pts_time",
        "-read_intervals", "%+{0}".format(int(window_seconds)),
        "-of", "json",
        output_file
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return False
        probe_data = json.loads(result.stdout) if result.stdout else {}
        packets = probe_data.get("packets", [])
        return len(packets) > 0
    except Exception:
        return False


def validateRecordingFile(output_file, elapsed_seconds):
    if not os.path.exists(output_file):
        return False, "找不到輸出檔案", {"has_video": False, "has_audio": False}

    file_size = os.path.getsize(output_file)
    if file_size < 1024 * 200:
        return False, "輸出檔案過小", {"has_video": False, "has_audio": False}

    ffprobe_bin = os.path.join("./", current_path, "ffprobe")
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_streams",
        "-of", "json",
        output_file
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return False, "ffprobe 檢查失敗", {"has_video": False, "has_audio": False}

        probe_data = json.loads(result.stdout) if result.stdout else {}
        streams = probe_data.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        if has_audio and not has_video:
            return False, "有聲無畫", {"has_video": False, "has_audio": True}
        if not has_video and not has_audio:
            return False, "無音訊與視訊串流", {"has_video": False, "has_audio": False}
        if not has_video:
            return False, "缺少視訊串流", {"has_video": False, "has_audio": has_audio}
        if not has_audio:
            return False, "無音訊串流（疑似開場異常）", {"has_video": True, "has_audio": False}

        start_window = 20
        if elapsed_seconds < start_window:
            start_window = max(5, int(elapsed_seconds))
        if not hasAudioPacketsAtStart(output_file, start_window):
            return False, "開頭無音訊（疑似開場異常）", {"has_video": True, "has_audio": True}

        return True, "正常", {"has_video": True, "has_audio": True}
    except Exception as e:
        return False, "檢查例外: {0}".format(e), {"has_video": False, "has_audio": False}

def getHDLiveUrl(url):
    hd_url = re.sub(r'\/(\d+Y)\/(playlist).m3u8(.*)', r'/\1_s3/\2.m3u8', url)
    if isM3UFile(hd_url):
        url = hd_url
    return url

def isM3UFile(url):
    bResult = False
    response = urllib.request.urlopen(url, timeout=10)
    content = response.read().decode("UTF-8")
    if content.find("#EXTM3U") >= 0:
        bResult = True
    return bResult


def loadCoverCache():
    if not os.path.exists(COVER_CACHE_FILE):
        return {"url_map": {}, "hash_map": {}}
    try:
        with open(COVER_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
            # Backward compatible: old cache format was {url: file}
            if isinstance(cache, dict) and "url_map" not in cache:
                return {"url_map": cache, "hash_map": {}}
            if not isinstance(cache, dict):
                return {"url_map": {}, "hash_map": {}}
            return {
                "url_map": cache.get("url_map", {}),
                "hash_map": cache.get("hash_map", {})
            }
    except Exception:
        return {"url_map": {}, "hash_map": {}}


def saveCoverCache(cache_data):
    try:
        if not isinstance(cache_data, dict):
            cache_data = {"url_map": {}, "hash_map": {}}
        cache_data.setdefault("url_map", {})
        cache_data.setdefault("hash_map", {})
        with open(COVER_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("** failed to update cover cache", e)


def saveLiveCoverImage(image_url, output_file_stem):
    if image_url == "":
        return
    os.makedirs(COVER_DIR, exist_ok=True)
    cache_data = loadCoverCache()
    url_map = cache_data.get("url_map", {})
    hash_map = cache_data.get("hash_map", {})
    if image_url in url_map:
        print("** skip duplicated live cover", image_url)
        return
    try:
        response = urllib.request.urlopen(image_url, timeout=10)
        image_data = response.read()
        image_hash = hashlib.sha256(image_data).hexdigest()
        if image_hash in hash_map:
            existed_file = hash_map.get(image_hash, "")
            url_map[image_url] = existed_file
            cache_data["url_map"] = url_map
            print("** skip duplicated live cover by content hash", image_url)
            saveCoverCache(cache_data)
            return

        parsed_url = urlparse(image_url)
        _, ext = os.path.splitext(parsed_url.path)
        if ext == "":
            ext = ".jpg"

        image_name = os.path.basename(output_file_stem) + "_liveimg" + ext
        image_file = os.path.join(COVER_DIR, image_name)
        with open(image_file, "wb") as f:
            f.write(image_data)
        url_map[image_url] = image_file
        hash_map[image_hash] = image_file
        cache_data["url_map"] = url_map
        cache_data["hash_map"] = hash_map
        saveCoverCache(cache_data)
        print("** saved live cover", image_file)
    except Exception as e:
        print("** failed to save live cover", e)


def loadJsonFile(filename, default_value):
    if not os.path.exists(filename):
        return default_value
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value


def saveJsonFile(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("** failed to save json file", filename, e)


def markRecordingStatus(uid, status, nickname="", output_file="", avatar_url="", liveimg_url="", restart_count=0, last_failure_reason=""):
    active_data = loadJsonFile(ACTIVE_RECORDINGS_FILE, {})
    key = str(uid)
    if status == "start":
        active_data[key] = {
            "uid": str(uid),
            "nickname": nickname,
            "output_file": output_file,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "avatar_url": avatar_url,
            "liveimg_url": liveimg_url,
            "restart_count": int(restart_count),
            "last_failure_reason": last_failure_reason or "-"
        }
    elif status == "end":
        if key in active_data:
            del active_data[key]
    saveJsonFile(ACTIVE_RECORDINGS_FILE, active_data)


def appendRecordingHistory(uid, nickname, output_file, elapsed_seconds, success, reason, stream_info, restart_count, failure_category):
    history_data = loadJsonFile(RECORDING_HISTORY_FILE, [])
    history_data.append({
        "uid": str(uid),
        "nickname": nickname,
        "output_file": output_file,
        "elapsed_seconds": int(elapsed_seconds),
        "success": bool(success),
        "reason": reason,
        "failure_category": failure_category,
        "restart_count": int(restart_count),
        "has_video": bool(stream_info.get("has_video", False)),
        "has_audio": bool(stream_info.get("has_audio", False)),
        "stall_seconds": STALL_SECONDS,
        "min_segment_seconds": MIN_SEGMENT_SECONDS,
        "ended_at": datetime.now().isoformat(timespec="seconds")
    })
    history_data = history_data[-200:]
    saveJsonFile(RECORDING_HISTORY_FILE, history_data)

# start recording only when lock file is not exits

ctypes.windll.kernel32.SetConsoleTitleW("TTP %s" % langlive_id)

oRecorder = ttpLangLiveRecorder()

oRecorder.quickedit(0)
applyRecorderConfig()

live_url, session_id, nickname, avatar_url, liveimg_url = oRecorder.getLiveInfo(langlive_id)

if live_url != False and live_url != '':
    output_file = oRecorder.getOutputFile(langlive_id)

    cover_url = liveimg_url
    if cover_url == "":
        cover_url = avatar_url
    saveLiveCoverImage(cover_url, os.path.splitext(output_file)[0])

    # remove queryString to get 720p video
    live_hd_url = getHDLiveUrl(live_url)
    if live_hd_url != live_url:
        live_url = live_hd_url
        print('** upgrade to HD', live_hd_url)

    total_elapsed = 0
    final_success = False
    verify_reason = "錄影未完成"
    stream_info = {"has_video": False, "has_audio": False}
    restart_count = 0
    last_failure_category = "other"
    current_output_file = output_file
    current_nickname = nickname
    current_avatar_url = avatar_url
    current_liveimg_url = liveimg_url

    markRecordingStatus(
        langlive_id,
        "start",
        current_nickname,
        current_output_file,
        current_avatar_url,
        current_liveimg_url,
        restart_count=restart_count,
        last_failure_reason=verify_reason
    )
    try:
        while restart_count <= MAX_STALL_RESTARTS:
            success, elapsed_seconds, stalled = doLiveRecording(live_url, current_output_file)
            total_elapsed += elapsed_seconds

            verify_success, verify_reason, stream_info = validateRecordingFile(current_output_file, elapsed_seconds)
            if success and verify_success:
                final_success = True
                break

            last_failure_category = classify_failure_reason(verify_reason, stalled=stalled)

            # 非卡住類型（如來源結束、輸出嚴重異常）不做循環重啟
            if not stalled:
                break

            restart_count += 1
            if restart_count > MAX_STALL_RESTARTS:
                verify_reason = "卡住重啟次數超過上限"
                last_failure_category = "restart_limit"
                break

            print("** restart attempt #%s" % restart_count)
            retry_delay = get_retry_delay_seconds(
                restart_count,
                FAST_RETRY_LIMIT,
                FAST_RETRY_DELAY_SECONDS,
                BACKOFF_BASE_SECONDS,
                BACKOFF_MAX_SECONDS,
            )
            print("** retry delay: %ss" % retry_delay)
            time.sleep(retry_delay)
            live_url_retry, session_id_retry, nickname_retry, avatar_retry, liveimg_retry = oRecorder.getLiveInfo(langlive_id)
            if live_url_retry == False or live_url_retry == "":
                verify_reason = "重啟時直播已結束"
                last_failure_category = "live_ended"
                break

            live_url = getHDLiveUrl(live_url_retry)
            # 避免過早碎檔：分段太短時沿用同檔名覆蓋重試
            if should_rotate_segment(elapsed_seconds, MIN_SEGMENT_SECONDS):
                current_output_file = oRecorder.getOutputFile(langlive_id)
            current_nickname = nickname_retry or current_nickname
            current_avatar_url = avatar_retry
            current_liveimg_url = liveimg_retry
            markRecordingStatus(
                langlive_id,
                "start",
                current_nickname,
                current_output_file,
                current_avatar_url,
                current_liveimg_url,
                restart_count=restart_count,
                last_failure_reason=verify_reason
            )
    finally:
        markRecordingStatus(langlive_id, "end")

    print("** record validation:", verify_reason)
    if final_success:
        last_failure_category = "none"
    appendRecordingHistory(
        langlive_id,
        current_nickname,
        current_output_file,
        total_elapsed,
        final_success,
        verify_reason,
        stream_info,
        restart_count,
        last_failure_category
    )
	