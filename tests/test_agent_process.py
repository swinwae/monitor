from agent.collectors.process import collect_process
from agent.config import ProcessConfig
from agent.runtime import CommandResult


class FakeRunner:
    def run(self, args, timeout=8.0):
        assert args == ["pgrep", "-fl", "python worker.py"]
        return CommandResult(0, "123 python worker.py\n", "")


def test_collect_process_tails_logs(tmp_path):
    log = tmp_path / "worker.log"
    log.write_text("a\nb\nERROR boom\n", encoding="utf-8")
    cfg = ProcessConfig(name="worker", pattern="python worker.py", log_paths=[str(log)])

    item = collect_process(FakeRunner(), cfg, 2)

    assert item["type"] == "process"
    assert item["name"] == "worker"
    assert item["status"] == "up"
    assert item["meta"]["matches"] == ["123 python worker.py"]
    assert item["recent_logs"] == "b\nERROR boom"

