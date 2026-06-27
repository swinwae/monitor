from __future__ import annotations

import platform
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HostConfig:
    id: str
    name: str
    platform: str


@dataclass
class ServerConfig:
    url: str
    token: str
    timeout: float = 8.0


@dataclass
class ProcessConfig:
    name: str
    pattern: str
    display_name: str | None = None
    log_paths: list[str] = field(default_factory=list)
    working_dir: str | None = None


@dataclass
class FrpConfig:
    enabled: bool = False
    service_name: str = "frps.service"
    admin_url: str | None = None
    username: str | None = None
    password: str | None = None


@dataclass
class ClashConfig:
    enabled: bool = False
    unix_socket: str = "/tmp/verge/verge-mihomo.sock"
    main_group: str = "Proxies"


@dataclass
class AgentConfig:
    host: HostConfig
    server: ServerConfig
    interval_seconds: int = 30
    log_lines: int = 80
    collect_systemd: bool = True
    collect_launchd: bool = True
    collect_docker: bool = True
    processes: list[ProcessConfig] = field(default_factory=list)
    frp: FrpConfig = field(default_factory=FrpConfig)
    clash: ClashConfig = field(default_factory=ClashConfig)


def _default_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    if system == "linux":
        return "linux"
    return system or "unknown"


def load_config(path: str | Path) -> AgentConfig:
    with Path(path).expanduser().open("rb") as f:
        raw = tomllib.load(f)

    host_raw = raw.get("host", {})
    host_id = host_raw.get("id") or platform.node() or "local"
    host = HostConfig(
        id=host_id,
        name=host_raw.get("name") or host_id,
        platform=host_raw.get("platform") or _default_platform(),
    )

    server_raw = raw.get("server", {})
    server = ServerConfig(
        url=server_raw["url"].rstrip("/"),
        token=server_raw["token"],
        timeout=float(server_raw.get("timeout", 8.0)),
    )

    collectors = raw.get("collectors", {})
    processes = [
        ProcessConfig(
            name=item["name"],
            pattern=item["pattern"],
            display_name=item.get("display_name"),
            log_paths=_as_list(item.get("log_paths") or item.get("log_path")),
            working_dir=item.get("working_dir"),
        )
        for item in raw.get("processes", [])
    ]
    frp_raw = raw.get("frp", {})
    clash_raw = raw.get("clash", {})

    return AgentConfig(
        host=host,
        server=server,
        interval_seconds=int(raw.get("interval_seconds", 30)),
        log_lines=int(raw.get("log_lines", 80)),
        collect_systemd=bool(collectors.get("systemd", True)),
        collect_launchd=bool(collectors.get("launchd", True)),
        collect_docker=bool(collectors.get("docker", True)),
        processes=processes,
        frp=FrpConfig(
            enabled=bool(frp_raw.get("enabled", False)),
            service_name=frp_raw.get("service_name", "frps.service"),
            admin_url=frp_raw.get("admin_url"),
            username=frp_raw.get("username"),
            password=frp_raw.get("password"),
        ),
        clash=ClashConfig(
            enabled=bool(clash_raw.get("enabled", False)),
            unix_socket=clash_raw.get("unix_socket", "/tmp/verge/verge-mihomo.sock"),
            main_group=clash_raw.get("main_group", "Proxies"),
        ),
    )


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)
