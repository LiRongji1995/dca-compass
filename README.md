# dca-compass

个人美股定投（DCA）追踪工具：记录成本、观察估值和回撤，帮助坚持纪律。

**它只做提示，不做择时，也不自动交易。**

- 每日拉取股指 ETF、行业 ETF、龙头个股的日线行情，存在本地 SQLite
- 指标：涨跌幅、200 日均线偏离、52 周回撤、历史最大回撤、PE 及历史分位
- 定投记录：平均成本、累计投入、市值、收益率、XIRR
- 提示：定投日提醒；回撤或估值达到阈值时标记“可考虑加码”
- Streamlit 看板：总览 / 观察 / 单标的详情

## 安装

需要 [uv](https://docs.astral.sh/uv/)。uv 会自动下载合适的 Python（3.11+），不影响系统 Python。

```bash
# 安装 uv（任选一种）
brew install uv
pip install --user uv        # 装到 ~/Library/Python/3.x/bin，需要加到 PATH

# 安装依赖
uv sync
```

## 日常使用

```bash
uv run dca-update        # 更新行情和估值（首次约 30 秒，之后只补新交易日）
uv run dca-signals       # 终端查看定投提醒和加码提示
uv run dca-portfolio     # 终端查看持仓和收益
uv run dca-dashboard     # 启动看板，打开 http://127.0.0.1:8501
```

`dca-update` 的常用参数：

```bash
uv run dca-update --symbols SPY QQQ   # 只更新部分代码
uv run dca-update --full              # 全量重新拉取
```

建议每个交易日收盘后运行一次 `dca-update`（可以用 cron 或 launchd 定时）。估值分位依赖每天积累的 PE 快照，跑得越久越有意义。

看板数据缓存 10 分钟；更新数据后点侧边栏的“重新加载数据”立即刷新。

## 配置

所有配置都在 `config/` 下，改完下次运行即生效。

| 文件 | 内容 |
|---|---|
| `watchlist.yaml` | 追踪的标的：股指 ETF、行业 ETF、按行业分组的个股 |
| `settings.yaml` | 数据源与存储路径、估值回看年数、提示阈值、定投计划 |
| `transactions.csv` | 你的买入记录（不进 Git，见下文） |

### 买入记录

```bash
cp config/transactions.example.csv config/transactions.csv
```

然后用任意编辑器或 Excel 编辑 `config/transactions.csv`，每笔买入一行：

```csv
date,symbol,amount,price,shares,fee
2024-01-16,VTI,500.00,236.01,2.1186,0
2024-04-15,VTI,500.00,249.89,,0
```

- `amount` 是成交金额（不含手续费），总投入 = `amount` + `fee`
- `amount` 和 `shares` 可以只填一个，另一个按 `price` 推算
- 没有 `transactions.csv` 时，程序会使用示例文件，看板上会有提示
- 买入记录里出现、但不在观察列表里的代码，`dca-update` 也会一并拉取

### 提示阈值

```yaml
signals:
  drawdown_from_high: 0.15   # 距 52 周高点回撤 >= 15%
  valuation_percentile: 0.20 # PE 处于过去 N 年 20% 分位以下
  below_ma200: true          # 低于 200 日均线时高亮（仅作说明，不单独触发加码）
```

## 指标口径

- 最新价、200 日均线、52 周高点用**收盘价**，与行情网站一致
- 涨跌幅、历史最大回撤用**复权价**，包含分红
- 周 / 月 / 年涨跌幅按日历回推，取当天或之前最近一个交易日
- PE 分位 = 过去 N 年的 PE 快照中 ≤ 当前值的比例；快照少于 `min_samples` 时不计算
- XIRR 按实际天数 / 365 年化；刚开始定投时数值波动大属于正常

## 目录结构

```
config/                 配置与示例买入记录
data/                   SQLite 数据库（不进 Git）
src/dca_compass/
  providers/            数据源接口与 yfinance 实现
  storage.py            SQLite 读写
  update.py             dca-update：增量更新、重试
  metrics.py            行情与估值指标
  portfolio.py          成本、收益、XIRR
  signals.py            定投提醒、加码标记
  dashboard/            Streamlit 看板
tests/                  pytest
```

## 更换数据源

在 `src/dca_compass/providers/` 下新建一个类，实现 `PriceProvider` 的两个方法（`get_history`、`get_valuation`，见 `base.py`），在 `providers/__init__.py` 的 `get_provider` 中注册，然后修改 `settings.yaml` 的 `data.provider`。

## 开发

```bash
uv run pytest
```

## 已知限制

- 只记录买入，不支持卖出
- 分红按复权价计入涨跌幅，但不计入持仓市值
- 定投日遇周末顺延到周一，不处理美股节假日
- yfinance 只提供当前 PE，历史分位需要靠每日快照积累；多数 ETF 没有远期 PE
- yfinance 是非官方接口，偶尔会失败或限流；失败的代码会被列出，重跑即可
