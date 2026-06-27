from agent.collectors.systemd import collect_unit, parse_systemctl_show
from agent.runtime import CommandResult


class FakeRunner:
    def run(self, args, timeout=8.0):
        if args[:3] == ["systemctl", "show", "demo.service"]:
            return CommandResult(
                0,
                "\n".join(
                    [
                        "Id=demo.service",
                        "Description=Demo Service",
                        "ActiveState=active",
                        "SubState=running",
                        "ExecMainPID=123",
                        "ExecStart={ path=/usr/bin/demo ; argv[]=/usr/bin/demo ; }",
                        "WorkingDirectory=/opt/demo",
                        "ActiveEnterTimestamp=Sat 2026-06-27 12:00:00 CST",
                        "Restart=always",
                        "NRestarts=7",
                        "UnitFileState=enabled",
                        "FragmentPath=/etc/systemd/system/demo.service",
                    ]
                ),
                "",
            )
        if args[:2] == ["journalctl", "-u"]:
            return CommandResult(0, "ok\nERROR failed once\n", "")
        raise AssertionError(args)


def test_parse_systemctl_show():
    assert parse_systemctl_show("A=1\nB=two=three\n") == {"A": "1", "B": "two=three"}


def test_collect_unit():
    item = collect_unit(FakeRunner(), "demo.service", 80)

    assert item["name"] == "demo.service"
    assert item["status"] == "up"
    assert item["restart_count"] == 7
    assert item["enabled"] is True
    assert item["meta"]["pid"] == 123
    assert "ERROR failed once" in item["recent_logs"]

