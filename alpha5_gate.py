#!/usr/bin/python
# coding=utf-8

import argparse
import json
import os
from datetime import datetime, timedelta


CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_PATH, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "recording_history.json")


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def parse_iso(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def evaluate(records, days, min_records, min_success_rate, max_avg_restarts):
    now = datetime.now()
    begin = now - timedelta(days=days)

    scoped = []
    for r in records:
        dt = parse_iso(r.get("ended_at", ""))
        if not dt:
            continue
        if dt >= begin:
            scoped.append(r)

    total = len(scoped)
    success_count = len([r for r in scoped if r.get("success") is True])
    success_rate = (success_count / total) if total > 0 else 0.0
    avg_restarts = (sum(int(r.get("restart_count", 0)) for r in scoped) / total) if total > 0 else 0.0
    short_segments = len([r for r in scoped if int(r.get("elapsed_seconds", 0)) < 120])
    short_ratio = (short_segments / total) if total > 0 else 0.0

    pass_total = total >= min_records
    pass_success = success_rate >= min_success_rate
    pass_restart = avg_restarts <= max_avg_restarts
    pass_short = short_ratio <= 0.35

    is_pass = pass_total and pass_success and pass_restart and pass_short
    return {
        "days": days,
        "total": total,
        "success_count": success_count,
        "success_rate": success_rate,
        "avg_restarts": avg_restarts,
        "short_segments": short_segments,
        "short_ratio": short_ratio,
        "pass_total": pass_total,
        "pass_success": pass_success,
        "pass_restart": pass_restart,
        "pass_short": pass_short,
        "is_pass": is_pass,
    }


def main():
    parser = argparse.ArgumentParser(description="Alpha 5 gate validator")
    parser.add_argument("--days", type=int, default=3, help="lookback days")
    parser.add_argument("--min-records", type=int, default=30, help="minimum records in window")
    parser.add_argument("--min-success-rate", type=float, default=0.90, help="minimum success rate")
    parser.add_argument("--max-avg-restarts", type=float, default=1.20, help="maximum average restart count")
    args = parser.parse_args()

    records = load_history()
    result = evaluate(
        records=records,
        days=args.days,
        min_records=args.min_records,
        min_success_rate=args.min_success_rate,
        max_avg_restarts=args.max_avg_restarts,
    )

    print("=== Alpha 5 Gate Report ===")
    print("Window: last {0} day(s)".format(result["days"]))
    print("Records: {0}".format(result["total"]))
    print("Success rate: {0:.2%}".format(result["success_rate"]))
    print("Avg restarts: {0:.2f}".format(result["avg_restarts"]))
    print("Short segment ratio(<120s): {0:.2%}".format(result["short_ratio"]))
    print("--- Criteria ---")
    print("Records >= threshold: {0}".format("PASS" if result["pass_total"] else "FAIL"))
    print("Success rate >= threshold: {0}".format("PASS" if result["pass_success"] else "FAIL"))
    print("Avg restarts <= threshold: {0}".format("PASS" if result["pass_restart"] else "FAIL"))
    print("Short segment ratio <= 35%: {0}".format("PASS" if result["pass_short"] else "FAIL"))
    print("=== Gate Result: {0} ===".format("PASS" if result["is_pass"] else "FAIL"))

    # Exit code for CI usage
    raise SystemExit(0 if result["is_pass"] else 1)


if __name__ == "__main__":
    main()
