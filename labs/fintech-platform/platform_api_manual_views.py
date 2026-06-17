from __future__ import annotations

from collections.abc import Callable


PageShellRenderer = Callable[..., str]


def render_platform_manual_html(
    *,
    lang: str | None = None,
    page_shell: PageShellRenderer,
) -> str:
    normalized_lang = "cn" if normalize_manual_lang(lang) == "cn" else "en"
    if normalized_lang == "cn":
        title = "平台用户手册"
        subtitle = "面向使用者的 FinTech 学习平台功能、流程和操作边界说明。"
        content = _platform_manual_content_cn()
    else:
        title = "Platform User Manual"
        subtitle = "A workflow guide for using the FinTech learning platform console."
        content = _platform_manual_content_en()
    return page_shell(
        title=title,
        subtitle=subtitle,
        active_nav="manual",
        content_html=content,
        lang=normalized_lang,
    )


def normalize_manual_lang(lang: str | None) -> str:
    if lang is None:
        return "en"
    normalized = lang.strip().lower()
    return "cn" if normalized in {"cn", "zh", "zh-cn"} else "en"


def _platform_manual_content_en() -> str:
    return f"""
    <section class="platform-section" id="overview">
      <h2>What This Platform Does</h2>
      <p class="muted">
        This is an educational FinTech operations platform. It shows how onboarding,
        payment processing, risk review, ledger posting, audit trails, approvals,
        reconciliation, evidence exports, and operability checks connect in one
        small system.
      </p>
      <div class="manual-callout">
        Need the end-to-end picture first? Open the <a href="#flow-diagram">Detailed Event Flow</a>.
      </div>
    </section>

    <section class="platform-section" id="capabilities">
      <h2>Platform Capabilities</h2>
      <ul class="manual-list">
        <li>Payment run creation, idempotency, KYC/AML decisioning, risk decisioning, and ledger posting.</li>
        <li>Async payment runs, worker processing, failed-run retry requests, and maker-checker approvals.</li>
        <li>Operations reports, ledger reconciliation, settlement reconciliation, evidence packages, audit events, and investigation cases.</li>
      </ul>
    </section>

    <div class="manual-grid" id="workflows">
      <section class="platform-section" id="payment-workflow">
        <h2>Payment Workflow</h2>
        <ol class="manual-list">
          <li>Create a payment run through <code>POST /platform/payment-runs</code>.</li>
          <li>The platform evaluates KYC/AML context, creates a payment order, runs risk checks, and posts ledger entries when the run is completed.</li>
          <li>Use the console payment table to open a run detail page and inspect the platform result, ledger context, and audit timeline.</li>
        </ol>
      </section>

      <section class="platform-section" id="async-workflow">
        <h2>Async Workflow</h2>
        <ol class="manual-list">
          <li>Create an async run through <code>POST /platform/async-payment-runs</code>.</li>
          <li>Process queued work through the worker endpoint or demo flow.</li>
          <li>Failed async runs appear in the console with a retry approval request form.</li>
        </ol>
      </section>

      <section class="platform-section" id="approval-workflow">
        <h2>Approval Workflow</h2>
        <ol class="manual-list">
          <li>A retry request creates a pending operation approval.</li>
          <li>An authorized operator reviews the request, async status, and reason.</li>
          <li>The approval can be approved, rejected, cancelled, or expired. The detail page shows the lifecycle timeline.</li>
        </ol>
      </section>

      <section class="platform-section" id="reconciliation">
        <h2>Reconciliation</h2>
        <p class="muted">
          The console includes ledger reconciliation findings for teaching consistency
          checks between platform status, payment order status, ledger posting, and
          customer audit events. These checks are not a production settlement control.
        </p>
      </section>
    </div>

    <section class="platform-section" id="flow-diagram">
      <h2>Detailed Event Flow</h2>
      <p class="muted">A single order can be followed from request intake to final evidence and operability review.</p>
      {_platform_flow_diagram_en()}
    </section>

    <section class="platform-section" id="audit-cases">
      <h2>Audit And Cases</h2>
      <ul class="manual-list">
        <li>Every API and console view writes an access audit event.</li>
        <li>Access anomaly detection summarizes repeated denied access and suspicious platform API access patterns.</li>
        <li>Investigation cases can be opened from anomaly findings and moved through a simple investigation lifecycle.</li>
      </ul>
    </section>

    <section class="platform-section" id="evidence-packages">
      <h2>Evidence Packages</h2>
      <p class="muted">
        The platform demo can export educational evidence package files that collect
        platform reports, reconciliation outputs, approval records, audit records,
        and operability outputs for portfolio review.
      </p>
    </section>

    <section class="platform-section" id="operability">
      <h2>Operability</h2>
      <ul class="manual-list">
        <li><code>GET /platform/operability/readiness</code> checks whether the local stores are reachable.</li>
        <li><code>GET /platform/operability/metrics</code> returns teaching metrics for payment runs, async runs, access events, approvals, and cases.</li>
        <li><code>GET /platform/operability/test-matrix</code> lists the local verification commands used by this lab.</li>
      </ul>
    </section>

    <section class="platform-section" id="roles-permissions">
      <h2>Roles And Permissions</h2>
      <p class="muted">
        The lab uses a teaching identity model based on actor names and optional
        <code>x-actor-role</code> headers. It demonstrates permission checks and
        denied-access audit records; it is not enterprise IAM, SSO, or a legal
        authorization model.
      </p>
    </section>

    <section class="platform-section" id="local-commands">
      <h2>Local Commands</h2>
      <pre><code>python -m pytest -p no:cacheprovider labs/fintech-platform -q
python labs/fintech-platform/demo.py
python -m uvicorn platform_api_app:app --host 127.0.0.1 --port 8000</code></pre>
    </section>

    <section class="platform-section" id="boundary">
      <h2>Educational Boundary</h2>
      <p class="muted">
        This platform does not connect to real payment rails, external KYC vendors,
        live market data, legal retention systems, production settlement, or licensed
        compliance workflows. It is designed for engineering learning and portfolio
        demonstration only.
      </p>
    </section>
"""


