from __future__ import annotations

from agent.runtime import CommandRunner, command_exists


PROPERTIES = [
    "Id",
    "Description",
    "ActiveState",
    "SubState",
    "ExecMainPID",
    "ExecStart",
    "WorkingDirectory",
    "ActiveEnterTimestamp",
    "Restart",
    "NRestarts",
    "UnitFileState",
    "FragmentPath",
]


def collect(runner: CommandRunner, log_lines: int) -> list[dict]:
    if not command_exists("systemctl"):
        return []
    listed = runner.run(
        ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"]
    )
    if listed.returncode != 0:
        return []
    units = [line.split()[0] for line in listed.stdout.splitlines() if line.strip()]
    return [m for unit in units if (m := collect_unit(runner, unit, log_lines)) is not None]


def collect_unit(runner: CommandRunner, unit: str, log_lines: int) -> dict | None:
    args = ["systemctl", "show", unit]
    for prop in PROPERTIES:
        args.append(f"--property={prop}")
    shown = runner.run(args)
    if shown.returncode != 0:
        return None
    props = parse_systemctl_show(shown.stdout)
    active = props.get("ActiveState", "")
    logs = runner.run(["journalctl", "-u", unit, "-n", str(log_lines), "--no-pager"])
    return {
        "type": "systemd",
        "name": props.get("Id") or unit,
        "display_name": props.get("Description") or None,
        "status": "up" if active == "active" else "down",
        "started_at": props.get("ActiveEnterTimestamp") or None,
        "restart_count": _int(props.get("NRestarts")),
        "enabled": props.get("UnitFileState") == "enabled",
        "meta": {
            "description": props.get("Description"),
            "sub_state": props.get("SubState"),
            "pid": _int(props.get("ExecMainPID")),
            "exec_start": props.get("ExecStart"),
            "working_directory": props.get("WorkingDirectory"),
            "restart": props.get("Restart"),
            "unit_file_state": props.get("UnitFileState"),
            "fragment_path": props.get("FragmentPath"),
        },
        "recent_logs": logs.stdout if logs.returncode == 0 else logs.stderr,
    }


def parse_systemctl_show(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key] = value
    return props


def _int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0

