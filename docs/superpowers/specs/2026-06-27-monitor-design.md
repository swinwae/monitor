# Monitor 设计文档

> 自建的轻量监控面板:统一监控本机(Mac)与 ECS 上自己部署的项目/服务,提供全局概览、对象明细、内网穿透隧道拓扑。

- 日期:2026-06-27
- 状态:已通过 brainstorming 评审,待实现

## 1. 目标与范围

### 要解决的问题

监控分散在多台机器(本机 Mac、阿里云 ECS,未来可能更多)上、用多种方式托管(systemd / launchd / docker / 裸进程)的自有项目。需要一个全局概览(谁活着、谁挂了、谁在反复重启、谁在报错)和逐个对象的明细(配置、日志),以及本机与 ECS 之间 frp 内网穿透隧道的连接拓扑。

### 第一版做什么

- 统一发现并监控四类托管对象:**存活状态 + 最近日志 + 配置/元信息**。
- 中心端"关注"机制:从一堆被发现的对象里筛选出真正关心的。
- frp 隧道拓扑:从 ECS 的 frps admin API 拉取所有隧道及在线状态。
- 中文 Web 面板:全局概览、发现页、对象明细、隧道拓扑。

### 第一版明确不做(YAGNI)

- **不做** CPU/内存/磁盘等资源占用曲线。
- **不做** 告警/主动通知(挂了只在面板上变红,不推飞书/邮件)。
- **不做** 日志全量转发与历史检索(只存每个对象最近 N 行,覆盖式)。
- **不做** clash-verge 的专有代理面板(节点/延迟/流量)。clash-verge 走通用监控(存活+日志+配置)即可。
- **不做** 独立 SPA 前端构建链路。

这些都设计为可在后续版本作为独立模块追加,不影响第一版架构。

## 2. 整体架构

```
┌─────────────┐   POST /api/report (默认 30s)   ┌──────────────────────────┐
│ Mac 本机     │ ──────────────────────────────▶ │   ECS 中心 (公网)          │
│  agent      │  {host, monitors[], tunnels[]}  │  FastAPI 接收/鉴权         │
└─────────────┘                                 │  SQLite 存最新状态+最近日志 │
┌─────────────┐                                 │  Jinja2 中文 Web 面板      │
│ ECS 本机     │ ──────────────────────────────▶ │  概览 / 发现 / 明细 / 拓扑  │
│  agent      │  (含 frp 隧道拓扑)               │                          │
└─────────────┘                                 └──────────────────────────┘
┌─────────────┐                                        ▲ 浏览器访问
│ 未来更多机器  │ ──────────────────────────────────────┘
└─────────────┘
```

- **采集为 agent 主动 push 模式**:本机在 NAT 后面,ECS 无法反向拉取,因此统一由各机器的 agent 定时 push 到中心 API。
- **传输鉴权**:agent push 携带共享 token(中心与各 agent 各配一份);中心建议挂在现有 nginx 后走 HTTPS。
- **失联判定**:中心按对象的 `last_report_at`,超过阈值(默认 90s)标记为 `unknown`(失联),与对象自身挂掉的 `down` 区分——避免 agent 本身挂掉时把所有项目误判为正常。

## 3. 采集设计

采集分两类逻辑。

### 3.1 通用监控(覆盖绝大多数对象,含 clash-verge)

agent 统一发现四类托管对象,抽象成统一的"被监控对象(monitor)"。各类型的存活判定、日志来源、发现策略:

| 类型 | 存活判定 | 日志来源 | 发现策略 |
|------|---------|---------|---------|
| systemd | `systemctl is-active` | `journalctl -u <unit> -n N` | **全自动**发现所有 unit |
| launchd | `launchctl print` / `launchctl list` 有无 PID | plist 的 `StandardOutPath`/`StandardErrorPath` 文件 | **全自动**发现(`~/Library/LaunchAgents` 等;可按 label 前缀过滤) |
| docker | `docker inspect .State.Running` | `docker logs --tail N <container>` | **全自动**发现所有容器 |
| 裸进程 / nohup / pm2 | `pgrep` 匹配 | 配置里指定的日志文件 | **声明式**:在 agent 配置里写要盯的进程模式 + 日志路径 |

