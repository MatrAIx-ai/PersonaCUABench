# Shopping Persona 实验计划（main code / rubric baseline）

本文档是 Shopping 六题的长期实验 decision record。后续每次运行都按日期新增记录，不覆盖旧结果。

## 2026-09-26：协议与 Persona 选择

### 当前决定

- 以 `main@4a1c0f2` 的 runner、prompt、task rubric 和 Haoming person-side judge **逻辑**为基线。
- Setting 1 采用 **4 个具名 Shopping persona + `none` control**。
- 不是“一道题只配一个 persona”；而是 **每个 persona 都运行全部 6 道题，每题再运行一次 `none`**。
- Persona simulator、原始 task judge、person-side experience judge 均固定使用 `GPT 5.6 Terra`。
- Execution backbone 使用计划中的 9 个模型；准确 provider、deployment/model ID 必须在开跑前写进当日 manifest，不能只记录展示名。
- Task completion、persona-mediated conversation/communication 和 persona satisfaction 分开报告，不合成一个总分。
- Setting 1 测量完整画像的 bundle effect；单维度归因留给 Setting 2。

这里的“按 main”指保持 main 的代码路径、prompts、rubrics、步数和 judge 规则；**不表示沿用 main 的默认模型名单**。main 当前默认是 Qwen 3.8 27B 负责 persona/CUA、GPT-5.5 负责原始 rubric judge，experience judge A/B 默认是 Terra 与 Claude Opus 4.8。本计划中的 Terra + 9 个 execution backbones 是明确记录的 experiment-level model overrides。把 experience judge A/B 都设为 Terra 后，报告的是同模型两次独立采样的 self-consistency，不是 Haoming 默认的 cross-model agreement。

### 规模

- 每个 execution backbone：`6 tasks × (4 personas + none) = 30 cells`。
- 9 个 execution backbone：`30 × 9 = 270 cells / replicate`。
- 如果以后明确加入第 5 个 persona：`6 × (5 + none) × 9 = 324 cells / replicate`，相对默认设计新增 54 个 cell。
- 环境失败后的精确重跑和 judge 重试不计入上述计划数。

## 1. 对应关系：一个 task 应该对应几个 persona？

### 会议记录能确认到什么

本地恢复的会议/分工记录位于 `artifacts/legacy/pre-standard-20260920/PersonaCUABench.md`。其中只写了：

> You can match the different persona with the specific category tasks.

该记录按 category 分配同学，并在 Ecommerce & Shopping 下列出 Defu 的六道题；`Persona` 一栏为空。它没有明确写“一道题只运行一个 persona”。记录中的 Google Drive 与 Zoom 录像链接目前不能通过现有工具读取，因此不能把录像中未实际看到的内容当作会议结论。

### main 的规则是明确的

`odyssey/README.md` 要求每位同学：

- 为自己负责的 tasks 定义 3–4 个明显不同的人群；
- 让不同 persona 以不同方式表达同一个 task；
- 运行 `Every persona × every task, plus the none control`。

`odyssey/run_grid.sh` 也用 persona 外层、task 内层的两层循环实现完整笛卡尔积。

因此本实验采用：

```text
每个 execution backbone
  ├── none × 6 tasks
  ├── shopping-budget-young-parent × 6 tasks
  ├── shopping-cautious-retiree × 6 tasks
  ├── shopping-busy-parent × 6 tasks
  └── shopping-premium-researcher × 6 tasks
```

不能采用“一人格一题”，因为那会把 persona 差异与 task 难度、目标网站可用性和 rubric 数量完全混在一起，无法判断差异究竟来自 persona 还是 task。

## 2. 六道 Shopping task

- `39255449e341`：Kobe 球鞋的即将发售、来源核验与 Nike 现货。
- `7cc602f23977`：Theory 绿色礼服、配套女鞋和 ooShirts 服务。
- `67ad95421a30`：Augusta 附近二手 Toyota 与车型参数比较。
- `63d68bb25e27`：Minneapolis–St. Paul 家庭车清单和 CryptPad Sheet。
- `4b9850333bdd`：英国啤酒、零食、流媒体和纸质信件订阅方案。
- `44f1e0211671`：Highlander、Fiat 500 和 Honda Civic 配件。

