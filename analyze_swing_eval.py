#!/usr/bin/env python3
"""
Score a swing eval log from collect_swing_eval.py.

  python analyze_swing_eval.py swing_eval_logs/session_20260523_120000.json
  python analyze_swing_eval.py swing_eval_logs/   # all sessions
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from swing_eval_scoring import format_report, score_session


def analyze_log_file(path: Path) -> str:
    log = json.loads(path.read_text())
    score = score_session(log, log_path=str(path))
    summary_path = path.with_name(path.stem + "_summary.json")
    summary = {
        "log": str(path),
        "overall_peak_velocity_match": score.overall_peak_velocity_match,
        "overall_trial_pass_rate": score.overall_trial_pass_rate,
        "overall_strong_frame_accuracy": score.overall_strong_frame_accuracy,
        "overall_swing_direction_accuracy": score.overall_swing_direction_accuracy,
        "overall_attack_direction_accuracy": score.overall_attack_direction_accuracy,
        "overall_idle_fraction": score.overall_idle_fraction,
        "overall_false_direction_fraction": score.overall_false_direction_fraction,
        "trials": [
            {
                "exercise_id": ts.exercise_id,
                "peak_velocity_direction": ts.peak_velocity_direction,
                "peak_velocity_match": ts.peak_velocity_match,
                "strong_frame_accuracy": ts.strong_frame_accuracy,
                "trial_pass": ts.trial_pass,
                "swing_direction_accuracy": ts.swing_direction_accuracy,
                "attack_direction_accuracy": ts.attack_direction_accuracy,
                "idle_fraction": ts.idle_fraction,
                "false_direction_fraction": ts.false_direction_fraction,
                "saw_begin": ts.saw_begin,
                "saw_mid": ts.saw_mid,
                "saw_end": ts.saw_end,
            }
            for ts in score.trial_scores
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    report = format_report(score)
    report += f"\nSummary JSON: {summary_path}\n"
    return report


def parse_args():
    p = argparse.ArgumentParser(description="Analyze swing eval logs")
    p.add_argument(
        "path",
        type=Path,
        help="Session .json file or directory of logs",
    )
    return p.parse_args()


def main():
    args = parse_args()
    path = args.path
    if path.is_dir():
        logs = sorted(path.glob("session_*.json"))
        logs = [p for p in logs if not p.name.endswith("_summary.json")]
        if not logs:
            print(f"No session_*.json in {path}")
            return
        for log_path in logs:
            print(analyze_log_file(log_path))
            print()
    else:
        print(analyze_log_file(path))


if __name__ == "__main__":
    main()
