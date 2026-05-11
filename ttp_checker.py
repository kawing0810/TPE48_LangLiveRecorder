#!/usr/bin/pyhton
#coding=utf-8

import urllib.request
import json
import ssl
from datetime import datetime
import os
import sys
import time
import random
import subprocess
import argparse
import ctypes

from ttp_langLiveRecorder import ttpLangLiveRecorder

sys.stdout.reconfigure(encoding='utf-8')

PYTHONHTTPSVERIFY=0

sys.tracebacklimit = 0
_my_debug_flag_here = 1

def exception_handler(exception_type, exception, traceback, debug_hook=sys.excepthook):
    if _my_debug_flag_here:
        debug_hook(exception_type, exception, traceback)
    else:
        print("%s: %s" % (exception_type.__name__, exception))

# sys.excepthook = exception_handler

current_path = os.path.dirname(os.path.abspath(__file__))
videos_path = current_path
DATA_DIR = os.path.join(current_path, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CHECKER_STATE_FILE = os.path.join(DATA_DIR, "dashboard_state.json")
ACTIVE_RECORDINGS_FILE = os.path.join(DATA_DIR, "active_recordings.json")

os.chdir(current_path)

member_key = 'akb48ttp' # group_members
interval = 60
check_live_only = 0

parser = argparse.ArgumentParser()
parser.add_argument('--interval', type=int, help="check interval in second(s)", default=60)
parser.add_argument('--group', type=str, help="choice which group of members (akb48ttp, or test)", default="akb48ttp")
parser.add_argument('--check', type=int, help="do checking only", default=0)
args = parser.parse_args()

print(parser.format_help())

print(args)

if args.interval: 
    interval = args.interval
if args.group:
    member_key = args.group
if args.check:
    check_live_only = args.check

member_key = member_key +'_members'

def do_scheduler():
    tstart = time.time()

    check_onlive()

    tend = time.time()

    elapsed = tend - tstart
    remain = interval - elapsed

    print(">>> elapsed %ds, wait %ds ... <<<" % (elapsed, remain))
    if remain < 0:
        remain = 5
    
    return remain

def open_recording_window(langlive_id, label="TTP"):
    cmd = [" "]
    cmd.append(os.path.join(".", current_path,sys.executable))
    cmd.append(os.path.join(current_path, "ttp_recorder.py"))
    cmd.append(langlive_id)
    cmd.append("--label %s" % label)
    # print(cmd)
    # open new prompt to recording
    if os.name == "nt":
        # subprocess.call(['runscript.bat', os.path.join(current_path, "recorder.py"), langlive_id])
        subprocess.call(['record.bat', langlive_id])
        # subprocess.call(["cmd.exe", "/c", "start", cmd])

    if os.name == "posix":
        param = " ".join(cmd)
        subprocess.call(["osascript", "-e", "tell application \"Terminal\" to do script \"%s\"" % param])


def is_recording_active(langlive_id):
    if not os.path.exists(ACTIVE_RECORDINGS_FILE):
        return False
    try:
        with open(ACTIVE_RECORDINGS_FILE, "r", encoding="utf-8") as f:
            active_data = json.load(f)
        return str(langlive_id) in active_data
    except Exception:
        return False


def ensure_recording_started(langlive_id, nickname):
    # recorder 啟動後給幾秒進入 active_recordings
    wait_seconds = 3
    retries = 1
    for attempt in range(retries + 1):
        time.sleep(wait_seconds)
        if is_recording_active(langlive_id):
            return True
        if attempt < retries:
            print("** recorder opened but not active, retry launch", langlive_id)
            open_recording_window(langlive_id, nickname)
    return False


def check_onlive():
    # open TTP members definition file
    filename = os.path.join(current_path, 'members.json')
    f = open(filename, encoding="utf8")
    data = json.load(f)
    f.close()

    prev_last_live = {}
    if os.path.exists(CHECKER_STATE_FILE):
        try:
            with open(CHECKER_STATE_FILE, "r", encoding="utf-8") as sf:
                prev_snap = json.load(sf)
            for pm in prev_snap.get("members", []):
                uid_key = str(pm.get("uid", ""))
                if uid_key:
                    prev_last_live[uid_key] = pm.get("last_live_at") or ""
        except Exception:
            pass

    snapshot = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "group": member_key,
        "interval": interval,
        "check_live_only": check_live_only,
        "members": []
    }

    if member_key in data:
        for langlive_id in data[member_key]:
            live_url, session_id, nickname, avatar_url, liveimg_url = oRecorder.getLiveInfo(langlive_id)

            print('** %s (%s) %s' % (langlive_id, nickname, live_url))

            is_live = (live_url != False and live_url != '')
            uid_str = str(langlive_id)
            if is_live:
                last_live_at = datetime.now().isoformat(timespec="seconds")
            else:
                last_live_at = prev_last_live.get(uid_str, "")
            launched = False
            if live_url != False and live_url != '':
                # live_url not empty, test any lock file
                lock_file = oRecorder.getLockFile(langlive_id, session_id)
                if check_live_only==0 and not os.path.exists(lock_file):
                    open_recording_window(langlive_id, nickname)
                    launched = True
                    if not ensure_recording_started(langlive_id, nickname):
                        print("** recorder launch failed to start recording", langlive_id)

            snapshot["members"].append({
                "uid": uid_str,
                "nickname": nickname,
                "avatar_url": avatar_url,
                "liveimg_url": liveimg_url,
                "is_live": is_live,
                "session_id": session_id,
                "launched_recorder": launched,
                "last_live_at": last_live_at
            })

    try:
        with open(CHECKER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("failed to write dashboard state", e)

# main

ctypes.windll.kernel32.SetConsoleTitleW("TTP Lang Live Checker")

oRecorder = ttpLangLiveRecorder()
oRecorder.quickedit(0) # Disable quick edit in terminal
try:
    while (1):
        remain = do_scheduler()
        time.sleep(remain)

except KeyboardInterrupt:
    pass