def _platform_manual_content_cn() -> str:
    return f"""
    <section class="platform-section" id="overview">
      <h2>平台概览</h2>
      <p class="muted">
        这是一个教学版 FinTech 运营平台，用来观察开户、支付处理、风控复核、
        账本入账、审计轨迹、操作审批、对账、证据包和可运行性检查如何在一个小系统中串起来。
      </p>
      <div class="manual-callout">
        如果想先看一笔订单从发起到结束的完整路径，可以打开 <a href="#flow-diagram">详细流程图</a>。
      </div>
    </section>

    <section class="platform-section" id="capabilities">
      <h2>平台能力清单</h2>
      <ul class="manual-list">
        <li>创建 payment run，演示幂等、KYC/AML 决策、风控决策和账本入账。</li>
        <li>创建 async payment run，由 worker 后台处理，失败后通过 retry request 和 maker-checker approval 恢复。</li>
        <li>查看 operations report、ledger reconciliation、settlement reconciliation、evidence package、access audit 和 investigation case。</li>
      </ul>
    </section>

    <div class="manual-grid" id="workflows">
      <section class="platform-section" id="payment-workflow">
        <h2>支付流程</h2>
        <ol class="manual-list">
          <li>通过 <code>POST /platform/payment-runs</code> 创建支付运行。</li>
          <li>平台依次评估 KYC/AML、创建 payment order、执行 risk decision，完成后写入 ledger posting。</li>
          <li>在 Console 的 payment 表格打开详情页，查看 platform result、ledger context 和 audit timeline。</li>
        </ol>
      </section>

      <section class="platform-section" id="async-workflow">
        <h2>异步流程</h2>
        <ol class="manual-list">
          <li>通过 <code>POST /platform/async-payment-runs</code> 创建 async run。</li>
          <li>通过 worker endpoint 或 demo 触发后台处理。</li>
          <li>失败的 async run 会出现在 Console，并可提交 retry approval request。</li>
        </ol>
      </section>

      <section class="platform-section" id="approval-workflow">
        <h2>审批流程</h2>
        <ol class="manual-list">
          <li>retry request 会创建 pending operation approval。</li>
          <li>授权操作人员检查申请原因、async 状态和确认文本。</li>
          <li>approval 可以流转为 approved、rejected、cancelled 或 expired，详情页展示 lifecycle timeline。</li>
        </ol>
      </section>

      <section class="platform-section" id="reconciliation">
        <h2>对账视角</h2>
        <p class="muted">
          Console 会展示 ledger reconciliation findings，用于教学性检查 platform status、payment order status、
          ledger posting 和 customer audit events 是否互相吻合。它不是生产级清结算控制。
        </p>
      </section>
    </div>

    <section class="platform-section" id="flow-diagram">
      <h2>详细流程图</h2>
      <p class="muted">下面用一笔订单说明事件如何从请求进入平台，一直到最终审计、对账和证据输出。</p>
      {_platform_flow_diagram_cn()}
    </section>

    <section class="platform-section" id="audit-cases">
      <h2>审计与工单</h2>
      <ul class="manual-list">
        <li>每次 API 和 Console 查看都会写入 access audit event。</li>
        <li>access anomaly detection 会汇总重复拒绝访问和可疑 API 访问模式。</li>
        <li>investigation case 可以从 anomaly finding 打开，并按教学版生命周期推进。</li>
      </ul>
    </section>

    <section class="platform-section" id="evidence-packages">
      <h2>证据包</h2>
      <p class="muted">
        demo 可以导出教学版 evidence package，把平台报表、对账输出、审批记录、审计记录和 operability 输出组织到一起。
      </p>
    </section>

    <section class="platform-section" id="operability">
      <h2>可运行性</h2>
      <ul class="manual-list">
        <li><code>GET /platform/operability/readiness</code> 检查本地 store 是否可打开。</li>
        <li><code>GET /platform/operability/metrics</code> 返回 payment、async、access、approval 和 case 的教学版指标。</li>
        <li><code>GET /platform/operability/test-matrix</code> 返回本实验使用的本地验证命令。</li>
      </ul>
    </section>

    <section class="platform-section" id="roles-permissions">
      <h2>角色与权限</h2>
      <p class="muted">
        本实验使用基于 actor 名称和可选 <code>x-actor-role</code> header 的教学版 identity model。
        它用于演示权限校验和 denied access audit，不是企业 IAM、SSO 或法律授权模型。
      </p>
    </section>

    <section class="platform-section" id="local-commands">
      <h2>本地命令</h2>
      <pre><code>python -m pytest -p no:cacheprovider labs/fintech-platform -q
python labs/fintech-platform/demo.py
python -m uvicorn platform_api_app:app --host 127.0.0.1 --port 8000</code></pre>
    </section>

    <section class="platform-section" id="boundary">
      <h2>教学边界</h2>
      <p class="muted">
        该平台不连接真实支付通道、外部 KYC 供应商、实时市场数据、法律留存系统、生产级清结算或持牌合规流程。
        它只用于工程学习和作品集展示。
      </p>
    </section>
"""


