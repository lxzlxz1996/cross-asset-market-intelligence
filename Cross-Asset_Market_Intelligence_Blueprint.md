# Cross-Asset Market Intelligence & Portfolio Risk System

## 跨资产市场情报与投资风险决策系统：项目总蓝图

**文档用途：** 本文档是项目的长期方向、开发顺序和验收依据。每次新增功能前，先检查它是否服务于本蓝图；每完成一个阶段，更新状态与经验。

## 一页提醒：永远不要偏离这五件事

这个系统不是预测明天股票涨跌的机器，也不是为了堆砌指标或做一个漂亮 Dashboard。它要持续回答：

1. 市场正在发生什么？
2. 为什么会发生？
3. 哪些结构正在改变？
4. 风险在哪里积累？
5. Portfolio 应该如何调整风险？

核心链条：

> Data → Information → Signal → Regime → Risk → Portfolio Decision → Review

长期纪律：

- 每加入一个指标，必须说明它提供了什么独立信息。
- 同一风险若已被多个指标重复表达，应降权、合并或删除。
- 先建立可靠数据和统一定义，再做模型和界面。
- 相关性不等于领先性；所有信号最终都要经过样本外与滚动检验。
- 系统给出证据、风险与条件，不替人进行无解释的自动交易。
- 每次判断必须记录原因、失效条件、行动和结果，形成反馈闭环。

## 1. 项目使命与最终目标

建立一套个人可持续使用的跨资产投资研究基础设施，把宏观、利率、信用、流动性、仓位、股票、外汇、商品和组合风险连接起来，实现：

- 自动收集、清洗、储存和更新市场数据；
- 把原始数据转化为趋势、异常、速度和相对位置；
- 解释主要市场驱动因素并识别跨资产背离；
- 判断 Growth、Inflation、Policy、Liquidity 与 Risk Appetite 所处状态；
- 用历史数据验证信号，而不是凭故事选择指标；
- 将市场状态映射到 Portfolio Risk、情景和风险预算；
- 保存每次决策并用结果修正模型。

最终产物不是“预测机器”，而是：

> Market Observation + Investment Research + Risk Management + Portfolio Decision

## 2. 系统主架构

1. Data Layer：采集、清洗、频率对齐、版本与缺失值管理。
2. Market Engines：Macro、Rates、Credit、Liquidity、Equity、Volatility、Positioning、FX、Commodity。
3. Signal Engine：变化率、趋势、Z-score、percentile、momentum、breakout 与异常检测。
4. Cross-Asset Engine：比较不同市场是否讲同一个故事并发现 divergence。
5. Regime Engine：识别宏观、流动性、信用与政策环境。
6. Research Engine：Event Study、Backtest、样本外与 walk-forward 检验。
7. Factor Engine：相关性、聚类与 PCA，压缩重复信息。
8. Risk & Portfolio Engine：风险暴露、贡献、压力测试和组合行动。
9. Decision & Review：Dashboard、Alerts、Decision Journal、Performance Attribution 与反馈。

## 3. 功能与指标总清单

### 3.1 Data Foundation

每个指标必须有统一的数据字典字段：indicator_id、name、category、source、frequency、unit、calculation、higher_means、interpretation、release_lag、start_date、update_status。

数据管道必须处理：API 获取、时间戳、交易日历、频率转换、缺失值、修订值、异常值、缓存、失败重试、日志和质量检查。

### 3.2 Rates Engine

- 3M、2Y、5Y、10Y、30Y Treasury；2s10s、3m10y、5s30s；
- Real Yield、Term Premium；
- Fed Funds Futures、SOFR Futures 与市场隐含政策路径。

目标：解释利率变化来自政策预期、实际利率、通胀预期还是期限溢价。

### 3.3 Inflation Engine

- CPI、Core CPI、PCE、Core PCE；
- 5Y/10Y Breakeven、5Y5Y Forward；
- Wage Growth、Commodity Inflation。

目标：区分已实现通胀、通胀趋势和市场预期。

### 3.4 Growth Engine

- ISM Manufacturing/Services、PMI；
- Initial Claims、NFP、Unemployment；
- Retail Sales、Industrial Production、Housing、Consumer Confidence；
- Leading Indicators、SLOOS。

目标：判断增长加速或减速，并观察信贷供给向投资、就业与增长的传导。

### 3.5 Credit Engine

- IG OAS、HY OAS、BB/B/CCC spreads；
- HY−IG、CCC−BB；
- CDS indices、default rate、distressed debt ratio。

目标：同时观察 level、direction、speed、percentile 和结构性恶化。

### 3.6 Liquidity Engine

- SOFR、Repo、Bank Reserves、TGA、ON RRP；
- Fed Balance Sheet、Standing Repo usage、银行融资压力；
- NFCI、OFR Financial Stress Index。

目标：识别系统流动性、货币市场融资和综合金融条件，而不是把 Fed balance sheet 等同于流动性。

