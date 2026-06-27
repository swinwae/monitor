from __future__ import annotations

import json
import os
import re
from pathlib import Path

from agent.runtime import CommandRunner, tail_file


PLIST_DIRS = [
    "~/Library/LaunchAgents",
    "/Library/LaunchAgents",
    "/Library/LaunchDaemons",
]


def collect(runner: CommandRunner, log_lines: int) -> list[dict]:
    labels = launchctl_list(runner)
    monitors: list[dict] = []
    for plist in iter_plists():
        item = collect_plist(runner, plist, labels, log_lines)
        if item is not None:
            monitors.append(item)
    return monitors


def iter_plists() -> list[Path]:
    paths: list[Path] = []
    for raw in PLIST_DIRS:
        base = Path(raw).expanduser()
        if base.exists():
            paths.extend(sorted(base.glob("*.plist")))
    return paths


def collect_plist(
    runner: CommandRunner,
    plist: Path,
    labels: dict[str, dict],
    log_lines: int,
) -> dict | None:
    parsed = runner.run(["plutil", "-convert", "json", "-o", "-", str(plist)])
    if parsed.returncode != 0:
        return None
    try:
        data = json.loads(parsed.stdout)
    except json.JSONDecodeError:
        return None
    label = data.get("Label") or plist.stem
    state = labels.get(label, {})
    details = launchctl_print(runner, label)
    stdout_log = tail_file(data.get("StandardOutPath"), log_lines)
    stderr_log = tail_file(data.get("StandardErrorPath"), log_lines)
    return {
        "type": "launchd",
        "name": label,
        "display_name": label,
        "status": "up" if state.get("pid") else "down",
        "restart_count": details.get("runs") or 0,
        "last_exit_code": details.get("last_exit_code"),
        "enabled": bool(data.get("RunAtLoad") or data.get("KeepAlive")),
        "meta": {
            "plist": str(plist),
            "program_arguments": data.get("ProgramArguments"),
            "working_directory": data.get("WorkingDirectory"),
            "stdout_path": data.get("StandardOutPath"),
            "stderr_path": data.get("StandardErrorPath"),
            "run_at_load": data.get("RunAtLoad"),
            "keep_alive": data.get("KeepAlive"),
            "environment": data.get("EnvironmentVariables"),
            "launchctl_status": state.get("status"),
        },
        "recent_logs": "\n".join(x for x in [stdout_log, stderr_log] if x),
    }


def launchctl_list(runner: CommandRunner) -> dict[str, dict]:
    result = runner.run(["launchctl", "list"])
    if result.returncode != 0:
        return {}
    labels: dict[str, dict] = {}
    for line in result.stdout.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid, status, label = parts
        labels[label] = {
            "pid": int(pid) if pid.isdigit() else None,
            "status": int(status) if status.lstrip("-").isdigit() else None,
        }
    return labels


def launchctl_print(runner: CommandRunner, label: str) -> dict:
    domains = [f"gui/{os.getuid()}/{label}", f"system/{label}"]
    text = ""
    for domain in domains:
        result = runner.run(["launchctl", "print", domain])
        if result.returncode == 0:
            text = result.stdout
            break
    return {
        "runs": _match_int(text, r"\bruns\s*=\s*(\d+)"),
        "last_exit_code": _match_int(text, r"\blast exit code\s*=\s*(-?\d+)"),
    }


def _match_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return int(match.group(1))
