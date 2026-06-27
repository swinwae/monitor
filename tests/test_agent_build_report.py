from agent.agent import build_report
from agent.config import AgentConfig, HostConfig, ProcessConfig, ServerConfig
from agent.runtime import CommandResult


class FakeRunner:
    def run(self, args, timeout=8.0):
        if args == ["pgrep", "-fl", "demo"]:
            return CommandResult(1, "", "")
        raise AssertionError(args)


def test_build_report_with_declared_process_only():
    config = AgentConfig(
        host=HostConfig(id="mac", name="Mac", platform="darwin"),
        server=ServerConfig(url="http://127.0.0.1:8800", token="secret"),
        collect_systemd=False,
        collect_launchd=False,
        collect_docker=False,
        processes=[ProcessConfig(name="demo", pattern="demo")],
    )

    report = build_report(config, FakeRunner())

    assert report["host"] == {"id": "mac", "name": "Mac", "platform": "darwin"}
    assert report["monitors"][0]["type"] == "process"
    assert report["monitors"][0]["status"] == "down"
    assert report["tunnels"] == []

