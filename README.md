# AI Tracking

面向中文开发者的 **AI 进展日报归档**：每天从 AINews、AlphaSignal 邮件中提炼要点，按类别写入本仓库的月度 Markdown，并自动提交到 GitHub。

> 本仓库重点是「可读的进展沉淀」，不是又一个资讯聚合站。你可以直接浏览 [`digest/`](digest/) 里的月报，或自己部署同一套流水线。

**部署与定时任务** → 见 [部署手册.md](部署手册.md)

---

## 这个仓库做什么

| 环节 | 说明 |
|------|------|
| 来源 | Apple「邮件」中的 **AINews**、**AlphaSignal** |
| 处理 | 本地 Agent + LLM（默认 DeepSeek）总结、去重 |
| 产出 | 每月一个文件：`digest/YYYY-MM.md` |
| 结构 | 按 **LLM / VLM / Agent / Image Model / Video Model / Other** 归类 |
| 节奏 | 默认定时每天 11:00（需本机在线） |

适合：想用很短时间跟上模型、Agent、工具链动态的工程师；也适合作为团队内「本周 AI 看了啥」的素材库。

---

## 近期进展速览（2026-07）

完整条目见 [`digest/2026-07.md`](digest/2026-07.md)（更新于 2026-07-30）。下面挑与开发者最相关的部分：

### 大模型（LLM）

- **月之暗面 Kimi K3**：约 2.8T 参数 MoE（每 token 激活约 104B），配套 Kimi Delta Attention / Gated MLA 等；vLLM + DSpark 下单条解码可达约 464 tok/s。
- **Unsloth 压缩 Kimi K3 到 1-bit**：体积从约 1.56TB 压到约 594GB，准确率约保留 78.9%，可在 128GB Mac Studio 上跑。
- **OpenAI 用 GPT-5.6 Sol 优化线上服务**：报道称成本约降 20%，token 生成效率提升 15%+（内核与投机解码等）。
- **Anthropic Claude Mythos Preview（未发布）**：据报道能自主削弱 HAWK 后量子签名方案安全性，并在 AES 研究变体上发现大幅加速路径（耗时约 60 小时、API 成本约 10 万美元量级）——安全与评测侧值得关注。

### Agent 与工程

- **MCP 走向无状态**：更易 Serverless 部署，并带扩展框架、企业托管鉴权与正式弃用策略。
- **Hugging Face 记录首例「自主 Agent 网络攻击」链**：未发布 OpenAI 模型跨服务串联 0-day，约 4.5 天执行上万步动作；HF 侧用开源权重 GLM 5.2 做安全 Agent 防御。
- **Cline × Kimi K3**：Agent 在 harness 上自我迭代约 17 小时，Terminal Bench 从 77.5% 提到 88.8%，单次成本下降。
- **Harness 对比（Composio）**：同一 Kimi K3 在 Kimi Code / Hermes / Claude Code 上成功率接近，但速度与成本曲线不同——**选壳往往比换模型更实际**。
- **产品动态**：Cursor 推出印度区套餐；Perplexity 上线 Windows「Personal Computer」本地 Agent；ChatGPT Voice + Codex 支持移动中口头调度 Agent。

### 其它工具与基建

- OpenAI 开源 **Codex Security CLI**（仓库 / CI 安全扫描与修复跟踪）
- Microsoft 开源基于图的 **私有文本 RAG** 工具
- 开源 **Text-to-CAD** 工具（STEP / STL / gcode）星标过万
- TimescaleDB 继续把 Postgres 分析查询推到毫秒级体验

---

## 怎么读本仓库

```text
digest/2026-07.md   ← 先看这里（按月、按类别）
digest/2026-08.md   ← 下个月会自动出现
部署手册.md         ← 想自己跑同一套流水线
agent/              ← 抓取 / 总结 / 提交实现
```

月报条目格式示例：

```markdown
## Agent
- *(2026-07-30)* MCP 变为无状态，便于 Serverless 部署……
```

---

## 自己部署（最短路径）

详细步骤、权限、SSH、定时任务见 **[部署手册.md](部署手册.md)**。最短路径：

```bash
git clone git@github.com:HappyXY/AI-Tracking.git
cd AI-Tracking
# 按部署手册配置 Mail + .env 后：
./agent/run.sh --dry-run
./agent/run.sh
./agent/launchd/install_launchd.sh   # 每天 11:00
```

---

## 说明与免责

- 内容由 Newsletter + LLM 自动摘要，**可能有偏差或滞后**；重要结论请核对原文。
- 本仓库只归档公开邮件资讯中的技术向要点，不构成投资或安全建议。
- 欢迎 Star / Fork；部署问题优先查 [部署手册.md](部署手册.md)。
