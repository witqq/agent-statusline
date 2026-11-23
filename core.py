"""Client-independent input, segments, and layout for terminal status lines."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import stat
import subprocess
import time


@dataclass(frozen=True)
class Limit:
    label: str
    used: float
    resets_at: float | None = None


@dataclass(frozen=True)
class Snapshot:
    client: str
    cwd: Path
    project_dir: Path
    model: str
    effort: str | None = None
    context_used: float | None = None
    limits: tuple[Limit, ...] = ()
    instance: str = "main"


Segment = Callable[[Snapshot], str]
_CONTROLS = dict.fromkeys((*range(32), *range(127, 160)))


def row(*segments: Segment, separator: str = "  ") -> Segment:
    """Join nonempty segments on the same line."""
    def render(state: Snapshot) -> str:
        return separator.join(filter(None, (segment(state) for segment in segments)))
    return render


def lines(*segments: Segment) -> Segment:
    """Stack segments vertically, including multiline text, skipping empty results."""
    return row(*segments, separator="\n")


@lru_cache(maxsize=64)
def _branch(cwd: Path, interval: int) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "branch", "--show-current"],
            capture_output=True, text=True, errors="replace", timeout=0.3,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def identity(state: Snapshot) -> str:
    name = state.cwd.name or str(state.cwd)
    if state.instance:
        name = f"[{state.instance}] {name}"
    model = state.model if not state.effort else f"{state.model}:{state.effort}"
    branch = _branch(state.cwd, int(time.monotonic() // 5))
    return "|".join(filter(None, (name, branch, model))).translate(_CONTROLS)


def context(state: Snapshot) -> str:
    return "" if state.context_used is None else f"ctx:{int(state.context_used)}%"


def until_reset(epoch: float) -> str:
    seconds = epoch - time.time()
    if seconds <= 0:
        return "0h"
    hours, minutes = divmod(int(seconds // 60), 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d" + (f"{hours}h" if hours else "")
    return f"{hours}h{minutes}m" if hours else f"{minutes}m"


def limits(state: Snapshot) -> str:
    parts = []
    for window in state.limits:
        remaining = max(0, min(100, 100 - window.used))
        part = f"{window.label}:{remaining:g}%"
        if window.resets_at is not None:
            part += f"({until_reset(window.resets_at)})"
        parts.append(part)
    return " ".join(parts)


def agent_status(state: Snapshot) -> str:
    """Show up to four nonblank project messages and mark stale entries."""
    path = state.project_dir / ".agent-status"
    try:
        with open(path, encoding="utf-8", errors="replace",
                  opener=lambda p, flags: os.open(p, flags | os.O_NONBLOCK)) as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                return ""
            # Bound the amount of work and text a terminal update can consume.
            content = stream.read(65537)
    except OSError:
        return ""
    prefix = "⏸ " if time.time() - info.st_mtime > 900 else ""
    cleaned = (line.expandtabs(4).translate(_CONTROLS) for line in content.splitlines())
    entries = [line for line in cleaned if line.strip()]
    visible = [prefix + line[:512] for line in entries[:4]]
    if len(content) > 65536:
        visible.append("…")
    elif len(entries) > 4:
        visible.append(f"… ещё {len(entries) - 4}")
    return "\n".join(visible)
