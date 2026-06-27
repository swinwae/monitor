# Monitor Agent 采集端实现计划

> Plan 2:实现各机器本地 agent,采集服务状态、最近日志、配置元信息与 frp 隧道拓扑,并主动 push 到中心 server。

**Goal:** 在不引入三方依赖的前提下,提供可在 Mac 与 ECS/Linux 上运行的 Python agent。agent 根据 `config.toml` 定时构造 `{host, monitors[], tunnels[]}` 并调用中心端 `POST /api/report`。

**Architecture:** 标准库模块化实现。`agent.agent` 负责 CLI、主循环、上报;`agent.config` 负责 TOML 配置;`agent.collectors.*` 分别实现 systemd / launchd / docker / process;`agent.probes.frp` 实现 frps admin API 自动发现与隧道采集。

**Tech Stack:** Python 3.11+ 标准库(`tomllib`、`subprocess`、`urllib`、`json`、`configparser`)。

## Global Constraints

- agent 不依赖 FastAPI/SQLModel 等 server 依赖,保持纯标准库。
- 上报 payload 必须兼容 server 的 `ReportIn` schema。
- 自动发现失败时返回空列表,不能让整个 agent 崩溃。
- 裸进程只通过配置声明采集,不全量扫描所有进程。
- 本地配置 `agent/config.toml` 含 token,不进 git;只提交 `agent/config.example.toml`。
- 日志只读取最近 N 行,不做全量历史转发。

## Tasks

- [x] 创建 agent 包结构与配置加载。
- [x] 实现命令执行、日志 tail 等运行时工具。
- [x] 实现 systemd collector: unit 列表、状态、重启次数、journal 最近日志。
- [x] 实现 launchd collector: plist 解析、PID 状态、runs/last exit code、日志路径。
- [x] 实现 docker collector: 容器状态、inspect 元信息、logs 最近日志。
- [x] 实现 process collector: 配置声明、pgrep 存活判定、日志文件 tail。
- [x] 实现 frp probe: 从 frps.service 自动发现配置,解析 TOML/INI,调用 admin API。
- [x] 实现 CLI: `--print`、`--once`、循环上报。
- [x] 补测试覆盖配置、解析、聚合与边界。
- [x] 更新 README agent 使用说明。