所有 persona 都跑所有 task。下面提到的“更敏感”只用于解释结果，不用于删除执行 cell。

## 3. Setting 1 的 Persona 选择

### 选择方法：从维度库构造，不冒充从 persona pool 抽样

main 的标准做法不是从一个现成 persona pool 中挑四个 ID，也不是把 persona 名字直接写进 prompt；它要求贡献者从 `odyssey/dimensions.json` 的 MatrAIx 1,290 维 schema 中选择一组维度，为自己的 task category 构造 3–4 个 group profiles，并由 `make_personas.py` 校验取值。

因此，本文把“从 persona 库选择”落实为：**从 MatrAIx 维度库构造四个 Shopping-specific profiles**。本计划选择 32 个共享维度，四个 persona 的 YAML 使用完全相同的字段集合，只改变值。这样可以控制 gross field count，但不同 value 的文本长度仍不同；正式 preview 要额外记录 renderer 实际保留的字段数，以及 profile/opening 的字符数或 token 数，不能宣称 prompt 严格等长。

本地 `MatrAIx-Persona-8B/persona/datasets/matraix-persona-dev-sample` 只有约 200 个 smoke persona，repo 文档明确说明它不是正式研究样本；production 1M pool 当前也未下载。因此这里的四个对象是 **schema-grounded Shopping archetypes**，不是从 production pool 抽出的四个自然人，也不能外推成对应人口群体的平均效果。如果未来团队要求真实 persona IDs 或 group-level 结论，应另开一个带日期的 protocol revision，下载 production pool、冻结 source/origin ID 和 profile hash，并在每个 group 内采样多个 persona。

### Task compatibility 约束

六道 task 的原文包含不可改写的个人事实：给儿子买生日鞋、为四口之家买车，以及为同一 household 的 Highlander、Fiat 500 和 Civic 选配件。由于每个 persona 必须运行全部六题，profile 不能与这些事实冲突。因此默认四组都设为家长/祖父母且具有合理的 household-car 背景；不会再使用 `Not a parent` 或 `Non-driver` 这类会迫使 simulator 在 persona 和 task 之间二选一的值。preview 若仍出现事实冲突，该 profile 不进入付费正式运行。

### 共享的 32 个 profile dimensions

身份、生活阶段与技术背景：

```text
age_bracket
socioeconomic_band
demo_parental_status
demo_driver_status
seniority
domain
role_function
primary_language
english_proficiency
tech_savviness
```

购物能力与任务兴趣：

```text
skill_budgeting
skill_research
ind_e_commerce
topic_cars
topic_fashion
topic_sports
```

消费与决策行为：

```text
lstyle_shopping_style
lstyle_frugality
lstyle_fashion_sense
lstyle_subscription_count
economic_motivation
pref_save_vs_spend
risk_tolerance
decision_style
trust_level
time_pressure
```

信息接收与可访问性：

```text
att_online_reviews
cog_detail_orientation
cog_patience
pref_detail_brief_vs_full
device_context
health_vision
```

### Persona A：`shopping-budget-young-parent`

定位：预算敏感、手机优先、数字原生的年轻家长；刚进入职场、日常开车，会快速比较价格，但耐心和细节需求较低，购买风险承受度较高。

```yaml
age_bracket: 25-34
socioeconomic_band: Lower-middle
demo_parental_status: Parent of minors
demo_driver_status: Daily driver
seniority: Entry
domain: Education
role_function: Operations
primary_language: English
english_proficiency: Native
tech_savviness: Digital native
skill_budgeting: Intermediate
skill_research: Intermediate
ind_e_commerce: Experienced
topic_cars: Interested
topic_fashion: Interested
topic_sports: Passionate
lstyle_shopping_style: Bargain hunter
lstyle_frugality: Frugal saver
lstyle_fashion_sense: Trend-follower
lstyle_subscription_count: 3-5
economic_motivation: Cost-sensitive
pref_save_vs_spend: Hard saver
risk_tolerance: Risk-tolerant
decision_style: Intuitive
trust_level: Trusting
time_pressure: Deadline
att_online_reviews: Enthusiast
cog_detail_orientation: Low
cog_patience: Low
pref_detail_brief_vs_full: Brief-leaning
device_context: Mobile, on-the-go
health_vision: Corrected
```

