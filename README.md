# Monitor

自建轻量监控面板:统一监控本机与 ECS 上自部署的项目(存活/日志/配置)+ frp 隧道拓扑。

## 中心 server

### 本地运行
```bash
pip install -r requirements-dev.txt
export MONITOR_TOKEN=$(openssl rand -hex 16)   # agent 上报用的共享密钥
export MONITOR_DB=monitor.db
uvicorn server.main:app --host 0.0.0.0 --port 8800
```
浏览器打开 http://localhost:8800

### 测试
```bash
python -m pytest -v
```

## agent
见 Plan 2(`docs/superpowers/plans/*-monitor-agent.md`)。
