from __future__ import annotations

from agent.config import ProcessConfig
from agent.runtime import CommandRunner, tail_file


def collect(runner: CommandRunner, processes: list[ProcessConfig], log_lines: int) -> list[dict]:
    return [collect_process(runner, item, log_lines) for item in processes]


def collect_process(runner: CommandRunner, item: ProcessConfig, log_lines: int) -> dict:
    result = runner.run(["pgrep", "-fl", item.pattern])
    matches = [line for line in result.stdout.splitlines() if line.strip()]
    logs = [tail_file(path, log_lines) for path in item.log_paths]
    return {
        "type": "process",
        "name": item.name,
        "display_name": item.display_name or item.name,
        "status": "up" if result.returncode == 0 and matches else "down",
        "restart_count": 0,
        "enabled": False,
        "meta": {
            "pattern": item.pattern,
            "matches": matches,
            "log_paths": item.log_paths,
            "working_directory": item.working_dir,
        },
        "recent_logs": "\n".join(x for x in logs if x),
    }

