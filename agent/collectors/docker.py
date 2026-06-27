from __future__ import annotations

import json

from agent.runtime import CommandRunner, command_exists


def collect(runner: CommandRunner, log_lines: int) -> list[dict]:
    if not command_exists("docker"):
        return []
    result = runner.run(["docker", "ps", "-a", "--format", "{{json .}}"])
    if result.returncode != 0:
        return []
    monitors: list[dict] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        monitors.append(collect_container(runner, row, log_lines))
    return monitors


def collect_container(runner: CommandRunner, row: dict, log_lines: int) -> dict:
    cid = row.get("ID") or row.get("ContainerID") or row.get("Names")
    name = row.get("Names") or cid
    state = (row.get("State") or "").lower()
    inspect = runner.run(["docker", "inspect", str(cid)])
    meta = {
        "container_id": cid,
        "image": row.get("Image"),
        "ports": row.get("Ports"),
        "status_text": row.get("Status"),
    }
    started_at = None
    restart_count = 0
    if inspect.returncode == 0:
        try:
            data = json.loads(inspect.stdout)[0]
            state_data = data.get("State", {})
            config = data.get("Config", {})
            started_at = state_data.get("StartedAt")
            restart_count = int(data.get("RestartCount") or 0)
            meta.update({
                "command": row.get("Command"),
                "env": config.get("Env"),
                "working_directory": config.get("WorkingDir"),
                "restarting": state_data.get("Restarting"),
                "exit_code": state_data.get("ExitCode"),
            })
            state = "running" if state_data.get("Running") else state
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
    logs = runner.run(["docker", "logs", "--tail", str(log_lines), str(cid)])
    return {
        "type": "docker",
        "name": name,
        "display_name": name,
        "status": "up" if state == "running" else "down",
        "started_at": started_at,
        "restart_count": restart_count,
        "enabled": False,
        "meta": meta,
        "recent_logs": logs.stdout if logs.returncode == 0 else logs.stderr,
    }