### 3.7 Equity & Earnings Engine

- Price：SPX、Nasdaq、Russell 2000、Dow；
- Breadth：A/D、50DMA/200DMA 上方比例、新高/新低、等权/市值权重；
- Leadership：行业相对强弱、Cyclical/Defensive、Small/Large；
- Earnings：Forward EPS、EPS/Revenue growth、revision、margin、surprise、guidance；
- Valuation：Forward P/E、CAPE、earnings yield、ERP、P/S、EV/EBITDA。

目标：拆分价格上涨来自盈利、估值扩张还是分红，并识别指数与内部结构背离。

### 3.8 Volatility & Options Engine

- VIX、MOVE、VIX term structure；
- Put/Call、SKEW、IV、RV、IV−RV；
- Open Interest、Gamma Exposure。

目标：识别显性波动、尾部保护需求、期限结构和潜在 dealer positioning 风险。

### 3.9 Positioning & Flow Engine

- CFTC Dealer、Asset Manager、Leveraged Funds；
- Futures OI、ETF/Fund Flow、options positioning；
- Short Interest、Margin Debt。

目标：用 Price + Position + Flow 识别 crowded trade；不把单一仓位机械解释为方向观点。

### 3.10 FX & Commodity Engine

- FX：DXY、EURUSD、USDJPY、USDCNH、AUDUSD；
- Commodity：Copper、Oil、Gold、Natural Gas、Industrial Metals；
- 辅助比率：Copper/Gold。

目标：观察政策分化、美元融资条件、增长、通胀与避险需求；商品信号只作 confirmation。

### 3.11 Macro Surprise & Event Engine

每次发布保存：Consensus、Actual、Previous、Revision、Surprise，以及事件前后 30 分钟、1 日和 5 日的 Rates、Equity、USD 反应。

覆盖 CPI、PPI、NFP、FOMC、央行讲话、Treasury auction、ECB、BoJ 与重要 earnings。

目标：研究市场交易的 Actual − Expectation，并建立可复用的事件研究库。

### 3.12 Signal、Divergence 与 Regime

每个指标统一输出：Current、1D/5D/20D change、Z-score、rolling percentile、trend、momentum、volatility、signal、confidence、data freshness。

优先识别：Equity↑/Credit↓、Equity↑/Breadth↓、Equity↑/VIX↑、DXY↑+MOVE↑+HY Spread↑。

基础 Regime：Goldilocks、Reflation、Stagflation、Deflationary Slowdown；成熟后加入 Liquidity、Credit 与 Policy 维度。

### 3.13 Risk、Portfolio、Backtest 与 Execution

- Risk：volatility、beta、VaR、CVaR、max drawdown、correlation、duration、convexity、credit beta、FX/factor exposure、risk contribution；
- Portfolio：risk budgeting、volatility targeting、scenario allocation、stress testing；
- Backtest：forward return、hit rate、Sharpe、drawdown、confidence interval、regime split、out-of-sample、walk-forward；
- Execution：bid-ask、slippage、market impact、turnover、rebalance frequency、net return。

目标：从“市场有风险”推进到“我的组合风险来自哪里、该减少或增加什么暴露”。

### 3.14 Dashboard、Alerts 与 Decision Journal

页面：Home、Macro、Rates、Credit、Liquidity、Equity、Earnings、Volatility、Positioning、FX、Commodities、Regime、Signals、Portfolio、Risk、Backtest、Journal。

首页只展示：Market State、Regime、Risk Level、Major Divergences、Top Drivers、Upcoming Events、Data Health。

每次重大判断保存：Date、Regime、各资产观点、证据、行动、风险、invalidation condition、outcome、review。

## 4. 第一版优先范围

V1 核心市场指标：2Y、10Y、2s10s、IG OAS、HY OAS、SOFR、MOVE、VIX、SPX。

首批八个增强指标：Term Premium、Breakeven Inflation、Fed/SOFR Futures、SLOOS、Equity Breadth、Earnings Revisions、VIX Term Structure、CFTC Positioning。

V1 的唯一业务目标：每天用 5 分钟理解核心市场状态、变化方向和最重要的异常。

## 5. 开发路线与完成标准

### Phase 0 — Architecture

做什么：确定项目目录、数据字典、数据库 schema、命名规范、数据源、更新时间和质量规则。

目标：建立可靠且可扩展的地基。

完成标准：核心指标均有定义；数据库可储存 raw/clean/signal 数据；目录和配置可运行；数据质量规则有测试。

### Phase 1 — Market Dashboard MVP

做什么：接入 Rates + Credit + Liquidity + Equity 核心指标，并建立每日更新流程。

目标：每天 5 分钟理解市场。

完成标准：九个 V1 指标自动更新；显示 current、1D/5D/20D change；失败有提示；首页可用。

### Phase 2 — Signal Engine

做什么：统一计算 Z-score、percentile、trend、momentum 与 signal。

