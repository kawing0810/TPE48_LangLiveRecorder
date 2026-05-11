#!/usr/bin/python
# coding=utf-8

import json
import os
import subprocess
import sys
import threading
import queue
import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from ttp_langLiveRecorder import ttpLangLiveRecorder


CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_PATH, "data")
ACTIVE_RECORDINGS_FILE = os.path.join(DATA_DIR, "active_recordings.json")
RECORDING_HISTORY_FILE = os.path.join(DATA_DIR, "recording_history.json")
MEMBERS_FILE = os.path.join(CURRENT_PATH, "members.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


class RecordMvpLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("TPE48 錄畫模式 MVP")
        self.root.geometry("760x450")
        self.root.minsize(720, 420)
        self.root.resizable(True, True)

        self.uid_var = tk.StringVar(value="")
        self.name_var = tk.StringVar(value="-")
        self.room_var = tk.StringVar(value="-")
        self.live_url_var = tk.StringVar(value="-")
        self.progress_var = tk.StringVar(value="size= -  time= -  bitrate= -  speed= -")
        self.status_var = tk.StringVar(value="待機")
        self.file_var = tk.StringVar(value="-")
        self.file_size_var = tk.StringVar(value="-")
        self.elapsed_var = tk.StringVar(value="-")
        self.started_var = tk.StringVar(value="-")
        self.last_result_var = tk.StringVar(value="-")
        self.last_reason_var = tk.StringVar(value="-")
        self._refresh_job = None
        self.recorder_process = None
        self.log_queue = queue.Queue()
        self.recorder_api = ttpLangLiveRecorder()

        self.uid_to_name = self._load_uid_map()
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_status()
        self._poll_log_queue()

    def _load_uid_map(self):
        data = load_json(MEMBERS_FILE, {})
        mapping = {}
        for value in data.values():
            if isinstance(value, dict):
                for uid, name in value.items():
                    mapping[str(uid)] = str(name)
        return mapping

    def build_ui(self):
        wrap = ttk.Frame(self.root, padding=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        input_row = ttk.Frame(wrap)
        input_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(input_row, text="LiveURL / UID").pack(side=tk.LEFT)
        uid_entry = ttk.Entry(input_row, textvariable=self.uid_var)
        uid_entry.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        uid_entry.bind("<KeyRelease>", lambda _e: self.on_uid_change())
        self.toggle_button = ttk.Button(input_row, text="開始錄影", command=self.toggle_recording)
        self.toggle_button.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(input_row, text="開啟輸出資料夾", command=self.open_output_folder).pack(side=tk.LEFT)

        info = ttk.LabelFrame(wrap, text="房間資訊", padding=8)
        info.pack(fill=tk.X, pady=(0, 8))
        self._row(info, 0, "名稱", self.name_var)
        self._row(info, 1, "房間", self.room_var)
        self._row(info, 2, "LiveURL", self.live_url_var)
        self._row(info, 3, "狀態", self.status_var)
        self._row(info, 4, "輸出檔", self.file_var)
        self._row(info, 5, "檔案大小", self.file_size_var)
        self._row(info, 6, "已錄秒數", self.elapsed_var)

        log_box = ttk.LabelFrame(wrap, text="Recorder Log", padding=8)
        log_box.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.log_text = tk.Text(log_box, height=7, wrap=tk.WORD, bg="#101010", fg="#e8e8e8")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll = ttk.Scrollbar(log_box, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.configure(state=tk.DISABLED)

        footer = ttk.Frame(wrap)
        footer.pack(fill=tk.X)
        ttk.Label(footer, textvariable=self.progress_var).pack(side=tk.LEFT)

    def _set_toggle_text(self, running):
        self.toggle_button.configure(text="停止錄影" if running else "開始錄影")

    def _row(self, parent, row, label, var):
        ttk.Label(parent, text=label, width=10).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Label(parent, textvariable=var).grid(row=row, column=1, sticky="w", pady=2)

    def normalize_uid(self):
        uid = self.uid_var.get().strip()
        self.uid_var.set(uid)
        return uid

    def on_uid_change(self):
        uid = self.normalize_uid()
        self.name_var.set(self.uid_to_name.get(uid, "-"))
        self.room_var.set("-")
        self.live_url_var.set("-")
        self.refresh_status()

    def start_recording(self):
        uid = self.normalize_uid()
        if not uid:
            messagebox.showinfo("提示", "請先輸入 UID")
            return
        if self.recorder_process and self.recorder_process.poll() is None:
            messagebox.showinfo("提示", "Recorder 已在執行中")
            return
        try:
            self._append_log(">>> start recorder uid={0}".format(uid))
            self._load_room_info(uid)
            cmd = [sys.executable, "ttp_recorder.py", uid]
            kwargs = {
                "cwd": CURRENT_PATH,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "bufsize": 1,
            }
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.recorder_process = subprocess.Popen(cmd, **kwargs)
            self.status_var.set("Recorder 啟動中")
            self._set_toggle_text(True)
            threading.Thread(target=self._reader_worker, daemon=True).start()
        except Exception as e:
            messagebox.showerror("錯誤", "啟動失敗: {0}".format(e))
        self.refresh_status()

    def stop_recording(self):
        uid = self.normalize_uid()
        if not uid:
            messagebox.showinfo("提示", "請先輸入 UID")
            return
        try:
            if self.recorder_process and self.recorder_process.poll() is None:
                self._append_log(">>> stop recorder uid={0}".format(uid))
                self.recorder_process.terminate()
                try:
                    self.recorder_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.recorder_process.kill()
                self.status_var.set("已停止內嵌 Recorder")
                self._set_toggle_text(False)
            else:
                cmd = 'taskkill /FI "WINDOWTITLE eq TTP {0}" /T /F'.format(uid)
                subprocess.call(cmd, cwd=CURRENT_PATH, shell=True)
                self.status_var.set("已送出停止指令")
                self._set_toggle_text(False)
        except Exception as e:
            messagebox.showerror("錯誤", "停止失敗: {0}".format(e))
        self.refresh_status()

    def open_output_folder(self):
        os.startfile(CURRENT_PATH)

    def toggle_recording(self):
        if self.recorder_process and self.recorder_process.poll() is None:
            self.stop_recording()
        else:
            self.start_recording()

    def _load_room_info(self, uid):
        try:
            live_url, _session_id, nickname, _avatar_url, _liveimg_url = self.recorder_api.getLiveInfo(uid)
            self.name_var.set(nickname or self.uid_to_name.get(uid, "-"))
            self.room_var.set("{0} ({1})".format(nickname or "-", uid))
            if live_url:
                self.live_url_var.set(live_url)
            else:
                self.live_url_var.set("-")
        except Exception:
            self.room_var.set("-")
            self.live_url_var.set("-")

    def refresh_status(self):
        uid = self.normalize_uid()
        active = load_json(ACTIVE_RECORDINGS_FILE, {})
        item = active.get(uid)
        if item:
            if self.recorder_process and self.recorder_process.poll() is None:
                self.status_var.set("錄影中（內嵌）")
                self._set_toggle_text(True)
            else:
                self.status_var.set("錄影中")
                self._set_toggle_text(False)
            output_file = item.get("output_file", "-")
            self.file_var.set(output_file)
            started_at = item.get("started_at", "-")
            self.started_var.set(started_at)

            file_path = output_file
            if file_path and file_path != "-" and not os.path.isabs(file_path):
                file_path = os.path.join(CURRENT_PATH, file_path)
            if file_path and os.path.exists(file_path):
                self.file_size_var.set(self._format_size(os.path.getsize(file_path)))
            else:
                self.file_size_var.set("-")
            self.elapsed_var.set(self._elapsed_seconds_text(started_at))
        else:
            self._set_toggle_text(False)
            if uid:
                self.status_var.set("待機 / 未錄影")
            else:
                self.status_var.set("待機")
            self.file_var.set("-")
            self.file_size_var.set("-")
            self.elapsed_var.set("-")
            self.started_var.set("-")

        result = "-"
        reason = "-"
        if uid:
            history = load_json(RECORDING_HISTORY_FILE, [])
            for h in reversed(history):
                if str(h.get("uid", "")) == uid:
                    result = "成功" if h.get("success") else "失敗"
                    reason = h.get("reason", "-")
                    break
        self.last_result_var.set(result)
        self.last_reason_var.set(reason)

        self._schedule_refresh()

    def _schedule_refresh(self):
        if self._refresh_job is not None:
            self.root.after_cancel(self._refresh_job)
        self._refresh_job = self.root.after(2000, self.refresh_status)

    def _reader_worker(self):
        if not self.recorder_process or not self.recorder_process.stdout:
            return
        try:
            for line in self.recorder_process.stdout:
                self.log_queue.put(line.rstrip("\r\n"))
        except Exception as e:
            self.log_queue.put("[reader-error] {0}".format(e))
        finally:
            code = None
            try:
                code = self.recorder_process.poll()
            except Exception:
                pass
            self.log_queue.put(">>> recorder exited (code={0})".format(code))

    def _poll_log_queue(self):
        got = False
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            got = True
            self._append_log(msg)
        if got:
            self.refresh_status()
        self.root.after(250, self._poll_log_queue)

    def _append_log(self, text):
        self._update_progress_from_log(text)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _update_progress_from_log(self, text):
        if "size=" not in text or "time=" not in text:
            return
        size_match = re.search(r"size=\s*([^\s]+)", text)
        time_match = re.search(r"time=\s*([^\s]+)", text)
        bitrate_match = re.search(r"bitrate=\s*([^\s]+)", text)
        speed_match = re.search(r"speed=\s*([^\s]+)", text)
        size_text = size_match.group(1) if size_match else "-"
        time_text = time_match.group(1) if time_match else "-"
        bitrate_text = bitrate_match.group(1) if bitrate_match else "-"
        speed_text = speed_match.group(1) if speed_match else "-"
        self.progress_var.set(
            "size= {0}  time= {1}  bitrate= {2}  speed= {3}".format(
                size_text, time_text, bitrate_text, speed_text
            )
        )

    def _elapsed_seconds_text(self, started_at):
        try:
            dt = datetime.fromisoformat(started_at)
            seconds = int((datetime.now() - dt).total_seconds())
            if seconds < 0:
                seconds = 0
            return str(seconds)
        except Exception:
            return "-"

    def _format_size(self, size_bytes):
        size = float(size_bytes)
        units = ["B", "KB", "MB", "GB"]
        idx = 0
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        if idx == 0:
            return "{0} {1}".format(int(size), units[idx])
        return "{0:.1f} {1}".format(size, units[idx])

    def on_close(self):
        if self.recorder_process and self.recorder_process.poll() is None:
            if not messagebox.askyesno("確認", "Recorder 尚在錄影中，確定關閉視窗並停止錄影？"):
                return
            try:
                self.recorder_process.terminate()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    RecordMvpLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
