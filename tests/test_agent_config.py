from agent.config import load_config


def test_load_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
interval_seconds = 15
log_lines = 20

[host]
id = "ecs"
name = "ECS"
platform = "linux"

[server]
url = "http://127.0.0.1:8800/"
token = "secret"

[collectors]
systemd = true
launchd = false
docker = false

[[processes]]
name = "worker"
pattern = "python worker.py"
log_path = "/tmp/worker.log"

[frp]
enabled = true
admin_url = "http://127.0.0.1:7500"
username = "admin"
password = "pwd"
""",
        encoding="utf-8",
    )

    loaded = load_config(cfg)

    assert loaded.host.id == "ecs"
    assert loaded.server.url == "http://127.0.0.1:8800"
    assert loaded.server.token == "secret"
    assert loaded.interval_seconds == 15
    assert loaded.log_lines == 20
    assert not loaded.collect_launchd
    assert loaded.processes[0].log_paths == ["/tmp/worker.log"]
    assert loaded.frp.enabled
    assert loaded.frp.admin_url == "http://127.0.0.1:7500"
