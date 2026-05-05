# Ledger Basics

这是第一个 FinTech 代码实验：用 Python 实现一个最小内存版双分录账本。

配套文档：[../../docs/03-ledger-basics.md](../../docs/03-ledger-basics.md)

## 当前功能

- 创建账户。
- 提交交易。
- 校验每笔交易借方合计等于贷方合计。
- 使用 `Decimal` 处理金额。
- 查询账户余额。
- 计算试算平衡。
- 提供内存版 `Ledger` 和 SQLite 持久化版 `SQLiteLedger`。
- 使用 `idempotency_key` 防止重复请求重复入账。
- 使用 `request_fingerprint` 检查同一个幂等键下的请求参数一致性。

## 运行示例

```powershell
python .\labs\ledger-basics\demo.py
```

本仓库优先使用 Anaconda / conda 管理 Python 环境。当前本机默认 `python` 可能不可用；如果遇到 Windows Store alias 或访问问题，可以使用已验证的 Anaconda Python：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\ledger-basics\demo.py
```

运行 SQLite 持久化示例：

```powershell
& 'C:\App\Anaconda\python.exe' .\labs\ledger-basics\demo_sqlite.py
```

## 运行测试

```powershell
python -m pytest .\labs\ledger-basics
```

当前本机已验证命令：

```powershell
& 'C:\App\Anaconda\python.exe' -m pytest -p no:cacheprovider .\labs\ledger-basics
```

如果本机还没有安装 pytest，可以先只运行 `demo.py`。后续我们会再建立正式的 Python 虚拟环境和依赖文件。
