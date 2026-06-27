from agent.config import AgentConfig, ClashConfig, HostConfig, ProcessConfig, ServerConfig
from agent.agent import build_report, merge_clash_runtime
from agent.probes.clash import collect, choose_main_group, resolve_active_node, selector_choices


PROXIES = {
    "Proxies": {"name": "Proxies", "type": "Selector", "now": "Auto - UrlTest"},
    "Auto - UrlTest": {
        "name": "Auto - UrlTest",
        "type": "URLTest",
        "now": "node-4",
        "all": ["node-1", "node-4"],
    },
    "Apple": {"name": "Apple", "type": "Selector", "now": "DIRECT"},
    "node-4": {"name": "node-4", "type": "Shadowsocks", "alive": True},
}


def test_choose_main_group_prefers_proxies():
    assert choose_main_group(PROXIES) == "Proxies"


def test_resolve_active_node_follows_selector_chain():
    selected, active = resolve_active_node(PROXIES, "Proxies")

    assert selected == "node-4"
    assert active == "node-4"


def test_selector_choices():
    choices = selector_choices(PROXIES)

    assert choices["Proxies"] == "Auto - UrlTest"
    assert choices["Auto - UrlTest"] == "node-4"
    assert choices["Apple"] == "DIRECT"


def test_build_report_merges_clash_probe_into_clash_verge(monkeypatch):
    config = AgentConfig(
        host=HostConfig(id="mac", name="Mac", platform="darwin"),
        server=ServerConfig(url="http://127.0.0.1:8800", token="secret"),
        collect_systemd=False,
        collect_launchd=False,
        collect_docker=False,
        processes=[ProcessConfig(name="clash-verge", pattern="clash-verge")],
        clash=ClashConfig(enabled=True),
    )

    def fake_collect(clash_config, timeout):
        return [{
            "type": "clash",
            "name": "clash-verge-runtime",
            "display_name": "Clash Verge 当前节点: node-4",
            "status": "up",
            "meta": {"active_node": "node-4"},
            "recent_logs": "",
        }]

    monkeypatch.setattr("agent.agent.clash.collect", fake_collect)

    class FakeRunner:
        def run(self, args, timeout=8.0):
            from agent.runtime import CommandResult
            return CommandResult(0, "123 /Applications/Clash Verge.app/Contents/MacOS/clash-verge\n", "")

    report = build_report(config, FakeRunner())

    assert len(report["monitors"]) == 1
    assert report["monitors"][0]["type"] == "process"
    assert report["monitors"][0]["name"] == "clash-verge"
    assert report["monitors"][0]["display_name"] == "Clash Verge · node-4"
    assert report["monitors"][0]["meta"]["clash"]["active_node"] == "node-4"


def test_merge_clash_runtime_falls_back_to_separate_monitor():
    monitors = []
    runtime = [{"type": "clash", "name": "clash-verge-runtime", "status": "up"}]

    merge_clash_runtime(monitors, runtime)

    assert monitors == runtime


def test_collect_formats_runtime_monitor(monkeypatch):
    monkeypatch.setattr(
        "agent.probes.clash.read_snapshot",
        lambda config, timeout: type("Snapshot", (), {
            "mode": "rule",
            "main_group": "Proxies",
            "selected_group": "Auto - UrlTest",
            "active_node": "node-4",
            "active_alive": True,
            "selectors": {"Proxies": "Auto - UrlTest"},
            "mixed_port": 7897,
            "tun_enabled": True,
        })(),
    )

    monitors = collect(ClashConfig(enabled=True))

    assert monitors[0]["type"] == "clash"
    assert monitors[0]["display_name"] == "Clash Verge 当前节点: node-4"
    assert monitors[0]["status"] == "up"
    assert monitors[0]["meta"]["active_node"] == "node-4"