目标：从看数字升级为看状态与异常。

完成标准：所有核心指标使用同一输出 schema；阈值可配置；每个 signal 可追溯到原始数据。

### Phase 3 — Cross-Asset Engine

做什么：建立资产间关系与 divergence rules。

目标：自动识别不同市场没有讲同一个故事的时刻。

完成标准：至少四类背离可自动识别、分级、解释并显示历史案例。

### Phase 4 — Macro & Regime Engine

做什么：加入 Growth、Inflation、Fed pricing 和 surprise 数据。

目标：识别当前经济与政策环境。

完成标准：输出 regime、主要证据、confidence 和改变 regime 的条件。

### Phase 5 — Positioning & Flow

做什么：接入 CFTC、futures OI、ETF flow 和 options 数据。

目标：识别仓位拥挤与潜在 unwind 风险。

完成标准：能够展示 price/position/flow 的联合判断，并避免把对冲仓位误判为方向观点。

### Phase 6 — Research & Backtest

做什么：建立事件研究、信号回测、样本外和 walk-forward 框架。

目标：验证哪些指标领先、确认或无效。

完成标准：每个保留信号都有假设、测试、成本前后结果、稳定性和适用 regime；无效指标被删除或降级。

### Phase 7 — Factor Model

做什么：用 correlation、clustering、PCA 处理指标重复。

目标：形成 Growth、Inflation、Rates、Liquidity、Credit、Risk Appetite、Positioning 等独立因子。

完成标准：解释指标归属与因子稳定性；避免重复计算同一风险。

### Phase 8 — Portfolio & Risk

做什么：导入持仓，计算风险暴露、risk contribution、VaR/CVaR、drawdown 和 stress scenarios。

目标：将市场判断映射到用户自己的组合风险。

完成标准：组合级与持仓级风险可追溯；主要风险来源和情景损失可解释。

### Phase 9 — Decision System

做什么：把 Regime + Signals + Risk 转化为有条件的 portfolio response。

目标：形成一致、透明、可复盘的 investment process。

完成标准：每条建议含证据、幅度、风险、失效条件和人工确认；Journal 自动记录。

### Phase 10 — Execution & Feedback

做什么：加入交易成本、滑点、冲击、再平衡和 performance attribution。

目标：形成 Signal → Decision → Outcome → Review 的闭环。

完成标准：报告 gross/net performance、成本和 attribution；模型可依据复盘结果修订并保留版本。

## 6. 版本成熟度

| 版本 | 系统能力 |
|---|---|
| V1 | Market Dashboard |
| V2 | Market Monitoring System |
| V3 | Cross-Asset Intelligence |
| V4 | Regime Model |
| V5 | Research System |
| V6 | Factor Model |
| V7 | Portfolio Risk System |
| V8 | Decision System |
| V9 | Execution System |
| V10 | Adaptive Investment System |

V1–V4：观察市场；V5–V7：研究市场；V8–V10：管理资金。

## 7. 建议技术栈与数据源

技术栈：Python、pandas、numpy、scipy、statsmodels、scikit-learn、DuckDB、Plotly、Streamlit、Jupyter、PyCharm、Git/GitHub。

优先数据源：FRED、Federal Reserve、US Treasury、CFTC、可靠公共市场数据；Bloomberg 作为后期增强。

## 8. 当前行动清单

- [ ] 完成 Market Data Dictionary。
- [ ] 确定 V1 九个指标的唯一来源、代码、单位与频率。
- [ ] 设计 raw、clean、features、signals 四层数据库表。
- [ ] 创建项目目录、配置文件、日志与测试结构。
- [ ] 写第一个可重复运行的数据更新 pipeline。
- [ ] 完成 V1 首页草图和验收样例。
- [ ] 在 Phase 0 验收前不扩展到复杂模型。

## 9. 每次开发前的检查问题

1. 这个功能解决哪一个核心问题？
2. 它提供什么现有模块没有的独立信息？
3. 数据是否可靠、及时、可复现并记录修订？
4. 输出是否可解释、可追溯、可测试？
5. 完成标准是什么？
6. 它是否让系统更接近 Portfolio Decision，而不只是增加图表？

## 10. 项目状态记录

当前阶段：Phase 1.5C — Graphical Treasury Dashboard Vertical Slice（完成）

当前重点：完成 Treasury 三项指标的 local/read-only Streamlit dashboard vertical slice

下一里程碑：TBD；需要明确授权后再定义，当前不得扩展其他 Phase 1 功能

Phase 0、Phase 1.1、Phase 1.2、Phase 1.3A、Phase 1.3B、Phase 1.4A、Phase 1.4B、Phase 1.5A、Phase 1.5B 与 Phase 1.5C 状态：完成。当前不得扩展其他 Phase 1 功能。Phase 2 — Signal Engine 明确不在当前范围内；不得实现 Z-score、percentile、trend、momentum、regime 或交易/组合逻辑。

最后更新：2026-09-17