裸进程走声明式的原因:Mac 上裸进程数以百计,全量上报会淹没面板;而 systemd/launchd/docker 天然是"被托管的服务",数量可控,可全自动发现。

**自动解析到的字段(无需用户手填,来自真实采样验证):**

- launchd(`plutil -p <plist>` + `launchctl print`):启动命令(`ProgramArguments`)、工作目录、**日志路径**(`StandardOutPath`/`StandardErrorPath`)、运行状态、PID、**累计重启次数**(`runs`)、上次退出码(`last exit code`)、自启配置(`RunAtLoad`/`KeepAlive`)、环境变量。
- systemd(`systemctl show` + `journalctl`):描述、启动命令(`ExecStart`)、工作目录、状态(`ActiveState`/`SubState`)、PID、启动时间(`ActiveEnterTimestamp`)、重启策略(`Restart`)、**累计重启次数**(`NRestarts`)、**开机自启**(`UnitFileState`/`is-enabled`)、配置文件路径(`FragmentPath`)、日志(journalctl)。

> `restart_count` 是重要健康信号:采样中 `feishu-claude.bot` 的 `runs=50`,强烈暗示在反复崩溃重启。概览页对异常高的重启次数高亮。

### 3.2 专有探针(目前仅 frp,架构可扩展)

跑在 ECS 的 agent 额外执行一步:

1. 从 `frps.service` 的 `ExecStart` 找到 frps 配置文件路径。
2. 解析配置中 webServer/admin 段的地址、端口、用户名、密码(全自动,用户不手填密钥)。
3. 调 frps admin API(默认 `127.0.0.1:7500`)的 `/api/proxy/<type>` 拉取所有隧道。
4. 每条隧道提取:name、proto、remote_port、客户端来源地址、在线状态、今日流量、连接数。

探针机制设计为可扩展:未来可为 nginx / mysql / redis 等增加各自探针,与通用监控并存。

### 3.3 错误识别

`error_count` = 最近 N 行日志中命中错误正则的行数。默认正则可配:`ERROR|Exception|Traceback|panic|fatal|FATAL`。用于概览页标记"最近在报错"的对象,以及明细页日志的错误行高亮。

## 4. 数据模型(SQLite)

```
hosts
  id            主机标识(配置指定,如 "mac-mini" / "ecs-aliyun")
  name          显示名
  platform      darwin / linux
  last_seen     最后一次任意上报时间

monitors        一行 = 一个被监控对象(服务 / 容器 / 进程)
  id            稳定 ID = hash(host_id + type + name)
  host_id       → hosts.id
  type          systemd / launchd / docker / process
  name          unit 名 / 容器名 / 进程标识
  display_name  中文显示名(可在面板修改)
  status        up / down / unknown(失联)
  started_at    启动时间(可取到时)
  restart_count 累计重启次数(launchd runs / systemd NRestarts)
  last_exit_code 上次退出码(launchd)
  enabled       开机自启(RunAtLoad / is-enabled)
  meta          JSON:启动命令、工作目录、日志路径、env、描述、镜像/版本等
  recent_logs   最近 N 行日志(纯文本,每次上报覆盖)
  error_count   最近日志命中错误模式的行数
  is_watched    是否关注(默认 false)
  last_report_at 该对象最后一次被上报时间

tunnels         一行 = 一条 frp 隧道
  id            稳定 ID
  frps_host_id  → hosts.id(运行 frps 的机器,即 ECS)
  name          隧道名
  proto         tcp / udp / http / https
  remote_port   映射端口
  client_addr   来源客户端地址
  client_host_id 映射回的来源主机(可空)
  online        是否在线
  traffic_in    今日入流量
  traffic_out   今日出流量
  conn_count    连接数
  last_report_at 最后上报时间
```