主要诊断价值：价格和促销敏感度、移动端可行动性、简洁表达、快速决策，以及低耐心下 agent 是否仍保留关键限制。

### Persona B：`shopping-cautious-retiree`

定位：技术谨慎、有视觉可访问需求、风险规避的退休购物者；偏好熟悉和稳妥的选择，希望答案简明但证据可信。

```yaml
age_bracket: 65-74
socioeconomic_band: Middle
demo_parental_status: Grandparent
demo_driver_status: Licensed, rarely drives
seniority: Retired
domain: Skilled Trades
role_function: Operations
primary_language: English
english_proficiency: Native
tech_savviness: Reluctant
skill_budgeting: Intermediate
skill_research: Beginner
ind_e_commerce: Some exposure
topic_cars: Neutral
topic_fashion: Indifferent
topic_sports: Neutral
lstyle_shopping_style: Minimalist
lstyle_frugality: Frugal saver
lstyle_fashion_sense: Classic
lstyle_subscription_count: 0-2
economic_motivation: Cost-sensitive
pref_save_vs_spend: Hard saver
risk_tolerance: Risk-averse
decision_style: Deliberative
trust_level: Skeptical
time_pressure: No rush
att_online_reviews: Skeptical
cog_detail_orientation: Moderate
cog_patience: High
pref_detail_brief_vs_full: Just the gist
device_context: Accessibility tool
health_vision: Low vision
```

主要诊断价值：可读性、页面与下一步是否真正可用、风险提示、对复杂标签页和长清单的处理，以及 agent 是否避免用技术术语压垮用户。

### Persona C：`shopping-busy-parent`

定位：有未成年子女、时间紧、日常开车的中等收入运营经理；以家庭实用性和整体价值为主，愿意核验但没有耐心做无限比较。

```yaml
age_bracket: 35-44
socioeconomic_band: Middle
demo_parental_status: Parent of minors
demo_driver_status: Daily driver
seniority: Manager
domain: Business & Management
role_function: Operations
primary_language: English
english_proficiency: Native
tech_savviness: Comfortable
skill_budgeting: Advanced
skill_research: Intermediate
ind_e_commerce: Some exposure
topic_cars: Interested
topic_fashion: Neutral
topic_sports: Interested
lstyle_shopping_style: Researcher
lstyle_frugality: Balanced
lstyle_fashion_sense: Practical
lstyle_subscription_count: 3-5
economic_motivation: Value-driven
pref_save_vs_spend: Saver-leaning
risk_tolerance: Cautious
decision_style: Consensus-driven
trust_level: Verifying
time_pressure: Deadline
att_online_reviews: Positive
cog_detail_orientation: Moderate
cog_patience: Low
pref_detail_brief_vs_full: Brief-leaning
device_context: Mobile, on-the-go
health_vision: Normal
```

主要诊断价值：家庭购买、汽车和配件 fitment、deadline、价值权衡，以及信息足够具体但不冗长时的满意度。

### Persona D：`shopping-premium-researcher`

定位：高收入、专业做消费者/电商研究、重证据和细节的资深用户；愿意为质量付费，偏好在桌面端仔细比较来源。

```yaml
age_bracket: 45-54
socioeconomic_band: High income
demo_parental_status: Parent of adults
demo_driver_status: Daily driver
seniority: Director
domain: Business & Management
role_function: Research
primary_language: English
english_proficiency: Native
tech_savviness: Digital native
skill_budgeting: Master
skill_research: Master
ind_e_commerce: Veteran
topic_cars: Passionate
topic_fashion: Passionate
topic_sports: Interested
lstyle_shopping_style: Researcher
lstyle_frugality: Spender
lstyle_fashion_sense: Trend-setter
lstyle_subscription_count: 6-10
economic_motivation: Premium-seeking
pref_save_vs_spend: Spender-leaning
risk_tolerance: Balanced
decision_style: Analytical
trust_level: Verifying
time_pressure: No rush
att_online_reviews: Skeptical
cog_detail_orientation: Very high
cog_patience: High
pref_detail_brief_vs_full: Every detail
device_context: Desktop, focused
health_vision: Normal
```

主要诊断价值：来源核验、规格和兼容性、premium choice、复杂比较，以及高完成度回答能否满足高细节用户。

### 可选 Persona E：`shopping-language-barrier-newcomer`

