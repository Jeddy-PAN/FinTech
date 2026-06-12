# 阶段 39：可运行交付、观测和测试矩阵

本阶段把当前教学平台从“功能已经能跑”推进到“本地如何启动、如何判断可用、如何观察运行状态、如何验收”更清楚的形态。目标仍是教学版 operability，不引入真实部署平台、真实 secret 管理、生产监控系统或云基础设施。

## 1. 基础概念

### 中文定义

- 可运行交付 operable delivery：代码不仅能编译，还能用清晰命令启动、演示、测试和复核输出。
- readiness：服务依赖是否处在可用状态，例如本阶段检查各个 SQLite store 是否能打开。
- metrics：用结构化计数描述系统当前状态，例如 payment run 数量、failed async run 数量、denied access event 数量。
- test matrix：把验收命令、覆盖范围和期望结果列成矩阵，避免只靠口头说明“已经测过”。

### 英文术语

- operability
- readiness
- metrics
- test matrix
- local delivery
- observability

### 为什么金融系统需要它

金融系统的问题经常不是“代码能不能运行一次”，而是出问题时能否快速回答：

1. 服务依赖是否可用。
2. 当前是否有失败任务、待审批操作、拒绝访问或开放调查工单。
3. 本地交付前需要跑哪些测试。
4. demo 生成了哪些审计、报表和对账材料。

本阶段不做生产级监控，但先把这些问题变成结构化 API 和测试矩阵。

## 2. 本阶段实现

新增文件：

```text
labs/fintech-platform/platform_operability.py
labs/fintech-platform/test_platform_operability.py
```

修改文件：

```text
labs/fintech-platform/platform_api_app.py
labs/fintech-platform/test_platform_api_app.py
labs/fintech-platform/demo.py
```

新增核心对象：

```text
PlatformReadinessCheck
PlatformReadinessReport
PlatformMetric
PlatformMetricsSnapshot
PlatformTestMatrixRow
```

新增 API：

| Endpoint | 作用 |
| --- | --- |
| `GET /platform/operability/readiness` | 检查 platform store、access audit store、async run store、investigation case store 和 operation approval store 是否可打开 |
| `GET /platform/operability/metrics` | 汇总 payment runs、async runs、operation approvals、access events 和 investigation cases 的教学版计数 |
| `GET /platform/operability/test-matrix` | 返回本地 py_compile、平台测试、demo 和全量 labs 测试矩阵 |

这三个 endpoint 都会写入 API access audit。当前允许 `audit_reader`、`compliance_lead` 和 `ops_manager` 角色访问；缺少权限会返回 `403` 并留下 denied access audit。

## 3. Demo 接入

`demo.py` 现在会输出：

```text
Platform operability snapshot
```

输出内容包括：

- readiness 状态。
- payment runs、async runs、pending approvals、denied access 等关键 metrics。
- test matrix 行数。

这些输出用于说明：demo 不只是跑业务流程，也能展示本地可运行交付的观测入口。

## 4. 当前边界

本阶段仍不实现：

- 真实部署脚本、容器镜像、Kubernetes、CI/CD 或云环境。
- Prometheus / OpenTelemetry / APM 等生产观测系统。
- 真实 readiness probe、liveness probe 或自动故障恢复。
- 真实 secret 管理、环境隔离、配置中心或权限系统。
- 生产级日志采集、告警、SLO、SLA 或 on-call 流程。

当前 metrics 是教学版结构化计数，不代表生产监控指标；readiness 只检查本地 SQLite store 可打开，不代表外部依赖健康。

## 5. 已完成代码与测试

已验证：

```text
py_compile: passed
test_platform_operability.py + test_platform_api_app.py: 53 passed
labs/fintech-platform: 164 passed
demo.py: runnable, printed Platform operability snapshot
labs: 409 passed
```

后续建议阶段 40 进入最终验收与学习作品集总结：把当前平台能力、可运行命令、测试矩阵、剩余边界和学习成果整理成一个收尾验收视角。
