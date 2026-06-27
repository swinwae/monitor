from __future__ import annotations

import base64
import configparser
import json
import re
import shlex
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from agent.config import FrpConfig
from agent.runtime import CommandRunner


PROXY_TYPES = ["tcp", "udp", "http", "https", "stcp", "xtcp"]


@dataclass
class FrpsAdmin:
    url: str
    username: str | None = None
    password: str | None = None


def collect(runner: CommandRunner, config: FrpConfig, timeout: float = 8.0) -> list[dict]:
    admin = resolve_admin(runner, config)
    if admin is None:
        return []
    tunnels: list[dict] = []
    for proto in PROXY_TYPES:
        payload = fetch_json(admin, f"/api/proxy/{proto}", timeout)
        for item in payload.get("proxies", []):
            tunnels.append(proxy_to_tunnel(proto, item))
    return tunnels


def resolve_admin(runner: CommandRunner, config: FrpConfig) -> FrpsAdmin | None:
    if config.admin_url:
        return FrpsAdmin(config.admin_url.rstrip("/"), config.username, config.password)
    conf_path = discover_config_path(runner, config.service_name)
    if conf_path is None:
        return None
    return parse_frps_config(conf_path)


def discover_config_path(runner: CommandRunner, service_name: str) -> Path | None:
    result = runner.run(["systemctl", "show", service_name, "--property=ExecStart", "--value"])
    if result.returncode != 0:
        return None
    try:
        parts = shlex.split(result.stdout.strip())
    except ValueError:
        return None
    for index, part in enumerate(parts):
        if part in {"-c", "--config"} and index + 1 < len(parts):
            return Path(parts[index + 1])
        if part.startswith("--config="):
            return Path(part.split("=", 1)[1])
    for part in parts[1:]:
        if part.endswith((".ini", ".toml")):
            return Path(part)
    return None


def parse_frps_config(path: Path) -> FrpsAdmin | None:
    if not path.exists():
        return None
    if path.suffix == ".toml":
        with path.open("rb") as f:
            data = tomllib.load(f)
        web = data.get("webServer", {})
        addr = web.get("addr", "127.0.0.1")
        port = web.get("port")
        if not port:
            return None
        return FrpsAdmin(
            url=f"http://{addr}:{port}",
            username=web.get("user"),
            password=web.get("password"),
        )

    parser = configparser.ConfigParser()
    parser.read(path)
    common = parser["common"] if parser.has_section("common") else parser.defaults()
    port = common.get("dashboard_port") or common.get("admin_port")
    if not port:
        return None
    addr = common.get("dashboard_addr") or common.get("admin_addr") or "127.0.0.1"
    return FrpsAdmin(
        url=f"http://{addr}:{port}",
        username=common.get("dashboard_user") or common.get("admin_user"),
        password=common.get("dashboard_pwd") or common.get("admin_pwd"),
    )


def fetch_json(admin: FrpsAdmin, path: str, timeout: float) -> dict:
    req = urllib.request.Request(urljoin(admin.url + "/", path.lstrip("/")))
    if admin.username and admin.password:
        token = base64.b64encode(f"{admin.username}:{admin.password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def proxy_to_tunnel(proto: str, item: dict) -> dict:
    conf = item.get("conf") or {}
    name = item.get("name") or conf.get("name") or item.get("proxyName") or "unknown"
    status = str(item.get("status") or item.get("phase") or "").lower()
    return {
        "name": name,
        "proto": conf.get("type") or item.get("type") or proto,
        "remote_port": _int(conf.get("remotePort") or conf.get("remote_port") or item.get("remotePort")),
        "client_addr": item.get("clientAddr") or item.get("client_addr") or _client_addr(item),
        "online": status in {"online", "running", "start"} or bool(item.get("todayTrafficIn") or item.get("curConns")),
        "traffic_in": _int(item.get("todayTrafficIn") or item.get("trafficIn") or item.get("inBytes")),
        "traffic_out": _int(item.get("todayTrafficOut") or item.get("trafficOut") or item.get("outBytes")),
        "conn_count": _int(item.get("curConns") or item.get("connCount")),
    }


def _client_addr(item: dict) -> str | None:
    raw = item.get("client")
    if isinstance(raw, dict):
        return raw.get("address") or raw.get("addr")
    if isinstance(raw, str):
        match = re.search(r"\d+\.\d+\.\d+\.\d+:\d+", raw)
        return match.group(0) if match else raw
    return None


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