def _platform_flow_diagram_en() -> str:
    return """
      <div class="flow-diagram" aria-label="Detailed order event flow">
        <div class="flow-step"><strong>1. Request intake</strong>Client submits a payment or async payment request with actor, order, customer, amount, and idempotency inputs.</div>
        <div class="flow-arrow">then</div>
        <div class="flow-step"><strong>2. API access audit</strong>The platform records who tried to create or view the resource and whether access was granted or denied.</div>
        <div class="flow-arrow">then</div>
        <div class="flow-step"><strong>3. Idempotency check</strong>The service compares run id and request fingerprint to replay the same request or reject conflicting input.</div>
        <div class="flow-arrow">then</div>
        <div class="flow-step"><strong>4. KYC/AML and risk decisions</strong>The orchestration layer evaluates onboarding context, creates the payment order, and applies risk rules.</div>
        <div class="flow-arrow">branch</div>
        <div class="flow-branch">
          <div class="flow-step"><strong>Approved</strong>Payment succeeds, ledger entries are posted, balances are captured, and customer audit events are appended.</div>
          <div class="flow-step flow-step-warning"><strong>Review required</strong>The order waits for a human review path before it can complete or fail.</div>
          <div class="flow-step flow-step-muted"><strong>Blocked or failed</strong>The payment order fails, ledger posting is skipped, and the reason remains visible in audit context.</div>
        </div>
        <div class="flow-arrow">then</div>
        <div class="flow-step"><strong>5. Async retry approval</strong>If an async run fails, retry starts as a pending operation approval. Approval execution can move the run back to accepted.</div>
        <div class="flow-arrow">then</div>
        <div class="flow-step"><strong>6. Reconciliation and evidence</strong>Ledger and settlement reconciliation reports inspect consistency. Evidence packages collect failed findings, approvals, denied access, and audit facts.</div>
        <div class="flow-arrow">finally</div>
        <div class="flow-step"><strong>7. Operability review</strong>Readiness, metrics, and the test matrix show whether local stores and verification commands are healthy.</div>
      </div>
"""


def _platform_flow_diagram_cn() -> str:
    return """
      <div class="flow-diagram" aria-label="订单端到端事件流程">
        <div class="flow-step"><strong>1. 请求进入平台</strong>客户端提交 payment 或 async payment request，包含 actor、order、customer、amount 和幂等相关输入。</div>
        <div class="flow-arrow">然后</div>
        <div class="flow-step"><strong>2. API 访问审计</strong>平台记录是谁尝试创建或查看资源，以及本次访问是 granted 还是 denied。</div>
        <div class="flow-arrow">然后</div>
        <div class="flow-step"><strong>3. 幂等检查</strong>service 使用 run id 和 request fingerprint 判断是重放同一请求，还是拒绝冲突输入。</div>
        <div class="flow-arrow">然后</div>
        <div class="flow-step"><strong>4. KYC/AML 与风控决策</strong>orchestration 层评估开户上下文，创建 payment order，并执行 risk rules。</div>
        <div class="flow-arrow">分支</div>
        <div class="flow-branch">
          <div class="flow-step"><strong>通过</strong>支付成功，写入 ledger entries，记录余额快照，并追加 customer audit events。</div>
          <div class="flow-step flow-step-warning"><strong>需要复核</strong>订单进入人工复核路径，之后才能完成或失败。</div>
          <div class="flow-step flow-step-muted"><strong>阻断或失败</strong>payment order 失败，不写入 ledger posting，失败原因保留在 audit context 中。</div>
        </div>
        <div class="flow-arrow">然后</div>
        <div class="flow-step"><strong>5. 异步 retry 审批</strong>如果 async run 失败，retry 会先创建 pending operation approval；审批通过后才把 run 放回 accepted。</div>
        <div class="flow-arrow">然后</div>
        <div class="flow-step"><strong>6. 对账与证据</strong>ledger 和 settlement reconciliation 检查一致性；evidence package 汇总失败 finding、审批记录、拒绝访问和审计事实。</div>
        <div class="flow-arrow">最后</div>
        <div class="flow-step"><strong>7. 可运行性检查</strong>readiness、metrics 和 test matrix 用来观察本地 store 和验证命令是否健康。</div>
      </div>
"""