这个 persona 只在团队明确把语言公平性列为研究问题时加入。它应使用同一 32 维集合，并以 `primary_language: Mandarin`、`english_proficiency: Intermediate (B1-B2)` 和 `device_context: Mobile, on-the-go` 为核心信号；若还要加入 `accessibility_needs: Language barrier`，必须把它作为所有 arms 都具有的第 33 个字段重新冻结，不能只给该 persona 增长 prompt。

默认不加入的原因：

- main 文档规定 3–4 个 group，四个默认 persona 已达到上限；
- 它会额外增加 54 个 execution cells / replicate；
- 语言和文化变量需要单独做 fairness 解释，不能与一般购物偏好混为一个“人格效果”。

## 4. 六题与 Persona 的诊断对应关系

每题仍运行全部 persona；以下只是预期会被激活的差异。

### Kobe 球鞋

- Budget young parent：价格、现货、球鞋/体育兴趣、快速购买。
- Cautious retiree：给家人买礼物时的可信来源、风险和简单说明。
- Busy parent：生日 deadline、现货与实用购买决策。
- Premium researcher：多来源交叉核验、发售上下文和产品细节。

### Theory 礼服与配鞋

- Budget young parent：价格和流行感。
- Cautious retiree：经典款、可理解和可购买性。
- Busy parent：时间限制、实用搭配和简洁总结。
- Premium researcher：面料/风格证据、premium choice 和精细比较。

### Augusta 二手 Toyota

- Budget young parent：预算参考、家庭实用性和较高风险容忍。
- Cautious retiree：卖家可信度、风险、易读规格。
- Busy parent：价值、家庭实用性和日常驾驶经验。
- Premium researcher：严格核验配置、价格、里程和跨站参数。

### Minneapolis 家庭车

- Budget young parent：家庭预算、信息负担和低耐心下的筛选表现。
- Cautious retiree：长清单可读性和操作复杂度。
- Busy parent：与 persona 生活阶段最贴合，可检验家庭价值排序。
- Premium researcher：完整 spreadsheet、精细排序和证据一致性。

### 英国订阅组合

- Budget young parent：循环费用与低价替代。
- Cautious retiree：订阅条款、额外费用和简单操作。
- Busy parent：一次性形成可执行方案并控制时间。
- Premium researcher：服务条款、来源核验和质量优先组合。

### 三车配件

- Budget young parent：多车家庭的低价配件和快速决策。
- Cautious retiree：兼容性风险、页面可读性和下一步。
- Busy parent：多车家庭的 fitment 与实用性。
- Premium researcher：精确车型匹配、产品证据和 premium accessory 比较。

## 5. 最终要 evaluate 的点

这里需要区分两件事：上面的 32 个字段用来**定义 persona**；下面的指标用来**评估一次 run**。不能把 32 个 profile 字段机械平均成一个 persona 分数。

### 5.1 Original task completion judge

沿用 main 的 R1–Rn rubric judge：

- 每个 rubric item 独立判断 `met`。
- 同一 item 独立判断 `communicated`。
- `score = met / all rubric items`。
- `communication coverage = communicated / all rubric items`。
- `score_communicated = met among communicated / communicated`。
- 语气、人格、礼貌和文风不进入 task completion 分数。

需要按 task、persona、execution backbone 和日期分别保留原始 verdict；不能只存一个总百分比。

### 5.2 Persona Factor 1：persona-mediated conversation 如何影响 task completion

main 中 profile 不只影响 opening，也会影响 persona 对 `ask_user` 的后续回答。因此主比较不是“纯 opening paraphrase effect”，而是 **opening + follow-up replies 的完整 persona-mediated conversation effect**。比较同一日期、同一 execution backbone、同一 task 下，每个具名 persona 相对 `none` 的差值：

- task score delta；
- communication coverage delta；
- `score_communicated` delta；
- 哪些原始 rubric 被遗漏；
- opening 长度、总 clarification 数和最终 stop reason。

main 的 `communicated` 是根据整段 conversation 判断，不只看 opening，也没有直接标注“哪一项是由第几次 clarification 补回的”。如果要报告“首条消息保留率”或“ask_user 补回率”，必须使用预先写明规则的 transcript coding/judge，保存 analysis script/hash，并标成 dated post-hoc analysis。zero-`ask_user` runs 可以作为 opening-only 的描述性切片，但不构成随机化的纯 paraphrase 因果估计；若要纯 opening effect，需要固定/回放后续回复，这属于新 protocol。

