#!/usr/bin/python
# coding=utf-8

import argparse
import json
import os
from datetime import datetime, timedelta


CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_PATH, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "recording_history.json")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
CONFIG_FILE = os.path.join(CURRENT_PATH, "config.json")


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def load_monthly_quality_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("monthly_quality", {})
    except Exception:
        return {}


def month_window(year, month):
    begin = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return begin, end


def parse_iso(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def filter_by_window(records, begin, end):
    result = []
    for item in records:
        dt = parse_iso(item.get("ended_at", ""))
        if not dt:
            continue
        if begin <= dt < end:
            result.append(item)
    return result


def save_markdown_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def evaluate_records(records, min_records, min_success_rate, max_avg_restarts, max_short_ratio):
    total = len(records)
    success_count = len([r for r in records if r.get("success") is True])
    success_rate = (success_count / total) if total > 0 else 0.0
    avg_restarts = (sum(int(r.get("restart_count", 0)) for r in records) / total) if total > 0 else 0.0
    short_segments = len([r for r in records if int(r.get("elapsed_seconds", 0)) < 120])
    short_ratio = (short_segments / total) if total > 0 else 0.0
    pass_total = total >= min_records
    pass_success = success_rate >= min_success_rate
    pass_restart = avg_restarts <= max_avg_restarts
    pass_short = short_ratio <= max_short_ratio
    return {
        "total": total,
        "success_rate": success_rate,
        "avg_restarts": avg_restarts,
        "short_ratio": short_ratio,
        "pass_total": pass_total,
        "pass_success": pass_success,
        "pass_restart": pass_restart,
        "pass_short": pass_short,
        "is_pass": pass_total and pass_success and pass_restart and pass_short,
    }


def main():
    monthly_cfg = load_monthly_quality_config()
    parser = argparse.ArgumentParser(description="Generate monthly recording quality report")
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--month", type=int, default=datetime.now().month)
    parser.add_argument("--min-records", type=int, default=int(monthly_cfg.get("min_records", 30)))
    parser.add_argument("--min-success-rate", type=float, default=float(monthly_cfg.get("min_success_rate", 0.90)))
    parser.add_argument("--max-avg-restarts", type=float, default=float(monthly_cfg.get("max_avg_restarts", 1.20)))
    parser.add_argument("--max-short-ratio", type=float, default=float(monthly_cfg.get("max_short_ratio", 0.35)))
    args = parser.parse_args()

    begin, end = month_window(args.year, args.month)
    records = load_history()
    scoped = filter_by_window(records, begin, end)

    result = evaluate_records(
        records=scoped,
        min_records=args.min_records,
        min_success_rate=args.min_success_rate,
        max_avg_restarts=args.max_avg_restarts,
        max_short_ratio=args.max_short_ratio,
    )

    month_label = "{0:04d}-{1:02d}".format(args.year, args.month)
    lines = [
        "# Monthly Quality Report",
        "",
        "Month: `{0}`".format(month_label),
        "Window: `{0}` to `{1}`".format(begin.date().isoformat(), (end - timedelta(days=1)).date().isoformat()),
        "",
        "## Metrics",
        "- Records: {0}".format(result["total"]),
        "- Success rate: {0:.2%}".format(result["success_rate"]),
        "- Avg restarts: {0:.2f}".format(result["avg_restarts"]),
        "- Short segment ratio: {0:.2%}".format(result["short_ratio"]),
        "",
        "## Gate Check",
        "- min_records: {0} => {1}".format(args.min_records, "PASS" if result["pass_total"] else "FAIL"),
        "- min_success_rate: {0:.0%} => {1}".format(args.min_success_rate, "PASS" if result["pass_success"] else "FAIL"),
        "- max_avg_restarts: {0:.2f} => {1}".format(args.max_avg_restarts, "PASS" if result["pass_restart"] else "FAIL"),
        "- max_short_ratio: {0:.0%} => {1}".format(args.max_short_ratio, "PASS" if result["pass_short"] else "FAIL"),
        "",
        "## Result",
        "- Overall: **{0}**".format("PASS" if result["is_pass"] else "FAIL"),
        "",
        "## Suggested Actions",
    ]
    if result["is_pass"]:
        lines.append("- Keep current thresholds; continue monthly monitoring.")
    else:
        lines.extend([
            "- Review failed records in `data/recording_history.json` by `failure_category`.",
            "- If `network_stall` dominates, tune `recorder.stall_seconds` and retry backoff.",
            "- If short ratio is high, increase `recorder.min_segment_seconds` or adjust restart threshold.",
        ])

    output_path = os.path.join(REPORTS_DIR, "quality-{0}.md".format(month_label))
    save_markdown_report(output_path, lines)
    print("Report generated:", output_path)


if __name__ == "__main__":
    main()
