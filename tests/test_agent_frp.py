from agent.config import FrpConfig
from agent.probes.frp import discover_config_path, parse_frps_config, proxy_to_tunnel, resolve_admin
from agent.runtime import CommandResult


class FakeRunner:
    def run(self, args, timeout=8.0):
        assert args == ["systemctl", "show", "frps.service", "--property=ExecStart", "--value"]
        return CommandResult(0, "/usr/local/bin/frps -c /etc/frp/frps.toml\n", "")


def test_discover_config_path():
    assert str(discover_config_path(FakeRunner(), "frps.service")) == "/etc/frp/frps.toml"


def test_parse_frps_toml(tmp_path):
    path = tmp_path / "frps.toml"
    path.write_text(
        """
[webServer]
addr = "127.0.0.1"
port = 7500
user = "admin"
password = "pwd"
""",
        encoding="utf-8",
    )

    admin = parse_frps_config(path)

    assert admin.url == "http://127.0.0.1:7500"
    assert admin.username == "admin"
    assert admin.password == "pwd"


def test_resolve_manual_admin():
    admin = resolve_admin(
        FakeRunner(),
        FrpConfig(enabled=True, admin_url="http://127.0.0.1:7500", username="u", password="p"),
    )

    assert admin.url == "http://127.0.0.1:7500"
    assert admin.username == "u"


def test_proxy_to_tunnel():
    item = proxy_to_tunnel(
        "tcp",
        {
            "name": "ssh",
            "status": "online",
            "conf": {"type": "tcp", "remotePort": 6000},
            "clientAddr": "10.0.0.2:1234",
            "todayTrafficIn": 12,
            "todayTrafficOut": 34,
            "curConns": 2,
        },
    )

    assert item == {
        "name": "ssh",
        "proto": "tcp",
        "remote_port": 6000,
        "client_addr": "10.0.0.2:1234",
        "online": True,
        "traffic_in": 12,
        "traffic_out": 34,
        "conn_count": 2,
    }

