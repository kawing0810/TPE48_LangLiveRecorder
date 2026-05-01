#!/usr/bin/python
# coding=utf-8

import argparse
import json
import os
import subprocess
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote_plus, urlparse


CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_PATH, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CHECKER_STATE_FILE = os.path.join(DATA_DIR, "dashboard_state.json")
ACTIVE_RECORDINGS_FILE = os.path.join(DATA_DIR, "active_recordings.json")
RECORDING_HISTORY_FILE = os.path.join(DATA_DIR, "recording_history.json")


def load_json(filename, default_value):
    if not os.path.exists(filename):
        return default_value
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value


def render_html(message=""):
    checker = load_json(CHECKER_STATE_FILE, {})
    active = load_json(ACTIVE_RECORDINGS_FILE, {})

    updated_at = checker.get("updated_at", "-")
    group = checker.get("group", "-")
    interval = checker.get("interval", "-")
    members = checker.get("members", [])
    live_count = len([m for m in members if m.get("is_live")])
    active_list = list(active.values())
    history_list = load_json(RECORDING_HISTORY_FILE, [])
    history_list = list(reversed(history_list[-20:]))

    rows = []
    for m in members:
        is_live = m.get("is_live")
        status = "<span class='badge badge-live'>開播中</span>" if is_live else "<span class='badge badge-offline'>離線</span>"
        launched = "是" if m.get("launched_recorder") else "-"
        avatar_url = m.get("liveimg_url") or m.get("avatar_url") or ""
        avatar_html = "<span class='avatar-fallback'>--</span>"
        if avatar_url:
            avatar_html = "<img class='avatar' src='{0}' alt='avatar'>".format(avatar_url)
        start_action = (
            "<form class='action-form' method='post' action='/action'>"
            "<input type='hidden' name='action' value='start'>"
            "<input type='hidden' name='uid' value='{uid}'>"
            "<button class='btn' type='submit'>立即錄影</button>"
            "</form>"
        ).format(uid=m.get("uid", ""))
        rows.append(
            "<tr>"
            "<td>{avatar}</td>"
            "<td>{uid}</td>"
            "<td>{nickname}</td>"
            "<td>{status}</td>"
            "<td>{launched}</td>"
            "<td>{action}</td>"
            "</tr>".format(
                avatar=avatar_html,
                uid=m.get("uid", ""),
                nickname=m.get("nickname", "") or "-",
                status=status,
                launched=launched,
                action=start_action
            )
        )

    active_rows = []
    for a in active_list:
        active_avatar_url = a.get("liveimg_url") or a.get("avatar_url") or ""
        active_avatar_html = "<span class='avatar-fallback'>--</span>"
        if active_avatar_url:
            active_avatar_html = "<img class='avatar' src='{0}' alt='avatar'>".format(active_avatar_url)
        stop_action = (
            "<form class='action-form' method='post' action='/action'>"
            "<input type='hidden' name='action' value='stop'>"
            "<input type='hidden' name='uid' value='{uid}'>"
            "<button class='btn btn-danger' type='submit'>停止錄影</button>"
            "</form>"
        ).format(uid=a.get("uid", ""))
        active_rows.append(
            "<tr>"
            "<td>{avatar}</td>"
            "<td>{uid}</td>"
            "<td>{nickname}</td>"
            "<td>{started_at}</td>"
            "<td>{restart_count}</td>"
            "<td>{last_failure_reason}</td>"
            "<td>{output_file}</td>"
            "<td>{action}</td>"
            "</tr>".format(
                avatar=active_avatar_html,
                uid=a.get("uid", ""),
                nickname=a.get("nickname", "") or "-",
                started_at=a.get("started_at", "") or "-",
                restart_count=a.get("restart_count", 0),
                last_failure_reason=a.get("last_failure_reason", "-"),
                output_file=a.get("output_file", "") or "-",
                action=stop_action
            )
        )

    history_rows = []
    for h in history_list:
        state_badge = "<span class='badge badge-live'>成功</span>" if h.get("success") else "<span class='badge badge-offline'>失敗</span>"
        reason = h.get("reason", "") or "-"
        restart_count = h.get("restart_count", 0)
        failure_category = h.get("failure_category", "") or "-"
        history_rows.append(
            "<tr>"
            "<td>{uid}</td>"
            "<td>{nickname}</td>"
            "<td>{state}</td>"
            "<td>{restarts}</td>"
            "<td>{category}</td>"
            "<td>{reason}</td>"
            "<td>{elapsed}</td>"
            "<td>{ended_at}</td>"
            "<td>{output_file}</td>"
            "</tr>".format(
                uid=h.get("uid", ""),
                nickname=h.get("nickname", "") or "-",
                state=state_badge,
                restarts=restart_count,
                category=failure_category,
                reason=reason,
                elapsed=str(h.get("elapsed_seconds", 0)) + "s",
                ended_at=h.get("ended_at", "") or "-",
                output_file=h.get("output_file", "") or "-"
            )
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="10">
  <title>TTP 監控儀表板</title>
  <style>
    :root {{
      --bg: #050805;
      --panel: #081108;
      --panel2: #0c160c;
      --line: #1d4d1d;
      --text: #92ff92;
      --muted: #4bbf4b;
      --green: #7dff7d;
      --red: #ff6b6b;
      --blue: #58ffcf;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top right, #0b1a0b 0%, var(--bg) 60%);
      color: var(--text);
      font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
      padding: 20px;
      text-shadow: 0 0 6px rgba(80, 255, 80, 0.18);
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    .header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      gap: 12px;
      flex-wrap: wrap;
    }}
    h2 {{ margin: 0; font-size: 24px; letter-spacing: 0.4px; }}
    h3 {{ margin: 0 0 10px 0; font-size: 16px; }}
    .muted {{ color: var(--muted); font-size: 12px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }}
    .metric {{
      background: rgba(8, 17, 8, 0.88);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
    }}
    .metric .title {{ color: var(--muted); font-size: 12px; }}
    .metric .value {{ font-size: 22px; font-weight: 700; margin-top: 4px; }}
    .card {{
      background: rgba(8, 17, 8, 0.9);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 14px;
      margin-bottom: 14px;
      box-shadow: 0 0 0 1px rgba(84, 255, 84, 0.12), inset 0 0 14px rgba(84, 255, 84, 0.04);
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-top: 8px;
      overflow: hidden;
      border-radius: 10px;
    }}
    th, td {{
      border-bottom: 1px solid #173517;
      padding: 8px 10px;
      text-align: left;
      font-size: 13px;
    }}
    th {{
      background: var(--panel2);
      color: #b7ffb7;
      position: sticky;
      top: 0;
    }}
    tr:nth-child(even) td {{ background: rgba(10, 26, 10, 0.42); }}
    tr:hover td {{ background: rgba(80, 255, 120, 0.08); }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.4px;
    }}
    .badge-live {{ background: rgba(80, 255, 120, 0.1); color: #89ff89; border: 1px solid rgba(80, 255, 120, 0.45); }}
    .badge-offline {{ background: rgba(255, 107, 107, 0.12); color: #ff9c9c; border: 1px solid rgba(255, 107, 107, 0.36); }}
    .pill {{
      display: inline-block;
      border: 1px solid rgba(88, 255, 207, 0.45);
      color: #8fffe0;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      margin-left: 6px;
    }}
    .avatar {{
      width: 28px;
      height: 28px;
      border-radius: 50%;
      object-fit: cover;
      border: 1px solid #2d7d2d;
      display: inline-block;
      vertical-align: middle;
    }}
    .avatar-fallback {{
      color: var(--muted);
      font-size: 12px;
    }}
    .action-form {{
      display: inline;
      margin-right: 6px;
    }}
    .btn {{
      background: #0f2a0f;
      color: #9dff9d;
      border: 1px solid #2d7d2d;
      border-radius: 4px;
      padding: 4px 8px;
      cursor: pointer;
      font-family: inherit;
      font-size: 12px;
    }}
    .btn:hover {{ background: #143814; }}
    .btn-danger {{
      color: #ffb2b2;
      border-color: #9f3b3b;
      background: #2c1111;
    }}
    .btn-danger:hover {{ background: #3a1616; }}
    .msg {{
      margin: 8px 0 12px 0;
      border: 1px solid #2d7d2d;
      background: rgba(20, 55, 20, 0.35);
      padding: 8px 10px;
      border-radius: 6px;
      color: #aaffaa;
    }}
  </style>
</head>
<body>
  <div class="container">
  <div class="header">
    <h2>TPE48 LangLiveRecorder 監控儀表板 <span class="pill">每 10 秒自動更新</span></h2>
    <div class="muted">頁面更新時間：{now}</div>
  </div>
  {message_html}

  <div class="grid">
    <div class="metric">
      <div class="title">最近檢查時間</div>
      <div class="value">{updated_at}</div>
    </div>
    <div class="metric">
      <div class="title">監控群組</div>
      <div class="value">{group}</div>
    </div>
    <div class="metric">
      <div class="title">檢查間隔</div>
      <div class="value">{interval}s</div>
    </div>
    <div class="metric">
      <div class="title">目前開播數</div>
      <div class="value">{live_count}</div>
    </div>
  </div>

  <div class="card">
    <h3>錄影中清單（{active_count}）</h3>
    <table>
      <tr><th>頭像</th><th>UID</th><th>暱稱</th><th>開始時間</th><th>重啟次數</th><th>最後失敗原因</th><th>輸出檔案</th><th>操作</th></tr>
      {active_rows}
    </table>
  </div>

  <div class="card">
    <h3>最新掃描快照（{member_count} 人）</h3>
    <table>
      <tr><th>頭像</th><th>UID</th><th>暱稱</th><th>狀態</th><th>已啟動錄影</th><th>操作</th></tr>
      {rows}
    </table>
  </div>

  <div class="card">
    <h3>最近錄影歷史（最多 20 筆）</h3>
    <table>
      <tr><th>UID</th><th>暱稱</th><th>結果</th><th>重啟次數</th><th>失敗分類</th><th>檢查結果</th><th>時長</th><th>結束時間</th><th>輸出檔案</th></tr>
      {history_rows}
    </table>
  </div>
  </div>
</body>
</html>
""".format(
        now=now,
        updated_at=updated_at,
        group=group,
        interval=interval,
        live_count=live_count,
        active_count=len(active_list),
        message_html=("<div class='msg'>{0}</div>".format(message)) if message else "",
        active_rows="\n".join(active_rows) if active_rows else "<tr><td colspan='8'>目前沒有錄影中項目</td></tr>",
        member_count=len(members),
        rows="\n".join(rows) if rows else "<tr><td colspan='6'>目前尚無掃描資料</td></tr>",
        history_rows="\n".join(history_rows) if history_rows else "<tr><td colspan='9'>目前尚無錄影歷史</td></tr>"
    )
    return html.encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/" and parsed.path != "/index.html":
            self.send_error(404)
            return
        qs = parse_qs(parsed.query)
        message = qs.get("msg", [""])[0]
        content = render_html(message=message)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/action":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        params = parse_qs(body)
        action = params.get("action", [""])[0]
        uid = params.get("uid", [""])[0].strip()

        if not uid:
            self.redirect_with_message("缺少 UID")
            return

        if action == "start":
            try:
                subprocess.call(["record.bat", uid], cwd=CURRENT_PATH)
                self.redirect_with_message("已送出錄影啟動：" + uid)
            except Exception as e:
                self.redirect_with_message("啟動失敗：{0}".format(e))
            return

        if action == "stop":
            try:
                cmd = 'taskkill /FI "WINDOWTITLE eq TTP {0}" /T /F'.format(uid)
                subprocess.call(cmd, cwd=CURRENT_PATH, shell=True)
                self.redirect_with_message("已送出停止錄影：" + uid)
            except Exception as e:
                self.redirect_with_message("停止失敗：{0}".format(e))
            return

        self.redirect_with_message("未知操作")

    def redirect_with_message(self, message):
        location = "/?msg={0}".format(quote_plus(message))
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, format_text, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787, help="dashboard port")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print("Dashboard running at http://127.0.0.1:{0}".format(args.port))
    server.serve_forever()


if __name__ == "__main__":
    main()
