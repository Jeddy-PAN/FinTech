# FinTech Platform 系统结构图

这张图说明当前 `labs/fintech-platform` 在项目中的位置：它不是单纯的订单系统，而是把 KYC/AML、支付订单、风控、账本、审计、报表、审批和运维视角串起来的教学版金融业务编排平台。

```mermaid
flowchart LR
    ExternalCaller["External caller<br/>API client / operator / browser"]
    Console["Console / Manual<br/>HTML views"]
    API["FastAPI app<br/>platform_api_app.py"]
    ApiService["PlatformApiService<br/>idempotency + request fingerprint"]
    Platform["FinTechPlatform<br/>business orchestration"]

    KYC["KYC/AML<br/>customer screening"]
    Risk["Risk rule engine<br/>decision + review case"]
    PaymentOrder["Payment order<br/>status machine"]
    Ledger["Ledger<br/>double-entry posting"]
    Audit["Compliance audit<br/>timeline + access audit"]
    Store["SQLite stores<br/>runs / async / approvals / cases"]

    Async["Async run store + worker<br/>accepted / processing / completed / failed"]
    Approval["Operation approval<br/>maker-checker lifecycle"]
    Reports["Reports<br/>operations / ledger / settlement"]
    Evidence["Evidence package<br/>findings + approvals + denied access"]
    Operability["Operability<br/>readiness / metrics / test matrix"]
    ProviderBoundary["Future provider boundary<br/>webhook + settlement parser"]

    ExternalCaller --> API
    ExternalCaller --> Console
    Console --> API
    API --> ApiService
    API --> Async
    API --> Approval
    API --> Operability
    ApiService --> Platform
    Async --> ApiService

    Platform --> KYC
    Platform --> PaymentOrder
    Platform --> Risk
    Platform --> Ledger
    Platform --> Audit
    Platform --> Store

    Approval --> Async
    Store --> Reports
    Audit --> Reports
    Reports --> Evidence
    Audit --> Evidence
    ProviderBoundary -. planned .-> Reports
    ProviderBoundary -. planned .-> Platform
```

## 读图要点

- `External caller` 指所有从系统外进入的调用者，包括 API client、浏览器操作员和未来的外部 provider 事件。
- `PlatformApiService` 负责把外部请求整理成内部可处理的请求，并处理 `run_id` + request fingerprint 幂等。
- `FinTechPlatform` 是主业务编排层，负责串起 KYC/AML、payment order、risk、ledger 和 audit。
- `Async` 和 `Approval` 是高影响操作的工程边界：后台任务独立推进，失败重试要先进入审批。
- `ProviderBoundary` 目前仍是计划中的缺口，用于补齐外部 payment provider、webhook 和 settlement file。