### 5.3 Persona Factor 2：任务做完后，不同 persona 是否同样满意

沿用 Haoming branch 已合入 main 的 P1–P5 person-side judge：

- P1 `asked_for`：是否交付此人实际提出的内容。
- P2 `readable_for_them`：此人是否看得懂。
- P3 `actionable`：此人能否凭答案和保留页面直接行动。
- P4 `gap_handling`：agent 是否处理未说出口但重要的缺口。
- P5 `overall`：此人总体是否被服务好。

每项是 1–5 或 `n/a`。如果保留 Haoming 的双 judge 设计，则使用同一 GPT 5.6 Terra deployment 做两次独立调用，A/B 分开报告，并给出 exact agreement 和 within-one agreement；这叫同模型 self-consistency，不叫 cross-model agreement。

为了回答“即使 task 完美完成，不同 persona 满意度是否仍不同”，主分析必须限制在：

```text
judgement.score == 1.0
```

然后按 persona 比较 P1–P5，尤其是 P2、P3、P4 和 P5。当前 `report.py` 原生提供的是 `score_communicated == 1.0` 的 P5 切片；`judgement.score == 1.0` 的完整任务切片需要由冻结版本的 dated post-hoc analysis 脚本计算。两者都报告，但不能用 communicated-perfect 替代“原始 task 完美完成”，否则未被说出的 rubric 会被忽略。

### 5.4 Persona opening 的运行前质量门槛

正式花费浏览器/API 成本前，先用 main 的 `--preview` 查看 24 个具名 persona × task openings，并检查：

- 没有改变原 task 的事实性硬约束；
- 没有发明冲突的地点、预算、尺寸或 deadline；
- 四个 persona 对同一 task 的表达确实可区分；
- 差异来自已声明的 profile values，不靠年龄、职业或可访问性的刻板印象猜测；
- 没有泄露 system prompt、profile 字段名、rubric 或 role-play 指令；
- wording 自然，不是把 32 个属性机械塞入一段话。

main 当前没有 direct persona-fidelity/adherence judge。P1–P5 衡量的是 CUA 是否服务好了这个人，并不能证明 simulator 忠实表达了 32 个维度。因此运行前 preview 是质量门槛，不应把 Haoming 的 experience judge 重命名成 fidelity judge。若团队以后需要自动 fidelity score，应作为一个新的、带日期的协议扩展单独批准。

### 5.5 Robustness 与失败分类

每个 cell 还要记录：

- steps、`ask_user` 次数、stop reason；
- latency、tokens、cost（provider 能提供时）；
- 有效结果还是环境/基础设施失败；
- 403、Access Denied、CAPTCHA、Cloudflare、DNS、超时或空页面；
- 429、无权限、无效 model ID、不支持 tool call 等 provider 失败；
- judge failure 与 genuine agent failure。

环境或 provider 阻断的 cell 保存 artifact，但标为 excluded/unscored 并精确重跑，不能转换成 agent 0 分。

## 6. 聚合与报告规则

`report.py` 只提供 repo-native 的 per-task score table、均值、A/B experience 均值、within-one agreement 和 communicated-perfect P5 切片。下面的 task-balanced/micro、paired delta、中位数、`score ≥ 4`、exclusion rate 和 full-task-perfect 切片都属于本计划的 **dated post-hoc analysis**；实现时必须保存脚本、规则和 SHA，不能把它们写成 main 自带输出。

- 实验单元：`date block × replicate × execution backbone × task × persona`。
- 主 completion 汇总：task-balanced macro average；每个 task 等权，task 内各 persona 等权。
- 次级 completion 汇总：rubric-item micro average。不能只报 micro，因为 8-rubric 的 Minneapolis 和 7-rubric 的配件题会获得更大权重。
- Persona effect：同 executor、task、date 下，各 persona 与 `none` 做 paired delta。
- Execution-backbone effect：同 task、persona、date 下做 paired comparison。
- P1–P5 是 ordinal score，优先报告分布、中位数和 `score ≥ 4` 比例；均值只作 repo-compatible 次级结果。
- 每个汇总同时报告 valid N、excluded N 和 exclusion rate。
- Task completion、communication、experience 和运行效率永远分栏报告，不做加权总分。
- Setting 1 的推断单位是这四个具体 profile prompts。每个 group 只有一个手工 profile 时，只能报告 archetype-level bundle effect，不能写成“年轻家长/退休者/忙碌家长/高收入研究者这一整个人群”的平均效果。

