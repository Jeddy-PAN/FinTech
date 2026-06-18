# FinTech Learning Lab 图集

本目录保存项目结构图和关键流程图。图使用 Mermaid 写在 Markdown 中，方便后续修改、复用和 Git diff。

## 图表列表

1. [fintech-platform-architecture.md](fintech-platform-architecture.md)：当前综合平台系统结构图。
2. [payment-provider-boundary-flow.md](payment-provider-boundary-flow.md)：外部 payment provider 与内部平台的协议边界。
3. [payment-run-lifecycle.md](payment-run-lifecycle.md)：payment run、async run、retry approval 和 worker 的生命周期。
4. [reconciliation-and-evidence-flow.md](reconciliation-and-evidence-flow.md)：对账、异常、调查工单和 evidence package 流程。

## 阅读建议

如果是第一次理解项目，建议顺序是：

```text
fintech-platform-architecture
-> payment-run-lifecycle
-> payment-provider-boundary-flow
-> reconciliation-and-evidence-flow
```

这些图是教学抽象，不代表真实支付通道、真实银行清结算网络、真实监管报送或生产级合规架构。
