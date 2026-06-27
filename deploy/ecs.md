# ECS 部署说明

> 目标:用 GitHub public 仓库 + ECS `git pull` 部署中心 server 与 ECS 本机 agent。

## 路径约定

- 项目目录:`/opt/monitor`
- Python 虚拟环境:`/opt/monitor/.venv`
- SQLite 数据库:`/opt/monitor/data/monitor.db`
- server 环境变量:`/opt/monitor/server.env`
- agent 配置:`/opt/monitor/agent/config.toml`

## 首次部署

```bash
cd /opt
git clone https://github.com/swinwae/monitor.git
cd /opt/monitor
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p data
cp deploy/examples/server.env.example server.env
cp deploy/examples/agent.ecs.config.example.toml agent/config.toml
```

编辑本地文件:

- `server.env`:设置 `MONITOR_TOKEN`
- `agent/config.toml`:让 `[server].token` 与 `MONITOR_TOKEN` 一致

安装 systemd:

```bash
cp deploy/systemd/monitor-server.service /etc/systemd/system/monitor-server.service
cp deploy/systemd/monitor-agent.service /etc/systemd/system/monitor-agent.service
systemctl daemon-reload
systemctl enable --now monitor-server monitor-agent
```

## 更新部署

```bash
cd /opt/monitor
git pull
.venv/bin/pip install -r requirements.txt
systemctl restart monitor-server monitor-agent
```

## 验证

```bash
systemctl status monitor-server monitor-agent --no-pager
curl -s http://127.0.0.1:8800/api/health
```

## Nginx 反代

面板没有内置登录,不要直接把 `8800` 暴露公网。可以参考:

```bash
cp deploy/nginx/monitor.conf.example /etc/nginx/conf.d/monitor.conf
nginx -t
systemctl reload nginx
```

上线前必须为该 server block 增加 Basic Auth、IP 白名单或其它访问控制。

## frps 隧道拓扑

当前 agent 需要 frps 的 `webServer`/admin API 才能采集隧道拓扑。如果 `/opt/frp/frps.toml` 只有 `bindPort`、`vhostHTTPPort`,则只能监控 `frps.service` 本身,隧道拓扑为空。

frps 可增加类似配置:

```toml
[webServer]
addr = "127.0.0.1"
port = 7500
user = "admin"
password = "change-me"
```

修改 frps 配置后需要重启 frps。该密码不要提交到 git。