- 日志只存"最近 N 行"且覆盖式写入,因此不单独建日志表,直接挂在 `monitors.recent_logs`,自动滚动。
- agent 每次上报 `{host, monitors[], tunnels[]}`,中心 upsert;只有运行 frps 的机器携带 `tunnels`。

## 5. HTTP API

```
POST  /api/report              agent 上报(需 token)。body: {host, monitors[], tunnels[]}
GET   /api/overview            概览:所有 host + 其下"关注"对象状态汇总
GET   /api/hosts/:id/all       发现页:某 host 下全部发现到的对象(含未关注)
GET   /api/monitors/:id        明细:单对象状态 + meta + recent_logs
POST  /api/monitors/:id/watch  切换关注
PATCH /api/monitors/:id        修改 display_name 等
GET   /api/tunnels             隧道拓扑数据
```

## 6. 面板布局(中文 UI)

1. **全局概览(首页)**:顶部汇总卡片(关注总数 · 运行 · 挂了 · 失联 · 最近报错);下方按主机分组(Mac / ECS),每行 `状态灯 · 显示名 · 类型 · 重启次数(异常高亮) · 报错标记 · 最后上报`;一张"隧道在线 N 条"入口卡片。
2. **隧道拓扑**:可视化 frps 下所有隧道 `客户端(机器) → 暴露端口`,在线/离线、流量;列表 + 简单连线图。
3. **发现页(每台主机)**:列出 agent 发现到的**全部**对象(含未关注),一键加/取消关注。
4. **明细页(单对象)**:状态/重启次数/启动时间/自启 + 配置(启动命令·工作目录·日志路径·env)+ 最近 N 行日志(错误高亮、可搜索过滤)。

刷新:前端定时轮询 `/api/overview` 更新状态灯(SSE 作为可选增强)。

## 7. 技术栈与项目结构

- **后端**:Python + FastAPI + SQLite(SQLModel)。单进程,ECS 用 systemd 运行,挂在现有 nginx 后。
- **前端**:服务端模板(Jinja2)+ Tailwind CDN + 少量原生 JS。零构建。
- **agent**:**纯 Python 标准库**(`subprocess` + `urllib` + `json`),零三方依赖,跨平台。配置 `config.toml`:host id、中心地址、token、上报间隔、裸进程声明清单、错误正则。Mac 用 launchd、ECS 用 systemd 拉起。

```
monitor/
  agent/
    agent.py                  主循环:发现 → 采集 → push
    collectors/               systemd.py · launchd.py · docker.py · process.py
    probes/                   frp.py
    config.example.toml
  server/
    main.py                   FastAPI app 入口
    db.py                     SQLite + 模型 + upsert
    api.py                    路由
    templates/                Jinja2 页面
    static/                   CSS / JS
  docs/
  README.md
```

## 8. 部署

- **中心**:ECS 上用 systemd 跑 uvicorn,nginx 反代(ECS 已有 nginx)。
- **agent**:Mac 用 launchd plist、ECS 用 systemd unit 拉起。
- **配置安全**:`config.toml`(含 token、自动解析出的 frps 密码不落盘)与 `deploy.md` 不进 git;`.gitignore` 覆盖 Python(`__pycache__`/`*.pyc`/`.venv`)、macOS(`.DS_Store`)。
- 首次部署后新建 `deploy.md` 记录服务器地址、路径、启动/重启命令。

## 9. 后续可扩展方向(非本期)

- 告警:对象 down / 失联 / 重启激增 / 报错时推飞书或邮件。
- 资源曲线:CPU/内存/磁盘随时间。
- clash-verge 专有探针:代理模式、节点延迟、实时流量。
- 日志全量转发与历史检索。
- 更多专有探针:nginx / mysql / redis。
