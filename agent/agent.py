from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from agent.collectors import docker, launchd, process, systemd
from agent.config import AgentConfig, load_config
from agent.probes import clash, frp
from agent.runtime import CommandRunner


def build_report(config: AgentConfig, runner: CommandRunner | None = None) -> dict:
    runner = runner or CommandRunner()
    monitors: list[dict] = []
    if config.collect_systemd and config.host.platform == "linux":
        monitors.extend(systemd.collect(runner, config.log_lines))
    if config.collect_launchd and config.host.platform == "darwin":
        monitors.extend(launchd.collect(runner, config.log_lines))
    if config.collect_docker:
        monitors.extend(docker.collect(runner, config.log_lines))
    monitors.extend(process.collect(runner, config.processes, config.log_lines))

    tunnels = []
    if config.frp.enabled:
        tunnels = frp.collect(runner, config.frp, config.server.timeout)

    if config.clash.enabled:
        merge_clash_runtime(monitors, clash.collect(config.clash, config.server.timeout))

    return {
        "host": {
            "id": config.host.id,
            "name": config.host.name,
            "platform": config.host.platform,
        },
        "monitors": monitors,
        "tunnels": tunnels,
    }


def merge_clash_runtime(monitors: list[dict], runtime_monitors: list[dict]) -> None:
    if not runtime_monitors:
        return
    runtime = runtime_monitors[0]
    target = find_clash_monitor(monitors)
    if target is None:
        monitors.extend(runtime_monitors)
        return
    clash_meta = runtime.get("meta", {})
    target.setdefault("meta", {})
    target["meta"]["clash"] = clash_meta
    active_node = clash_meta.get("active_node")
    if active_node:
        target["display_name"] = f"Clash Verge · {active_node}"
    logs = [target.get("recent_logs", ""), runtime.get("recent_logs", "")]
    target["recent_logs"] = "\n".join(x for x in logs if x)
    if runtime.get("status") == "down":
        target["status"] = "down"


def find_clash_monitor(monitors: list[dict]) -> dict | None:
    for item in monitors:
        name = str(item.get("name", "")).lower()
        display_name = str(item.get("display_name", "")).lower()
        if name == "clash-verge" or display_name == "clash verge":
            return item
    return None


def post_report(config: AgentConfig, report: dict) -> tuple[bool, str]:
    body = json.dumps(report, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{config.server.url}/api/report",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Monitor-Token": config.server.token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.server.timeout) as resp:
            text = resp.read().decode()
            return 200 <= resp.status < 300, text
    except urllib.error.HTTPError as exc:
        return False, exc.read().decode(errors="replace")
    except urllib.error.URLError as exc:
        return False, str(exc)


def run_once(config: AgentConfig, runner: CommandRunner | None = None) -> tuple[bool, str]:
    return post_report(config, build_report(config, runner))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor agent")
    parser.add_argument("-c", "--config", default="agent/config.toml", help="配置文件路径")
    parser.add_argument("--once", action="store_true", help="采集并上报一次后退出")
    parser.add_argument("--print", action="store_true", help="只打印采集 JSON,不上报")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    runner = CommandRunner()
    while True:
        report = build_report(config, runner)
        if args.print:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        ok, message = post_report(config, report)
        if not ok:
            print(f"report failed: {message}", file=sys.stderr)
        if args.once:
            return 0 if ok else 1
        time.sleep(config.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
