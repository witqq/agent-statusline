"""Read a Claude Code statusLine payload from stdin and print dim terminal rows."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

from core import Limit, Snapshot
from layout import render


MODEL_FAMILIES = {"opus": "OPS", "sonnet": "SNT", "haiku": "HKU", "fable": "FBL"}


def model_name(model):
    name = model.get("display_name") or model.get("id") or "Claude"
    for family, abbreviation in MODEL_FAMILIES.items():
        if family in name.lower():
            suffix = "(1M)" if "1m" in name.lower() else ""
            version = re.search(r"\d+(?:\.\d+)?", re.sub(r"1m", "", name, flags=re.I))
            return abbreviation + (version[0] if version else "") + suffix
    return name


def reset_time(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            return None
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.timestamp()


def snapshot(data, instance="main"):
    workspace = data.get("workspace") or {}
    cwd = Path(workspace.get("current_dir") or data.get("cwd") or Path.cwd())
    limits = []
    rates = data.get("rate_limits") or {}
    for key, label in (("five_hour", "5h"), ("seven_day", "7d"), ("seven_day_opus", "opus")):
        window = rates.get(key) or {}
        if window.get("used_percentage") is not None:
            limits.append(Limit(label, window["used_percentage"], reset_time(window.get("resets_at"))))
    return Snapshot(
        client="claude", cwd=cwd, project_dir=Path(workspace.get("project_dir") or cwd),
        model=model_name(data.get("model") or {}),
        effort=(data.get("effort") or {}).get("level"),
        context_used=(data.get("context_window") or {}).get("used_percentage"),
        limits=tuple(limits), instance=instance,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", default="main", help="Prefix for this Claude instance")
    args = parser.parse_args()
    state = snapshot(json.load(sys.stdin), args.instance)
    columns = os.environ.get("COLUMNS", "80")
    width = max(20, int(columns)) if columns.isascii() and columns.isdigit() else 80
    lines = render(state).splitlines()
    clipped = [line[:width - 1] + "…" if len(line) > width else line for line in lines]
    sys.stdout.write("\n".join(f"\033[2m{line}\033[0m" for line in clipped))


if __name__ == "__main__":
    main()
