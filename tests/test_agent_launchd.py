import json

from agent.collectors.launchd import collect_plist, launchctl_list
from agent.runtime import CommandResult


class FakeRunner:
    def __init__(self, plist_payload=None):
        self.plist_payload = plist_payload or {}

    def run(self, args, timeout=8.0):
        if args == ["launchctl", "list"]:
            return CommandResult(0, "PID\tStatus\tLabel\n123\t0\tcom.demo.worker\n-\t1\tcom.down\n", "")
        if args[:4] == ["plutil", "-convert", "json", "-o"]:
            return CommandResult(0, json.dumps(self.plist_payload), "")
        if args[:2] == ["launchctl", "print"]:
            return CommandResult(0, "runs = 5\nlast exit code = 0\n", "")
        raise AssertionError(args)


def test_launchctl_list():
    labels = launchctl_list(FakeRunner())

    assert labels["com.demo.worker"]["pid"] == 123
    assert labels["com.down"]["pid"] is None


def test_collect_plist(tmp_path):
    out = tmp_path / "out.log"
    out.write_text("hello\nERROR bad\n", encoding="utf-8")
    plist = tmp_path / "com.demo.worker.plist"
    plist.write_text("<plist/>", encoding="utf-8")
    runner = FakeRunner(
        {
            "Label": "com.demo.worker",
            "ProgramArguments": ["/usr/bin/python3", "worker.py"],
            "RunAtLoad": True,
            "StandardOutPath": str(out),
        }
    )

    item = collect_plist(runner, plist, {"com.demo.worker": {"pid": 123, "status": 0}}, 10)

    assert item["name"] == "com.demo.worker"
    assert item["status"] == "up"
    assert item["restart_count"] == 5
    assert item["enabled"] is True
    assert item["meta"]["program_arguments"] == ["/usr/bin/python3", "worker.py"]
    assert "ERROR bad" in item["recent_logs"]

