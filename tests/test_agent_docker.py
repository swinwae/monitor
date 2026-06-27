import json

from agent.collectors.docker import collect_container
from agent.runtime import CommandResult


class FakeRunner:
    def run(self, args, timeout=8.0):
        if args[:2] == ["docker", "inspect"]:
            return CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "State": {
                                "Running": True,
                                "StartedAt": "2026-06-27T12:00:00Z",
                                "Restarting": False,
                                "ExitCode": 0,
                            },
                            "RestartCount": 3,
                            "Config": {"Env": ["A=B"], "WorkingDir": "/app"},
                        }
                    ]
                ),
                "",
            )
        if args[:2] == ["docker", "logs"]:
            return CommandResult(0, "ready\n", "")
        raise AssertionError(args)


def test_collect_container():
    item = collect_container(
        FakeRunner(),
        {"ID": "abc", "Names": "web", "Image": "nginx", "State": "running"},
        50,
    )

    assert item["type"] == "docker"
    assert item["name"] == "web"
    assert item["status"] == "up"
    assert item["restart_count"] == 3
    assert item["meta"]["working_directory"] == "/app"
    assert item["recent_logs"] == "ready\n"