## 7. Backbone 冻结方案

### 固定角色

- Persona simulator：`GPT 5.6 Terra`。
- Original task completion judge：`GPT 5.6 Terra`。
- Persona/experience judge：`GPT 5.6 Terra`；建议保留两次独立 A/B 调用。

### Execution backbone 候选

- Claude Opus 5.5
- GPT 6 Astra
- Muse Spark 1.1
- Gemini V4 Pro
- Kimi-K3
- Grok 4.7
- MiniMax M3
- GLM 5.3
- Qwen 3.8 27B

这些名称在本文档中是计划标签，不代表当前 main 已经能调用。正式运行前必须对每个模型完成：

- 精确 provider/deployment/model ID 解析；
- OpenAI-compatible chat/tool-call 兼容性 smoke test；
- 凭证、rate limit 和并发限制检查；
- temperature、tool schema、max token 与 reasoning 参数兼容性检查；
- 禁止无记录地用另一个模型替换失败模型。

若发生替换，必须在新的日期记录中写明原模型、替代模型、原因、受影响 cell，并把它视为新的 protocol version。

## 8. Setting 2：10–20 个单维度实验

Setting 1 的四个人格一次改变很多变量，只能解释“整体画像 bundle 是否影响结果”，不能说某一个维度导致了差异。

建议先筛选以下 12 个与 Shopping 最相关、且较容易在 utterance 中观察的维度：

```text
economic_motivation
risk_tolerance
trust_level
decision_style
time_pressure
cog_detail_orientation
cog_patience
tech_savviness
lstyle_shopping_style
att_online_reviews
pref_detail_brief_vs_full
need_for_cognition
```

Setting 2 使用自己冻结的 12-dimension baseline，不能把 Setting 1 的 32 维 profile 直接当作 leave-one-out 基线；例如 `need_for_cognition` 不在 Setting 1 的 32 维中，但会明确存在于 Setting 2 baseline。预注册的 paired endpoints 为：

```text
economic_motivation:         Cost-sensitive ↔ Premium-seeking
risk_tolerance:              Risk-averse ↔ Risk-tolerant
trust_level:                 Skeptical ↔ Trusting
decision_style:              Deliberative ↔ Intuitive
time_pressure:               No rush ↔ Deadline
cog_detail_orientation:      Low ↔ Very high
cog_patience:                Low ↔ High
tech_savviness:              Reluctant ↔ Digital native
lstyle_shopping_style:       Bargain hunter ↔ Researcher
att_online_reviews:          Skeptical ↔ Enthusiast
pref_detail_brief_vs_full:   Just the gist ↔ Every detail
need_for_cognition:          Low ↔ Very high
```

建议把团队口中的“ablation”实现为受控 single-dimension contrast：

- 固定一个 coherent baseline；
- 每个 pair 只改变一个 schema dimension，其他字段、task、date、executor 和 runtime 全部相同；
- 两个 arm 都必须在 persona utterance 中清楚表达自己的值，才能解释 paired effect；
- 比较 paired delta：task completion、communication 和 P1–P5；
- 年龄、语言、残障/可访问性另做 fairness stress test，不与行为维度一起排“谁影响最大”的名次。

如果团队说的 ablation 是字面上的 leave-one-dimension-out，则应另设：完整 profile 对比删除该字段后的 profile。它测量的是“这个字段出现在 prompt 中是否有影响”，与两种取值的 causal contrast 不是同一个问题，两个 effect size 不能混在一个排名里。

12 个维度 × 2 arms × 6 tasks × 9 executors 会达到 1,296 cells / replicate，因此不建议一开始全量跑。推荐：

1. 每个 task 先选 2–3 个最相关维度做 screening；
2. 找到有清楚 persona expression 且 effect 较大的候选；
3. 再把 top 3–5 dimensions 扩展到全部 6 task 和全部 execution backbone；
4. 只在共同 task support 或 task-standardized paired effect 上做排序。

