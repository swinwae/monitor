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

agent 为纯 Python 标准库实现,负责在每台机器上发现/采集并主动上报到中心 server。

### 配置

```bash
cp agent/config.example.toml agent/config.toml
```

编辑 `agent/config.toml`:

- `[host]`: 当前机器的稳定 ID、显示名、平台(`darwin`/`linux`)
- `[server]`: 中心 server 地址与 `MONITOR_TOKEN`
- `[collectors]`: 是否开启 systemd / launchd / docker 自动发现
- `[[processes]]`: 裸进程声明式监控,填写 `pattern` 与日志路径
- `[frp]`: ECS 上运行 frps 时开启,默认从 `frps.service` 自动发现 admin API 配置
- `[clash]`: 本机运行 Clash Verge/Mihomo 时开启,采集当前模式、主策略组、当前选择与实际生效节点

### 本地调试

只采集并打印 JSON:

```bash
python -m agent.agent -c agent/config.toml --print
```

采集并上报一次:

```bash
python -m agent.agent -c agent/config.toml --once
```

常驻循环上报:

```bash
python -m agent.agent -c agent/config.toml
```

### 部署建议

- Mac: 用 launchd 拉起 `python -m agent.agent -c /path/to/agent/config.toml`
- Linux/ECS: 用 systemd 拉起同一命令
- `agent/config.toml` 含 token,已被 `.gitignore` 排除,不要提交
