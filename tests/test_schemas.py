from server.schemas import ReportIn


def test_parse_report():
    """测试解析完整的上报数据"""
    payload = {
        "host": {"id": "mac", "name": "Mac", "platform": "darwin"},
        "monitors": [{
            "type": "launchd", "name": "com.feishu-claude.bot",
            "status": "up", "restart_count": 50, "enabled": True,
            "meta": {"cmd": "python main.py"}, "recent_logs": "ok\n"
        }],
        "tunnels": [{"name": "web", "proto": "tcp", "remote_port": 7001, "online": True}],
    }
    r = ReportIn.model_validate(payload)
    assert r.host.id == "mac"
    assert r.monitors[0].restart_count == 50
    assert r.monitors[0].meta["cmd"] == "python main.py"
    assert r.tunnels[0].remote_port == 7001


def test_defaults_when_minimal():
    """测试最小必需字段时的默认值"""
    r = ReportIn.model_validate({"host": {"id": "x", "name": "X", "platform": "linux"}})
    assert r.monitors == [] and r.tunnels == []
