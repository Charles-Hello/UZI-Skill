<div align="center">

# 游资（UZI）Skills

*"66 个投资大佬帮你看盘，巴菲特、赵老哥和股海贼王终于坐在了同一张桌子上。"*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.com/product/claude-code)
[![Dimensions](https://img.shields.io/badge/Dimensions-22-brightgreen)]()
[![Investors](https://img.shields.io/badge/Investors-66-orange)]()
[![Tests](https://img.shields.io/badge/Tests-685%20passed-brightgreen)]()

A 股 / 港股 / 美股 · 个股深度分析引擎 · **66 位评审团 × 9 大流派 × 22 维数据 × 22 种机构方法** · 全免费数据源 · 零 API key

[安装](#-安装) · [用法](#-用法) · [评审团](#-66-位评审团) · [报告](#-报告长什么样) · [数据源](#-数据源) · [项目结构](#-项目结构) · [FAQ](#-faq) · [更新日志](#-更新日志)

**中文** | [English](README_EN.md)

</div>

---

## 🚀 这是啥

输入一只股票，Claude 变成你的私人分析师：跑 22 个维度数据、调 22 种华尔街分析模型（DCF / Comps / LBO / IC Memo…）、让 66 个投资风格完全不同的大佬各自打分，最后吐出一份 Bloomberg 风格 HTML 报告。

```bash
/stock-deep-analyzer:analyze-stock 贵州茅台   # 完整分析（5-8min）
/stock-deep-analyzer:quick-scan 002217        # 30 秒速判
/stock-deep-analyzer:scan-trap 002217         # 杀猪盘排查
/stock-deep-analyzer:dcf 600519               # DCF 估值专项
```

分析完你会得到：
- **HTML 报告** — 自包含、离线可看、可分享
- **朋友圈竖图 + 微信群战报** — 直接发
- **一句话摘要** — 复制粘贴就能发群里

**全免费数据源，零 API key，A 股直接能跑。** 支持 A 股 / 港股 / 美股，输入代码或中文名均可。

---

## 📦 安装

不管你用什么 agent，都是**丢一句话过去就行**：

| 平台 | 操作 |
|---|---|
| **Claude Code** | `/plugin marketplace add wbh604/UZI-Skill` 然后 `/plugin install stock-deep-analyzer@uzi-skill` |
| **Codex** | "按 https://raw.githubusercontent.com/wbh604/UZI-Skill/main/.codex/INSTALL.md 装 UZI-Skill，分析 600519" |
| **Cursor** | `/add-plugin stock-deep-analyzer` |
| **Gemini CLI** | `gemini extensions install https://github.com/wbh604/UZI-Skill` |
| **Hermes** | `curl -fsSL https://raw.githubusercontent.com/wbh604/UZI-Skill/main/install-hermes.sh \| bash`（详见 [INSTALL-HERMES.md](INSTALL-HERMES.md)） |
| **OpenClaw / 龙虾** | "装 https://github.com/wbh604/UZI-Skill 这个股票分析技能" |
| **CLI 直用** | `git clone https://github.com/wbh604/UZI-Skill.git && cd UZI-Skill && pip install -r requirements.txt && python run.py 贵州茅台` |

> ⚠️ **用全名 `/stock-deep-analyzer:<cmd>`**：Claude Code 装 plugin 后所有命令带命名空间前缀，短名（`/analyze-stock`）在部分环境不会自动解析。Cursor / Gemini / Codex 同理。
>
> 📱 **不在电脑前？** 对 agent 说"用远程模式"，它会生成 Cloudflare 公网链接，手机扫码就能看报告。

---

## 🎯 用法

### 三档思考深度

| 档位 | 耗时 | 内容 |
|---|---|---|
| `lite` | 30-60s | 核心 7 维 + 10 位评委 |
| `medium`(默认) | 2-4min | 22 维 + 51 位评委 |
| `deep` | 15-20min | 全部 + Bull-Bear 辩论 + Segmental 分部模型 |

### 专项命令

| 命令 | 干嘛的 |
|---|---|
| `/stock-deep-analyzer:dcf 600519` | DCF 估值 · WACC + 5×5 敏感性表 |
| `/stock-deep-analyzer:comps 002273` | 同行对标 · PE/PB/ROE 对比 |
| `/stock-deep-analyzer:lbo 600519` | LBO 测试 · PE 买方能赚多少 IRR |
| `/stock-deep-analyzer:initiate 002273` | 机构首次覆盖报告 |
| `/stock-deep-analyzer:ic-memo 002273` | 投委会备忘录 · 三情景回报 |
| `/stock-deep-analyzer:earnings 002273` | 财报解读 · beat/miss 检测 |
| `/stock-deep-analyzer:catalysts 002273` | 催化剂日历 · 未来 60 天 |
| `/stock-deep-analyzer:thesis 002273` | 投资逻辑追踪 · 5 支柱监控 |
| `/stock-deep-analyzer:screen 002273` | 5 套量化筛选 |
| `/stock-deep-analyzer:dd 002273` | 尽调清单 · 5 工作流 21 项 |
| `/stock-deep-analyzer:quick-scan 002273` | 30 秒速判 |
| `/stock-deep-analyzer:panel-only 600519` | 只看 66 评委投票 |
| `/stock-deep-analyzer:scan-trap 002273` | 杀猪盘排查 |
| `/stock-deep-analyzer:segmental-model 300308` | 分业务收入建模 · 3 情景 × 3 年 |
| `/stock-deep-analyzer:ai-readiness 002273` | AI 就绪度/卡位评估 |
| `/stock-deep-analyzer:earnings-preview 002273` | 财报前预览 · 一致预期 + 三情景 |
| `/stock-deep-analyzer:model-update 002273` | 新财报增量更新模型 |
| `/stock-deep-analyzer:returns` | 组合收益归因 |
| `/stock-deep-analyzer:rebalance` | 逐持仓再平衡 |

### CLI 直跑（git clone 用户）

```bash
python run.py 600519.SH --depth lite --no-browser   # 30-60s 快速档
python run.py 300394.SZ --school I                  # 只看 Serenity 卡位视角（A-I 九派任选）
python run.py --versus 茅台 五粮液 002594.SZ         # 2-4 只票横向对决
python run.py --portfolio holdings.csv             # CSV 组合 · 加权评分 + 健康度
python run.py 600519.SH --output-dir /tmp/out      # SaaS 集成 · index.html + meta.json
python run.py 600519.SH --remote                   # 公网链接（手机看）
```

---

## 🎭 66 位评审团

**9 大流派 × 66 位投资大佬**，每人一套量化规则（242 条）+ 真实持仓/风格校验，各自对当前股票独立打分：

| 流派 | 代表 |
|---|---|
| A · 价值派 | 巴菲特 / 格雷厄姆 / 芒格 / 费雪 / 邓普顿 / 卡拉曼 |
| B · 成长派 | 林奇 / 木头姐 / Andreessen (a16z) / Gurley / Naval |
| C · 宏观派 | 索罗斯 / 达里奥 / Druckenmiller / Burry / Chanos |
| D · 技术派 | 利弗莫尔 / 米内尔维尼 / 达瓦斯 / 江恩 |
| E · 中国价投 | 段永平 / 张坤 / 冯柳 / 邓晓峰 / 张磊 (高瓴) |
| F · A股游资 | 赵老哥 / 孙哥 / 章盟主 / 葛卫东 / 炒股养家 + 股海贼王（从真实交割单蒸馏） |
| G · 量化 | Renaissance (Simons) / Ed Thorp / DE Shaw / AQR (Asness) |
| H · 科技领袖派 | 黄仁勋 / 马斯克 / Sam Altman / Saylor |
| I · Serenity | AI 供应链卡脖子/瓶颈猎手 |

- **风格加权**：自动识别股票风格（白马/高成长/周期/小盘投机…），按风格调评委权重
- **流派锁定**：`--school F` 只看游资视角 · 报告带 SCHOOL LOCK banner
- **Role-play**：deep 档 agent 按每位评委的知识库和风格真正扮演打分，成果合并进报告

---

## 📸 报告长什么样

报告包含：
- **综合评分 + 定调**（值得重仓 / 可以蹲 / 观望 / 谨慎 / 回避）
- **66 评委投票分布 + 审判席**
- **The Great Divide** — 最有说服力的多空大分歧
- **DCF 估值 · 5×5 敏感性热力图**
- **IC 投委会备忘录 · 三情景回报**
- **22 维深度卡**（基本面/估值/技术/资金/舆情…）
- **杀猪盘等级** + **离场信号** + **买入区间**

截图见 [docs/screenshots/](docs/screenshots/)（综合评分 / 多空分歧 / 聊天室 / DCF / IC memo / 朋友圈竖图）。

---

## 🔧 数据源

全免费公开数据源，多级 fallback 链保证稳定：

- **A 股**：akshare（东财 push2 / 雪球 / 腾讯 qt / 新浪 / 百度）+ baostock + 巨潮 cninfo 公告
- **港股**：akshare HK 接口 + AASTOCKS
- **美股**：yfinance + Yahoo Chart v8 直连 HTTP
- **财务三表**：利润表 / 现金流 / 资产负债表按报告期对齐（含货币资金 / 总负债 / 净资产，用于 DCF 净债桥）
- **搜索**：DuckDuckGo + 权威域白名单（央行/统计局/证监会）+ 东财妙想 API（可选，境外更稳）

> 💡 **MX_APIKEY（可选）**：境外/Codex 环境访问东财常被反爬，设 `MX_APIKEY` 走官方 API 更稳。见 `.env.example`。

---

## 📁 项目结构（v3.x）

```
run.py                                  # CLI 入口（python run.py <ticker>）
skills/deep-analysis/
├── SKILL.md                            # 深度分析工作流
├── personas/                           # 51 位评委 YAML 人格档案（12 flagship）
├── assets/                             # HTML 模板 / avatars
└── scripts/
    ├── run_real_test.py                # legacy stage1/stage2
    ├── fetch_*.py (22)                 # 数据采集 fetcher
    ├── compute_*.py                    # 机构建模（DCF/BCG/Porter）
    ├── assemble_report.py              # HTML 组装
    ├── lib/pipeline/                   # v3.0 管道式架构（默认路径）
    ├── lib/report/                     # 报告渲染
    ├── lib/investor_*.py               # 66 评委规则引擎
    └── tests/                          # 685 pytest
```

架构演进：v3.0 pipeline 默认主干 · v3.1/3.2 拆分瘦身 · `UZI_LEGACY=1` 强制回老路径。

---

## ❓ FAQ

**Q: 需要 API key 吗？** 不需要。全免费公开数据源。可选设 `MX_APIKEY` 提高境外稳定性。

**Q: 支持哪些市场？** A 股 / 港股 / 美股，输入代码（`600519.SH` / `00700.HK` / `AAPL`）或中文名（`贵州茅台`）均可。

**Q: 报告能分享吗？** 能。HTML 自包含可发文件；`--remote` 生成公网链接；附朋友圈竖图 + 战报。

**Q: 数据缺失怎么办？** 报告标注数据缺口 + 自检 gate，不会用假数据充数。agent 会主动兜底（Playwright / WebSearch / MX）。

**Q: 为什么我的股票全判"回避"？** 数据拉取不全时评委倾向保守。用 `--depth medium` 或设 `MX_APIKEY` 提高数据完整性。

**Q: Hermes 装不上？** `hermes skills install` 被上游 Skills Guard 误判，用一键脚本：`curl -fsSL https://raw.githubusercontent.com/wbh604/UZI-Skill/main/install-hermes.sh | bash`。

---

## 📋 更新日志（最近）

| 版本 | 主要变化 |
|---|---|
| **Unreleased** | 全球同行对比 + 数据完整性 hotfix · issue #87/#90 |
| **v3.9.2** | 流程与数据契约 hotfix · OCF 显式输出 · industry=None fallback（issue #82/#83） |
| **v3.9.1** | HTML 报告导航栏可折叠（issue #79） |
| **v3.9.0** | 新评委「股海贼王」· 首位从真实交割单蒸馏（65→66） |
| **v3.8.1** | skills 全面体检 · H/I 两组配套层补齐 |
| **v3.8.0** | Tier-1 五方法 + Serenity 严谨化 + 杜邦分解 |

完整演进见 [RELEASE-NOTES.md](RELEASE-NOTES.md)。

---

## 🤝 致谢

- [anthropics/financial-services-plugins](https://github.com/anthropics/financial-services-plugins) — 机构级分析方法论
- [obra/superpowers](https://github.com/obra/superpowers) — 多平台架构 / HARD-GATE / hooks 设计
- [akshare](https://github.com/akfamily/akshare) — A 股数据引擎
- [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) — Pydantic Signal 模式
- [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) — 多空辩论循环

---

## ⚠️ 免责声明

本报告由 AI 模型基于公开信息生成，数据可能存在滞后或误差。评分和建议均为模拟，不代表任何真实投资者的实际观点。**本报告不构成任何投资建议**，投资者应独立判断并承担投资风险。

[Star History](https://star-history.com/#wbh604/UZI-Skill&Date)