默认把单次 `r1` 当作 pilot，不据此给“影响最大”下稳定结论。进入正式 dimension ranking 前，在当日 manifest 预注册 replicate N；默认建议至少 3 个独立 replicate，并同时报告各 replicate 而不是只报合并均值。

## 9. 为什么这个选择合理

- 4 个 persona 符合 main 的 3–4 group 规则，也落在团队提出的“大约 4–5 个”范围内。
- 四组覆盖年轻/年长、中低/高资源、初入职场/退休/家长经理/研究专业人员，以及不同的技术、设备、风险、耐心、细节和消费倾向。
- Shopping 六题同时包括球鞋、服饰、二手车、家庭车、订阅和汽车配件；四组在这些题上都有合理购买动机，不是为某一道题硬造一个 persona。
- 所有 persona 跑所有 task，避免把 task/site 难度与 persona 完全混淆。
- `none` control 给出原始 task 的基线，从而可以测量完整 persona-mediated conversation 的影响。
- 所有 profile 使用同一组 32 维字段，并避开会被 renderer 当作 nullish 丢弃的取值，控制实际字段数量；不同 value 的字数仍会造成 prompt 长度差异，所以另外记录渲染长度。
- 固定 Terra persona/judge、只变化 execution backbone，使整体设计更接近要比较的因素。
- Completion 与 satisfaction 分开，正好对应团队定义的两个 Persona factors。
- Setting 1 提供四个具体 archetype 的画像覆盖；Setting 2 再提供单维归因，两者回答不同问题而不是互相替代。需要 population/group-level 结论时，必须在每个 stratum 内增加多个从正式 pool 冻结的 persona。

## 10. 使用 main 代码/规则基线时必须接受的限制

### 10.1 Minneapolis task 与 8-tab 上限冲突

main 的 `MAX_TABS=8`，但 Minneapolis task 要求保留约 15 个车辆 listing 和一个 spreadsheet。即使所有网站可用，该 task 也不可能在当前 main 配置下满足全部开页要求。

因此必须在报告中把它标成 protocol-capacity limitation，不能把对应 rubric 的失败全部解释成 execution backbone 能力差。若以后把 tab 上限提高到 20，就是新的 protocol version，不能与当前 main-baseline 分数直接混合。

### 10.2 Persona opening 每个 cell 都重新生成

main 没有 frozen opening cache。同一 persona/task 在不同 execution backbone 前会由 Terra 重新生成 opening，因此 executor 差异会混入 paraphrase sampling variance。

不改 main 逻辑时，只能：

- 保存每个 opening；
- 随机/轮换 execution model 顺序；
- 尽量在同一日期块内完成同一 task/persona；
- 使用多个 replicate；
- 把结果解释为 end-to-end persona+executor performance，而不是纯 executor causal effect。

如果以后要冻结同一个 opening 给 9 个 executor，必须把它记录为 protocol revision，而不能说仍然是未修改的 main runner 行为。

### 10.3 当前 main 的 task/profile 状态

- 当前 `main` 工作树里的 `odyssey/tasks.json` 不是这六个 Shopping task；正式运行前要从已冻结来源精确 materialize 六题，不能改写 task 或 rubric。
- 当前 persona 文件是早期 travel-oriented 示例；本计划中的 Shopping profile 尚未 materialize。添加 schema-valid persona YAML / 更新 profile generator 属于实验数据配置，不是 runner 或 judge 逻辑修改。
- main 的 persona renderer 只读取 profile attributes，顶层 `note` 不会传给 simulator，所以每个群体身份必须由实际 attributes 支撑，不能只靠好听的 persona 名称。

### 10.4 Live-web availability

库存、价格、网页结构和反机器人策略会随日期改变。不同 model 如果分散在不同日期运行，网站状态本身就可能造成假模型差异。因此日期既是记录字段，也是实验 blocking variable。

## 11. 按日期隔离的结果约定

### 目录

每次开始一个新日期块时使用：

```text
artifacts/experiments/YYYY-MM-DD/
  shopping-main-setting1-rN[-attemptNN]/
    RUN_MANIFEST.md
    RUN_MANIFEST.json
    inputs/
      tasks.json
      personas/
      prompts/
      runtime-config.json
    results/
    logs/
    analysis/
    report.md
```

