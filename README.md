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

### 面板鉴权边界

面板所有只读页面（`/`、`/hosts/*`、`/monitors/*`、`/tunnels`）及关注/改名等写操作接口默认**不带 token 验证**，任何能访问该端口的请求均可读写。  
**仅 `POST /api/report`（agent 上报）由 `MONITOR_TOKEN` 保护。**

因此，面板必须部署在受信内网或反向代理（建议 HTTPS + IP 白名单/Basic Auth）之后，**切勿将端口直接暴露到公网**。若需公网访问，请在 Nginx/Caddy 层加鉴权。

## agent
见 Plan 2(`docs/superpowers/plans/*-monitor-agent.md`)。
