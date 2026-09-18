"""Package the reviewed, frozen research snapshot into one report's content.

The Markdown is the inspectable report source; the local Data app renders the
same sections. Narrative decisions are intentionally bound to this snapshot.
"""

from pathlib import Path
import argparse
import json

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
EXPECTED_SNAPSHOT = "553358fb9ccbc3db1b27dfed39efea5da0748a3fd94390d378714a36cde2c9ac"


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(cell(v) for v in headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-project", type=Path, help="Update an existing local Data report's generated src/data.json; preserve its artifact ID")
    parser.add_argument("--complete", action="store_true", help="Mark the reviewed local rendering ready after verification")
    arguments = parser.parse_args()
    result = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    if result["provenance"]["selected_snapshot_sha256"] != EXPECTED_SNAPSHOT:
        raise ValueError("Report interpretations require review for a changed dataset; do not reuse this narrative silently")
    levels = json.loads((OUT / "selected_observations.json").read_text(encoding="utf-8"))
    scores = json.loads((OUT / "rolling_scores.json").read_text(encoding="utf-8"))
    import csv
    with (OUT / "changes.csv").open(encoding="utf-8") as handle:
        changes = list(csv.DictReader(handle))
    changes = [{**row, "sofr_percent": float(row["sofr_percent"]), "change_bp": float(row["change_bp"]), "absolute_change_bp": float(row["absolute_change_bp"])} for row in changes]
    sections = []
    def add(identifier, title, body, query_ids):
        sections.append({"id": identifier, "title": title, "body": f"## {title}\n\n{body}", "queryIds": query_ids})
    title = "SOFR 变化异常研究：ties 与小 MAD 已影响读数，生产窗口仍缺证据"
    summary = """本次使用项目已验证的 61 个 SOFR 观测，得到 60 个连续观测变化；只有 prior-20-change 方法有 40 个可评估日期。60/120/252-window 均没有完整评估样本，无法据此选定生产窗口。

实测显示 robust Z 在 MAD=0.5 bp 的窗口里，将两个 −2 bp 变化放大到 −3.3725；percentile 的 ties 也很重要，最新 −2 bp 的 strict / midrank / weak 分别为 65% / 77.5% / 90%。

建议下一轮优先研究 **绝对变化 midrank percentile + signed bp magnitude + tie bracket**，暂不采用 robust Z 作为唯一分类基础。仍需通过既有 approved ingestion/processing 路径扩展历史，并完成多窗口与低变动区间研究，才足以决定 anomaly_state 的生产规则。"""
    add("dataset", "1. Dataset", f"""**实测事实。** 研究只读 `{result['provenance']['database']}` 的 validated processed SOFR，经既有 `sofr_history` 选择：同日若已保存 revised `r` 则优先，否则选择 `original`，并要求 approved processing version 与 exact raw lineage 匹配。61 个 raw 与 61 个 processed SOFR 均是 `frbny_sofr_revision:original`；没有 duplicate dates、revised vintage 或 null raw value。逐项核对 processed ID hash、raw/processed 数值与 lineage，共 61 项一致。

范围：2026-06-22 至 2026-09-16。原生单位为 percent per annum；`3.62` 表示 3.62%。date 是 FRBNY effective/reference date，而不是 publication date。`1D` 在本研究中指 **连续有效 SOFR 观测之间的变化**；60 个变化中，间隔 1/3/4 个日历日分别为 48/10/2 次。没有填补周末、假日、缺失或未返回日期，也没有假定 weekday calendar 可证明数据完整。

`change_1obs_bp = 100 × (SOFR_t − SOFR_previous_valid)`。先以 `Decimal(str(value))` 相减再转 bp，避免浮点微差制造 ties 或极小 MAD；实测所有变化都是整数 bp，未进行人为整数舍入。

**时间限制。** 61 个 publication timestamp 均未知；raw retrieval 时间为 2026-09-17 18:50:02.914188 至 19:16:36.204990 UTC。研究是当前保存 original vintage 的回顾性 snapshot；只能保证 score baseline 在经济日期上 prior-only，不能证明这些 backfilled values 在每个历史 decision timestamp 已为系统所知。canonical research input 是此次冻结的 selected processed-ID list；它不是历史 availability-time replay。

分析运行于 `{result['provenance']['executed_at']}`，analysis version `{result['provenance']['analysis_version']}`。commit、源代码 hash、script hash、selected-snapshot hash 保存在 `results.json`。snapshot hash：`{EXPECTED_SNAPSHOT}`。README 列出重跑命令与文件。

架构文档的 Phase 1.6C 段落保留当时“三个观测”的历史描述；1.6D 描述已 backfill，实际库为 61。未发现阻碍此次分析的 processing bug；没有改动冻结的 production 文件。""", ["levels", "changes"])
    qrows = []
    for probability in (.5, .75, .9, .95, .975, .99, .995):
        key = str(probability)
        qrows.append([f"{100*probability:g}%", f"{result['signed_distribution_bp']['quantiles'][key]:.3f}", f"{result['absolute_distribution_bp']['quantiles'][key]:.3f}", f"{60*(1-probability):.2f}"])
    frequencies = [[f"{r['change_bp']:+g}", r["count"], f"{r['percent']:.2f}%"] for r in result["frequency_bp"]]
    add("distribution", "2. SOFR change distribution", """**实测事实。** 60 个变化：min −5 bp，max +6 bp，mean +0.0167 bp，median 0 bp，sample standard deviation 2.1112 bp（ddof=1），unscaled MAD 1 bp。13/60（21.67%）为零，33/60（55%）在 ±1 bp 内，49/60（81.67%）在 ±2 bp 内。没有 |change|≥10 bp；±5 bp 各一次。绝对变化 mean 1.5833 bp、median 1 bp。

""" + table(["Quantile", "Signed change (bp)", "Absolute change (bp)", "Expected upper-tail sample count"], qrows) + "\n\n" + table(["Observed signed bp", "Count", "Share"], frequencies) + """

Quantiles 使用 `(n−1)p` 位置的线性插值；例如 99.5% 的 5.705 bp 不是实测交易步长。97.5/99/99.5% 的 upper-tail expected counts 只有 1.5/0.6/0.3；这些仅是顺序统计摘要，不能用来校准稳定尾概率。

signed moment skewness=0.3594、excess kurtosis=0.4540（未作小样本无偏修正）。有离散整数步长和少量 4–6 bp 变化，但这段短样本不能确立长期 fat-tail 分布或正式 volatility regime。月度 change std：六月 2.7142 bp（仅 6 个变化）、七月 2.4863、八月 1.8413、九月 1.2933（仅 11 个变化）；后期变动较低的描述可成立，不能据此认定结构性 regime change。""", ["changes", "frequency", "monthly"])
    add("standard", "3. Standard Z-score findings", """公式：`z_t = (delta_t − mean(prior N deltas)) / sample_std(prior N deltas)`；std 的 ddof=1。对当前变化 i，reference slice 严格为 `[i−N:i]`；current delta 不进入 baseline。

**实测事实（N=20）。** 40/40 可计算；std=0 有 0/40、0<std<1 bp 有 0/40，rolling std 范围 1.5424–3.0070 bp。Z-score 范围 −2.0747 至 +2.4085；|Z|≥2 为 2/40（5%），|Z|≥3 为 0/40。没有 ≤2 bp 的变化取得 |Z|≥2。绝对 score 的 median/90%/95% 分别为 0.5135/1.2998/1.7831；完整 score 分布保存在 results.json。

**实测敏感度诊断。** 对每个 prior window 临时去掉一个最大 |delta|，仅用于观察 denominator 影响，不构成另一条 production rule。原始 std 相对删去该输入后的 std 最高高出 19.71%。2026-08-21（+2 bp）：原始 std=1.6376、Z=1.2519；删去 prior +4 bp 后 std=1.3680、Z=1.6544。这个 score 差同时包含 mean 与 scale 的变化，不能全归因于 denominator。此前 +6 bp 仍在窗口的 7 月 22–29 日，原始 std 约 2.94–3.01 bp，较删去该点后约 2.66–2.74 bp 更宽。

**研究解释。** prior extremes 确实会扩宽 baseline，减少部分后续变化的相对显著程度；这是标准 Z 的定义特性，不能据此声称有已知异常被漏报。20-window 对较低变动期会适应，但只有一个可评估窗口，无法比较其速度与更长窗口。未观察到接近零 std，不能把 0/40 failure 外推到其他历史区间。Z 值不对应此处已验证的 normal tail probability。

60/120/252-window 各为 0 个 eligible dates；failure percentage 不适用，不能报告为 0% 或 100% scale failure。""", ["scores"])
    add("robust", "4. Robust Z / MAD findings", """公式：`robust_z = 0.6745 × (delta_t − median(prior N deltas)) / MAD`；MAD=`median(|x−median(x)|)`，不加 epsilon、不启用 fallback。

**实测事实（N=20）。** MAD=0 为 0/40（0%），因此 undefined robust Z 为 0/40（0%）。0<MAD<1 bp 为 4/40（10%），MAD≤1 bp 为 28/40（70%）；MAD 范围 0.5–2 bp。robust Z 范围 −3.3725 至 +2.698；|robust Z|≥2 为 7/40（17.5%），其中 3 次变化仅有 |delta|≤2 bp；|robust Z|≥3 为 2/40，两次都是 −2 bp。绝对 score 的 median/90%/95% 为 0.6745/2.0910/2.7317。

2026-08-12 和 2026-09-01 的 prior median 均为 +0.5 bp、MAD=0.5 bp；当前 −2 bp 相对中心的 −2.5 bp 偏差得到 −3.3725。2026-08-18 的 −1 bp 也得到 −2.0235（standard Z 仅 −0.8375）。本研究没有经过校准的经济真值标签，所以不能把这些称为统计意义上的 false positive；它们证明小 bp movement 可因小尺度而取得大 score。

**研究解释。** 数值计算在此样本中可运行，经济解释却对半 bp 的 MAD/median 台阶敏感。没有观察到 MAD=0 不代表 SOFR 长历史中不会出现；60/120/252-window 的 MAD=0/小 MAD/undefined frequency 全部未知。当前证据不支持把 robust Z 用作唯一 anomaly classifier，也不支持立即永久淘汰它。""", ["scores"])
    add("percentile", "5. Empirical percentile findings", """令 a=`abs(delta_t)`，prior magnitude 为 |x|；报告三种 percentile（当前变化不参与计数）：

- strict：`100 × count(|x|<a)/N`。
- weak：`100 × count(|x|≤a)/N`。
- midrank：`100 × (count(|x|<a)+0.5×count(|x|=a))/N`。

**实测事实（N=20）。** 40/40 可计算；三种 percentile 都不需要除以 volatility scale。弱/严格 percentile 的 gap 平均 24.375 percentage points，最大 45 pp；每个当前幅度在 prior window 中有 1–9 个 ties。最新 2026-09-16，3.64%→3.62%（−2 bp）：baseline 是 8 月 18 日至 9 月 15 日的 20 个 prior changes，13 个幅度小于 2 bp，5 个等于 2 bp，2 个大于 2 bp；strict=65%、midrank=77.5%、weak=90%。weak 的 90% 不能读作该变化“罕见到只有 10% 概率”。

40 个 eligible dates 中恰好 |delta|=1 bp 有 16 个；三种 convention 下 ≥90% 或 ≥95% 均为 0/16。weak≥90% 共 5/40（其中一个是最新 −2 bp），midrank≥90% 为 3/40，strict≥90% 为 2/40。≥95% 分别为 3/40、1/40、1/40；这些只用于比较 convention，不是生产阈值。

**研究解释。** 当前数据没有“1 bp 位于很高 percentile”的实测例子，但 0/16 不能排除长时期近零 baseline 的情况。ties 在实际读数中已造成实质差异。midrank 更适合作为中性描述；同时保留 strict/weak bracket 与 equality count，使研究者知道 percentile 的离散不确定性。20-window 每个 prior observation 占 5 pp，midrank 可出现 2.5 pp 台阶；percentile=100 仅说明当前幅度大于全部 prior inputs，不能衡量超出最大值多少，也不是经验证的概率。""", ["scores"])
    crows = [[r["flag"], str(r["value"]), r["n"], f"{r['mean_abs_bp']:.4f}", r["abs_at_least_3bp"], r["abs_at_least_5bp"]] for r in result["calendar_groups"]]
    add("calendar", "6. Calendar findings", """研究 flag 使用已知 calendar date：每月最后一个 Monday–Friday 为 month_end；其月份为 3/6/9/12 时也是 quarter_end，12 月时也是 year_end。该规则**忽略 holiday adjustment**，因为项目没有 authoritative business calendar。实际保存的三个边界为 6 月 30 日、7 月 31 日、8 月 31 日；未把 9 月 16 日当成 month-end。

around flag 为边界本身及相邻 ±1 个**实际保存的 SOFR observation**（不是 ±1 calendar day）；只对保存边界存在时计算。around flags 是 retrospective context，可能使用下一个边界后观测来标识范围；不参与任何 score/baseline，也不作为 point-in-time trading input。

""" + table(["Flag", "Value", "n changes", "Mean |delta| bp", "|delta|≥3 count", "|delta|≥5 count"], crows) + """

3/5 bp 是本研究的描述性分组，不是生产 materiality thresholds。month-end +6/+1/+3 bp；只有 3 个边界，季度末只有 1 个，year-end 没有任何样本。month-end 组 |delta|≥3 为 2/3，非 month-end 为 9/57；±1 观测 context 组为 2/9，外部组为 9/51。可观察到边界集中，但样本不足以确认长期 disproportion、估计稳定效应或建立 calendar adjustment。

+6 bp 的 6 月 30 日发生在 20-window warm-up 内，没有 anomaly score；7 月 31 日 +1 bp 的 Z/robust/midrank 为 0.4094/0.3373/32.5%，8 月 31 日 +3 bp 为 1.7315/2.0235/90%。没有删掉边界变化。项目未发现可用、可靠的 policy-event 数据集；FOMC/policy-event 分类明确 deferred，未从跳动本身推断事件。""", ["changes", "calendar", "scores"])
    add("materiality", "7. Rarity vs materiality", """**实测事实。** robust score 已将 −1/−2 bp movement 放大，ties 又使同一个 −2 bp 在不同 percentile convention 下跨越 65–90%。这证明一个压缩 score 无法独立表达幅度、稀有性和 reference-scale 特性。样本没有 +10/+15 bp，因此无法从这些数据判断多大才有经济 materiality。

**推荐设计选择。** 未来 evidence 至少保留 `change_1obs_bp`（signed magnitude）、`change_magnitude_percentile`、`reference_window_count`、strict/weak percentile 或 less/equal/greater counts，以及 baseline first/last date 和 exact input IDs。方向可由 signed bp 解释，异常稀有性仍基于绝对幅度，不预设上行比下行更异常。

生产 classification 很可能需要独立的 bp materiality 逻辑或同时展示 rarity 与 magnitude；本研究支持保留这一维度，但**无法校准其阈值**。罕见 SOFR movement 仅表示它偏离自身历史变化分布，不独立意味着资金危机、系统流动性压力、金融条件收紧、股票/债券方向或预期收益。""", ["scores"])
    event_text = "20-window 的最大标准化变化主要发生于 8 月；全样本幅度最大的 +6 bp（6 月 30 日）与 −5/+5 bp（7 月 9/13 日）处于 warm-up，不能补造 score。以下分别按 |Z|、|robust Z|、midrank percentile 排序，每项列出 20 个日期。score 相同时按 |bp| 降序再日期升序，仅用于 audit 排序。全部五种 score/tie convention 的 top20 CSV 与未排名全量 rolling_scores.csv 均保留。\n\n"
    for method, label in (("standard_z", "Standard Z"), ("robust_z", "Robust Z"), ("percentile_midrank", "Absolute-change midrank percentile")):
        rows = []
        for row in result["top20"][method]:
            flags = ", ".join(flag for flag in ("month_end", "quarter_end", "year_end", "around_month_end") if row[flag]) or "—"
            rows.append([row["date"], f"{row['sofr_percent']:.2f}", f"{row['previous_sofr_percent']:.2f}", f"{row['change_bp']:+g}", row["window"], f"{row[method]:.4f}", flags])
        event_text += f"### {label}\n\n" + table(["Date", "SOFR %", "Previous %", "Change bp", "Window", "Score / percentile %", "Calendar context"], rows) + "\n\n"
    add("events", "8. Historical examples", event_text, ["scores"])
    comparison = [
        ["Standard Z", 20, "40/40 eligible; zero std 0%", "std 1.542–3.007 bp; |Z|≥2 2/40", "largest-prior deletion changes std up to 19.71%", "works here; constant scale undefined", "≤2bp |Z|≥2: 0/40", "deviation from rolling mean in sample std units", "outlier scale widening; near-zero scale untested"],
        ["Robust Z / MAD", 20, "40/40; MAD=0 0%", "MAD 0.5–2; small MAD 10%", "less direct squared-tail leverage; discrete center/scale", "MAD=0 remains undefined", "≤2bp |robust|≥2: 3/40; ≥3: 2/40", "median deviation in MAD units", "small moves receive large scores; zero MAD untested"],
        ["Abs percentile", 20, "40/40", "5pp prior weight; ties gap mean24.375pp", "each outlier changes rank by at most 5pp, no scale denominator", "computable even with all-zero prior; magnitude still required", "1bp ≥90: 0/16; 2bp weak≥90: 1/40", "fraction of prior magnitudes less/equal; not probability", "ties, short-window resolution, saturation at100"],
    ]
    for method in ("Standard Z", "Robust Z / MAD", "Abs percentile"):
        for window in (60, 120, 252):
            comparison.append([method, window, "0 eligible; not evaluated", "unmeasured", "unmeasured", "unmeasured", "unmeasured", "formula defined, no empirical verdict", "insufficient stored history"])
    add("comparison", "9. Method comparison", table(["Method", "Window", "Availability", "Stability", "Outlier sensitivity", "Zero-heavy handling", "Small-move escalation", "Interpretability", "Major failure mode"], comparison) + """

“Small-move escalation” 对应用户所问的 small-move false-alarm 风险；没有外部 ground-truth 标签，不能宣称真实 false-alarm rate。

**Window 机制与可测边界。** N 长度 baseline 每次仅替换一个 prior change，历史极端持续至它离开 N 个 prior slots；20-window 的 sd/MAD 已随历史改变。更长窗口单条 rank 权重理论为 1.667/0.833/0.397 pp（N=60/120/252），通常替换信息较慢，但是否更稳定、是否横跨不兼容的政策环境在本数据中未测。不能按公式上的平滑性选窗口。

首个可评分日期至少需 N+2 个 levels：20/60/120/252 分别是 22/62/122/254。要有 20 个 eligible score，需要 N+20 个 changes，即 N+21 个 levels：41/81/141/273；这只是 arithmetic availability，不是证据质量门槛。40 个高度重叠的20-window score不等于40个独立实验，且仍没有年末和大型政策变化覆盖。""", ["scores", "windows"])
    add("recommendation", "10. Recommended methodology for Phase 2.1B", """**A — Best evidence measure（条件性推荐）。** 优先保留绝对变化的 midrank empirical percentile 与 signed `change_1obs_bp`，外加 strict/weak bracket。它直接回答相对于此前幅度的排序问题；实际 ties 大幅改变读数，保留 bracket 比单独给出 weak percentile 更透明。标准 Z 可保留作 research diagnostic；robust Z 的小-scale 放大已出现。

**B — Best classification foundation。** midrank percentile + 明确独立的 magnitude evidence 是更值得下一轮评估的基础；目前不足以冻结 `normal/unusual` mapping。无需把所有计算结果都成为生产 signal；保留字段是证据设计，生产分类仍需有经济问题与检验依据。

**C — Materiality。** 需要保留独立绝对 bp 概念；是否作为 hard gate、何种阈值或是否采用分层提示，尚无足够证据。不能用本样本缺少 ≥10 bp 来制造 cutoff。

**D — Window。** 20-window 可以作为这次探索用的 baseline；不能因为它是唯一可算窗口就把它选为 v1。60/120/252 的比较尚未发生，当前没有 defensible production winner 或窗口范围。下一轮需要经既有 ingestion → validation → processing 路径扩展历史，覆盖零变动期、较高变动期、多个月/季度与 year-end，然后比较窗口，不在本任务里直接下载另一个数据集。

**E — Failure handling。** 缺少 N 个 prior valid changes时 score=null并保留原因；std=0或MAD=0时对应score=null，不默认为 normal、不加epsilon；可计算的 percentile可以另行保留，但不是静默fallback classifier。必须区分warm-up、undefined scale、unknown availability和calendar coverage不足。保留实际previous date/calendar gap，不做插值或年度化。

**生产实施决定：需要更多研究。** Phase 2.1A schema可承载这些structured evidence与可空状态，但本次没有production definition、threshold、signal observation或actual generator。""", ["scores", "windows"])
    add("questions", "11. Unresolved questions", """1. 扩展同一 approved source历史后，MAD=0在各窗口的实际发生率是多少？不同政策环境/低变动期中小MAD是否仍放大1–2bp？
2. 60/120/252-window的响应、baseline contamination、rank稳定性和实际事件可读性如何？20-window percentile过粗这一机制已知，但没有经验比较证明60“足够”。
3. 大型bp movement与政策利率变更如何区别？当前可靠policy-event数据缺失，不能从SOFR变化反推FOMC。
4. 何种absolute materiality规则有经济依据，如何处理超过baseline最大值的1bp和15bp都排在100%的饱和？需要外部经济/事件证据，非仅数学排名。
5. Calendar需何种authoritative holiday/business calendar？当前只有3个月末、1个季度末、0个年末，不支持调整、排除或阈值学习。
6. 后续生产是否仅做current monitoring，还是需要历史availability-time replay？后者需补足explicit publication/vintage availability；当前backfill不能还原当时information set。
7. production evidence quality如何反映有效prior count、scale状态、可用时间与覆盖？本次仅给经验结果，不创建sufficient/limited/insufficient门槛。

下一步的具体研究输入是**既有FRBNY路径内的更长validated history**。本任务到研究报告为止；Phase 2.1B production实施尚未开始。""", ["levels", "windows"])
    report = "# " + title + "\n\n" + summary + "\n\n" + "\n\n".join(section["body"] for section in sections)
    (OUT / "report.md").write_text(report + "\n", encoding="utf-8")
    source = {
        "label": "Project validated SOFR snapshot (FRBNY)", "provider": "local DuckDB / FRBNY",
        "tables": ["processed_observations", "processed_observation_inputs", "raw_observations"],
        "executedAt": result["provenance"]["executed_at"],
        "evidenceFlow": [
            {"title": "Read-only source", "detail": "config/settings.toml database; sofr_history selection of approved processed SOFR with exact saved raw vintage."},
            {"title": "Transformation", "detail": "Decimal source percent differences times100=bp; prior-only N deltas; sample std ddof1; unscaled MAD; empirical less/equal tie counts. notebooks/sofr_daily_change_anomaly/analyze.py."},
            {"title": "Frozen inputs", "detail": f"61 selected levels,60 deltas;2026-06-22..2026-09-16;selected snapshot SHA256={EXPECTED_SNAPSHOT}"},
        ],
        "caveats": ["All historical publication timestamps unknown; backfilled2026-09-17; not historical availability-time replay.", "Only20-window eligible;60/120/252 unmeasured.", "Weekday-only boundary context ignores holidays; no FOMC dataset."]
    }
    queries = {
        "levels": {"rows": levels, "source": source}, "changes": {"rows": changes, "source": source},
        "scores": {"rows": scores, "source": source}, "frequency": {"rows": result["frequency_bp"], "source": source},
        "monthly": {"rows": result["monthly"], "source": source}, "calendar": {"rows": result["calendar_groups"], "source": source},
        "windows": {"rows": [{"window":w["window"],"eligible_dates":w["eligible_dates"]} for w in result["windows"]], "source": source},
    }
    snapshot = {"surface": "report", "title": title, "status": "reviewed", "buildStatus": "creating", "generatedAt": result["provenance"]["executed_at"], "filters": [], "queries": queries, "report": {"asOf": "2026-09-16"}, "researchSummary": summary, "researchSections": sections}
    if arguments.complete:
        snapshot["buildStatus"] = "complete"
    (OUT / "reviewed_report.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    if arguments.app_project:
        target = arguments.app_project.resolve() / "src" / "data.json"
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("surface") != "report" or not str(existing.get("id", "")).startswith("report:"):
            raise ValueError("Expected an existing prepared report with a stable artifact ID")
        rendered = {**snapshot, "id": existing["id"]}
        target.write_text(json.dumps(rendered, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Generated report.md and reviewed_report.json from the reviewed frozen snapshot.")


if __name__ == "__main__":
    main()