示例：

```text
artifacts/experiments/2026-09-26/shopping-main-setting1-r1/
```

main 已支持 `--out`，因此可以把 `results/` 直接指向当日目录，无需修改 runner 逻辑。`inputs/` 必须保存实际使用的完整 task 文件、persona YAML、prompts 和 runtime arguments，不能只记 SHA；否则工作树切换后，`experience_judge.py` 会从新的 `odyssey/tasks.json` / `odyssey/personas/` 读取错误输入。

date block 定义为一次 grid/replicate invocation 在 `America/Los_Angeles` 的启动日期，同时在 manifest 中为每个 cell 记录 UTC start/end。main 的单次 `run_grid.sh --out` 不会在跨午夜时自动换目录，因此若必须严格按自然日切开，就在午夜停止并用新日期目录启动下一次 invocation；否则整个 invocation 保留在启动日的 block 中。后续日期重跑写入新的 `attemptNN`，不覆盖原 cell。

`experience_judge.py` 必须在切换工作树输入前完成；需要日后重判时，先在独立 worktree 中 checkout 对应 Git SHA，并把 dated `inputs/` 恢复到脚本期待的路径。judge 和 post-hoc analysis 完成后写入 `FINALIZED` 标记，此后该日期目录才视为不可变。

### 每个 manifest 必须记录

- local date、UTC start/end、experiment ID、replicate ID；
- branch、Git SHA、dirty status；
- task file SHA-256、persona YAML SHA-256、prompt SHA-256，以及对应 dated input snapshot 路径；
- persona、judge 和 execution 的精确 provider/deployment/model IDs；
- temperature、max steps、max tabs、headless、browser/profile mode；
- planned/completed/valid/excluded/rerun cell 数；
- 每个 exclusion 的分类与原始证据路径；
- 相对上一日期是否有任何 protocol deviation。

### 时间区组原则

- 同一个 task × persona block 的 9 个 executor 尽可能在同一日期、相近时间运行。
- 轮换或随机化 executor 顺序；不要把 Model A 全部放在第一天、Model B 全部放在第五天后直接比较。
- judge/report 完成并写入 `FINALIZED` 后，日期目录保持不可变；新的判断或重跑通过新日期/attempt 关联旧 cell。
- `report.py` 会为同一 `(task, persona, model)` 选择最新结果，因此绝不能把多个日期混在一个 results root，否则旧尝试会被静默遮住。

## 12. 后续实验日志模板

每次用户要求运行实验时，在本文档末尾追加一个新日期段，同时生成独立 dated artifact 目录。

```markdown
## YYYY-MM-DD：<experiment-id>

- Protocol: main / revision id
- Replicate: rN
- Date block: America/Los_Angeles YYYY-MM-DD
- Git: <branch>@<sha>, clean/dirty
- Frozen inputs: <dated inputs path>
- Tasks: <task hash>
- Personas: <ids + hashes>
- Persona/Judge: <exact deployment>
- Execution backbones: <exact model ids>
- Analysis code/rules: <path + hash>
- Planned cells: N
- Completed numeric results: N
- Valid cells: N
- Excluded/rerun cells: N
- Deviations: none / <details>
- Result root: <path>
- Summary report: <path>

### Results

- Task completion:
- Persona-mediated conversation / communication:
- P1–P5 experience:
- Perfect-task satisfaction slice:
- Environment/provider failures:
- Interpretation and limitations:
```

## 参考依据

- `odyssey/README.md`：main 的 persona 数量、preview 和完整 persona × task grid 规则。
- `odyssey/run_grid.sh`：persona × task 两层循环。
- `odyssey/prompts/rubric_judge.md`：`met` 与 `communicated`。
- `odyssey/prompts/experience_judge.md`：Haoming person-side P1–P5。
- `odyssey/experience_judge.py`：双 judge 独立保留和 agreement 逻辑。
- `odyssey/dimensions.json`：所有 persona dimension 与合法取值。
- `artifacts/legacy/pre-standard-20260920/PersonaCUABench.md`：可访问的会议/分工记录。
- `SHOPPING_V1_V2_EVALUATION_REPORT.md`：此前两版 Shopping 运行结果和环境审计。
