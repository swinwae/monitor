from __future__ import annotations

import http.client
import json
import socket
from dataclasses import dataclass

from agent.config import ClashConfig


SELECTOR_TYPES = {"Selector", "URLTest", "Fallback", "LoadBalance", "Relay"}


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_socket: str, timeout: float = 8.0):
        super().__init__("localhost", timeout=timeout)
        self.unix_socket = unix_socket

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.unix_socket)


@dataclass
class ClashSnapshot:
    mode: str | None
    main_group: str
    selected_group: str | None
    active_node: str | None
    active_alive: bool | None
    selectors: dict[str, str]
    mixed_port: int | None
    tun_enabled: bool | None


def collect(config: ClashConfig, timeout: float = 8.0) -> list[dict]:
    snap = read_snapshot(config, timeout)
    if snap is None:
        return [{
            "type": "clash",
            "name": "clash-verge-runtime",
            "display_name": "Clash Verge 当前节点: 未连接",
            "status": "down",
            "meta": {"unix_socket": config.unix_socket, "main_group": config.main_group},
            "recent_logs": "无法读取 Clash/Mihomo 控制接口",
        }]
    title = snap.active_node or snap.selected_group or "未知"
    return [{
        "type": "clash",
        "name": "clash-verge-runtime",
        "display_name": f"Clash Verge 当前节点: {title}",
        "status": "up" if snap.active_node else "down",
        "meta": {
            "mode": snap.mode,
            "main_group": snap.main_group,
            "selected_group": snap.selected_group,
            "active_node": snap.active_node,
            "active_alive": snap.active_alive,
            "selectors": snap.selectors,
            "mixed_port": snap.mixed_port,
            "tun_enabled": snap.tun_enabled,
            "unix_socket": config.unix_socket,
        },
        "recent_logs": "\n".join([
            f"模式: {snap.mode or 'unknown'}",
            f"主策略组: {snap.main_group}",
            f"当前选择: {snap.selected_group or 'unknown'}",
            f"实际节点: {snap.active_node or 'unknown'}",
        ]),
    }]


def read_snapshot(config: ClashConfig, timeout: float = 8.0) -> ClashSnapshot | None:
    proxies_payload = request_json(config.unix_socket, "/proxies", timeout)
    configs_payload = request_json(config.unix_socket, "/configs", timeout)
    proxies = proxies_payload.get("proxies")
    if not isinstance(proxies, dict):
        return None
    main_group = config.main_group if config.main_group in proxies else choose_main_group(proxies)
    selected_group, active_node = resolve_active_node(proxies, main_group)
    selectors = selector_choices(proxies)
    active_alive = None
    if active_node and isinstance(proxies.get(active_node), dict):
        active_alive = proxies[active_node].get("alive")
    tun = configs_payload.get("tun") if isinstance(configs_payload.get("tun"), dict) else {}
    return ClashSnapshot(
        mode=configs_payload.get("mode"),
        main_group=main_group,
        selected_group=selected_group,
        active_node=active_node,
        active_alive=active_alive,
        selectors=selectors,
        mixed_port=configs_payload.get("mixed-port"),
        tun_enabled=tun.get("enable"),
    )


def request_json(unix_socket: str, path: str, timeout: float) -> dict:
    conn = UnixHTTPConnection(unix_socket, timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        if resp.status >= 400:
            return {}
        return json.loads(resp.read().decode())
    except (OSError, TimeoutError, json.JSONDecodeError, http.client.HTTPException):
        return {}
    finally:
        conn.close()


def choose_main_group(proxies: dict) -> str:
    for name in ["Proxies", "GLOBAL", "Proxy", "🚀 节点选择"]:
        if name in proxies:
            return name
    for name, item in proxies.items():
        if isinstance(item, dict) and item.get("type") in SELECTOR_TYPES and item.get("now"):
            return name
    return next(iter(proxies), "unknown")


def resolve_active_node(proxies: dict, main_group: str) -> tuple[str | None, str | None]:
    seen: set[str] = set()
    current = main_group
    selected_group = None
    while current and current not in seen:
        seen.add(current)
        item = proxies.get(current)
        if not isinstance(item, dict):
            return selected_group, current
        now = item.get("now")
        if item.get("type") not in SELECTOR_TYPES or not now:
            return selected_group, item.get("name") or current
        selected_group = now
        current = now
    return selected_group, current


def selector_choices(proxies: dict) -> dict[str, str]:
    choices: dict[str, str] = {}
    for name, item in proxies.items():
        if isinstance(item, dict) and item.get("type") in SELECTOR_TYPES and item.get("now"):
            choices[name] = item["now"]
    return choices
