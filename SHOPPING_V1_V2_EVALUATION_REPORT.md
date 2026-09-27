# Shopping 场景评测报告：Version 1 与 Version 2

生成日期：2026-09-26

> 这是两种历史协议的对照报告。后续团队决定以 main 协议运行 Shopping-specific Setting 1 的三次正式重复；其日期隔离结果与结论见 [`artifacts/experiments/SHOPPING_MAIN_SETTING1_FORMAL_REPORT.md`](artifacts/experiments/SHOPPING_MAIN_SETTING1_FORMAL_REPORT.md)。本文的历史 Version 1 使用通用/旅行向 persona，不是新正式序列的 r1，两者不合并统计。

## 版本定义与结论摘要

- **Version 1**：`main@4a1c0f2` 上的基线方法，结果目录为 [`artifacts/shopping-version-1-main-4a1c0f2`](artifacts/shopping-version-1-main-4a1c0f2)。
- **Version 2**：以 `main-shop@70e5443` 为 reference commit 的 matched-pair 方法，结果目录为 [`artifacts/shopping-results`](artifacts/shopping-results)。结果本身不直接嵌入 Git SHA，因此不把该 commit 表述成每条结果已自证的 execution SHA。
- 两版使用同一组 6 个 Shopping task ID 和同一套 task rubrics；实际运行时也都使用 Azure OpenAI-compatible endpoint 上的 `gpt-5.6-terra`，温度为 1，最大步数为 50。
- 两版的 persona 设计、对话协议、浏览器 tab 上限、cell 数量和附加评分不同，因此 **Version 2 的 49.51% 与 Version 1 的 33.53% 不能直接解释成模型能力提升 15.98 个百分点**。它们是两种协议下的结果，不是只改变一个变量的 A/B test。
- Version 1 的 30/30 个 cell 都生成了数值评分，但环境审计后只有 7 个 cell 可保留；另外 23 个因目标网站 403、Access Denied、Cloudflare、安全验证、DNS 或超时而应排除并在环境恢复后重跑。
- Version 2 的 36/36 个 cell 均完成 task judge、双路 experience judge 和 persona-fidelity judge；环境审计后 7 个可保留、29 个应排除并重跑。当前也只有 replicate `r1`，尚不能代替多次重复实验。

## 评测范围

两版覆盖相同的 6 个 Shopping task：

- `39255449e341`：Kobe 球鞋的即将发售与现货信息。
- `7cc602f23977`：Theory 绿色礼服、配套女鞋与 ooShirts 服务。
- `67ad95421a30`：Augusta 附近二手 Toyota 与车型参数比较。
- `63d68bb25e27`：Minneapolis–St. Paul 家庭用车清单与 CryptPad Sheet。
- `4b9850333bdd`：英国啤酒、零食、流媒体与纸质信件订阅夜方案。
- `44f1e0211671`：Highlander、Fiat 500、Honda Civic 的汽车配件。

## 1. 结果

### 1.1 Version 1：main 基线方法

完成情况：

- 设计：6 个 task × 5 个 persona/control，共 30 个 cell。
- 结果完整性：30/30 个 `result.json` 含数值 task judgement。
- 停止原因：22 个 `finish`，8 个 `no_tool_call`；两类结果均有 final answer 和 judge score。
- 原始 rubric 得分：`57/170 = 33.53%`，这是把全部 rubric item 合并后的 micro score。
- 30 个 cell 的简单平均分：`34.57%`。
- 沟通覆盖率：`118/170 = 69.41%`，即 69.41% 的隐藏 rubric 要求实际进入了 persona-agent 对话。
- 已沟通要求中的完成率：`55/118 = 46.61%`。

按 task 汇总的原始 rubric 得分：

- Kobe 球鞋：`8/25 = 32.00%`；沟通覆盖 `8/25 = 32.00%`。
- Theory 礼服：`8/20 = 40.00%`；沟通覆盖 `19/20 = 95.00%`。
- Augusta 二手 Toyota：`1/25 = 4.00%`；沟通覆盖 `10/25 = 40.00%`。
- Minneapolis 家庭用车：`0/40 = 0.00%`；沟通覆盖 `25/40 = 62.50%`。
- 英国订阅夜：`15/25 = 60.00%`；沟通覆盖 `23/25 = 92.00%`。
- 汽车配件：`25/35 = 71.43%`；沟通覆盖 `33/35 = 94.29%`。

按 persona/control 对 6 个 task 做 cell macro average：

- `travel-expert`：约 40%。
- `none`：约 36%。
- `budget-student`：约 34%。
- `elderly-novice`：约 34%。
- `non-native-speaker`：约 29%。

环境审计结论：

- **可保留：7/30 个 cell。** 分别是 `39255449e341/non-native-speaker`、`67ad95421a30/budget-student`，以及 `4b9850333bdd` 的全部 5 个 persona/control。
- **应排除并重跑：23/30 个 cell。** Kobe 有 4 个、Theory 有 5 个、Augusta 有 4 个、Minneapolis 有 5 个、汽车配件有 5 个。
- 字面返回 HTTP 403 的是 2 个 Augusta cell；Theory 的 5 个 cell 是 Access Denied，其他主要阻断包括 Cars.com Cloudflare、SoleCollector DNS、SneakerNews 超时，以及 Temu 登录/安全验证页。
- 7 个可保留 cell 的描述性得分为 `16/35 = 45.71%`。由于这 7 个 cell 在 task 和 persona 上严重不平衡，这个数字只能说明剩余样本，不能代表 Version 1 的总体能力。
- Google CAPTCHA 和 PrintPigeon `.com` 错误并非一律判为失败：如果轨迹成功切换搜索引擎或使用正确的 `.co.uk` 页面并完成取证，就保留该 cell。环境判定看的是是否实际阻断 rubric，而不是简单搜索错误关键字。

因此，Version 1 可以说“30/30 已运行并产出原始评分”，但不能说“30/30 都是有效的 agent 能力观测”。用于正式分析时，应保留原始 artifact，将 23 个阻断 cell 标为无结果/待重跑，而不是记作 agent 的 0 分失败。

### 1.2 Version 2：matched-pair 方法

完成情况：

- 设计：6 个 task；每个 task 选择 3 个 persona axis，每个 axis 有 positive/negative 两个 arm，共 18 个 matched pairs、36 个 cell。
- 当前 replicate：`r1`。
- 结果完整性：36/36 个 cell 有数值 task judgement；36/36 完成两路 experience judgement；36/36 完成 persona-fidelity judgement。
- 停止原因：33 个 `finish`，3 个 `no_tool_call`；36 个均有 final answer 和 judge score。
- 原始 rubric 得分：`101/204 = 49.51%`。
- 36 个 cell 的简单平均分：`49.42%`。
- 沟通覆盖率：`204/204 = 100%`。
- communication guardrail：36/36 通过。

按 task 汇总的原始 rubric 得分：

- Kobe 球鞋：`18/30 = 60.00%`。
- Theory 礼服：`8/24 = 33.33%`。
- Augusta 二手 Toyota：`5/30 = 16.67%`。
- Minneapolis 家庭用车：`10/48 = 20.83%`。
- 英国订阅夜：`24/30 = 80.00%`。
- 汽车配件：`36/42 = 85.71%`。

Experience judge 结果：

- 两次独立 judgement 在 1 分以内的一致率：`177/179 = 98.88%`。
- 完全同分：`132/179 = 73.74%`。
- 共有 180 个潜在维度判断，其中 1 个合法记为 `n/a`，所以一致性分母为 179。
- P1「是否交付此人实际提出的内容」：Judge A `3.028`，Judge B `3.139`。
- P2「此人是否读得懂」：Judge A `4.500`，Judge B `4.583`。
- P3「此人能否直接采取行动」：Judge A `2.944`，Judge B `2.917`。
- P4「是否处理未说出口但重要的缺口」：Judge A `3.361`，Judge B `3.286`；Judge B 有 1 个 `n/a`。
- P5「此人总体是否被服务好」：Judge A `3.000`，Judge B `3.139`。
- 两个 judge 都是同一 `gpt-5.6-terra` deployment 的独立调用，而不是跨模型一致性实验；分数保留为并列结果，**不取平均来隐藏分歧**。

Persona-fidelity 结果：

- 36 个 cell 各有 1 个目标 persona attribute：score 0 有 18 个，score 1 有 10 个，score 2 有 8 个；另有 3 个 cell 被标记为出现反向表达。
- 只有 score 2 才算 persona target 被清楚表达；score 1 只表示弱或含混证据。
- 18 个 matched pairs 中，只有 2 对同时满足：positive arm 与 negative arm 都得到 score 2，并在行为证据上表现出实质性的相反方向。
- 这 2 对是：
  - Theory task 的 `price_orientation`：premium 方案 `$434.99`，cost-sensitive 方案 `$316.99`，差 `$118`。
  - 英国订阅夜 task 的 `price_orientation`：premium 方案 `£53.99`，cost-sensitive 方案 `£35.99`，差 `£18`。

Version 2 的结果说明 full-coverage 协议确实把全部 rubric 要求带入了对话，但 persona 差异并没有在大多数 pair 中被清楚、双向地表达出来。100% communication coverage 也不等于 100% task completion；原始 task score 仍为 49.51%。

环境审计结论：

- **可保留：7/36 个 cell。** 分别是 `39255449e341/mp_evidence_verification_negative`，以及 `4b9850333bdd` 的全部 6 个 matched-pair arms。
- **应排除并重跑：29/36 个 cell。** Kobe 有 5 个，Theory、Augusta、Minneapolis 和汽车配件各 6 个。
- Kobe 的 5 个 cell 被 SoleCollector DNS 失败阻断；Theory 全部 6 个停在 Theory Access Denied；Augusta 全部 6 个遇到 Edmunds 403，部分还遇到 Cars.com Cloudflare；Minneapolis 全部 6 个遇到 Cars.com Cloudflare/超时及 CryptPad 不可编辑；汽车配件全部 6 个无法取得可验证的 Temu live listing。
- 字面 HTTP 403 出现在 7/36 个 cell：Augusta 的 6 个 cell，以及 `7cc602f23977/mp_decision_style_positive` 的一个备用鞋类站点；后者的主要阻断仍是 Theory Access Denied。
- 英国订阅夜的 6 个 cell 都成功从错误或失效路径恢复到可用的官方页面，因此全部保留。
- 7 个可保留 cell 的描述性得分为 `28/35 = 80.00%`。其中 6 个都来自同一个英国订阅 task，样本同样严重不平衡，不能把 80% 当作 Version 2 总体能力。

上述环境分类不修改原始 JSON：49.51% 仍是完整保存的 raw execution score。用于因果分析时，29 个阻断 cell 应记为 excluded/unscored，而不是转换成 agent 的零分。Persona-fidelity 中只依据 user utterance 的“是否表达目标属性”判断不依赖网页是否可访问；但涉及最终选择或行为差异的解释，仍应结合环境阻断谨慎使用。

### 1.3 两版结果应如何一起解读

- 可以比较协议产出的现象：Version 2 沟通覆盖更完整，并额外提供 experience 与 persona-fidelity 证据。
- 不能把 `49.51% - 33.53%` 当作模型提升，因为 Version 2 强制 full coverage，而 Version 1 允许 persona 自然遗漏隐藏要求；两版 persona 也不是同一组。
- Version 1 的 tab 上限是 8，Version 2 是 20；这对需要同时保留大量商品或车辆页面的 task 有直接影响。
- 特别是 Minneapolis task 要求保留约 15 个车辆 listing 和一个 spreadsheet，Version 1 的 8-tab 上限在结构上就无法同时满足全部开页要求。
- Version 1 是 5 个通用 persona/control 跨全部 task；Version 2 是每个 task 选择 3 个相关轴并做正负配对。
- Version 1 有 23 个、Version 2 有 29 个已确认环境阻断 cell。两版都各自只剩 7 个可直接保留，而且保留样本集中在少数 task；在完成合适的 environment reattempt 前，两个 raw score 都不是干净的能力估计。Version 1 若重新采样 utterance 只能叫 configuration-matched reattempt；Version 2 已冻结 opening，复用原 opening/hash 时才可称 frozen-opening re-execution。

## 2. 具体是怎么做的

### 2.1 两版共有的执行链路

1. 固定 Shopping task 文本和逐项 rubric。两版的 task/rubric 数据一致，CUA system prompt 和 rubric-judge prompt 也保持一致。
2. persona model 根据 persona profile 和 task 生成开场请求，并在 agent 追问时继续以该 persona 回答。
3. computer-use agent 只看到 persona 实际说出的内容，在真实 Chrome 和实时网页上搜索、打开页面、读取证据并给出最终回答。
4. rubric judge 同时读取隐藏 task、完整对话、操作轨迹、最终回答和结束时保留的 tabs，对每个 rubric item 分别判断 `met` 与 `communicated`。
5. 每个 cell 保存配置、对话、轨迹、最终回答、tabs 和 judgement，供汇总及人工环境审计。

### 2.2 Version 1 的做法

- 在最新 `main@4a1c0f2` 上执行，不修改 runner、prompt、rubric 或评分逻辑。
- `main` 当时自带的是另一组 task，因此运行时只把历史 Shopping task 数据从 `f8e8a6f` 精确放入 `odyssey/tasks.json`；数据 SHA-256 为 `fc327ba9934171865d93b41f2edf12d4243b2fd9787f3f7d4ff9db96c262e985`。运行后已恢复 main 原文件。
- 采用 main 的通用 grid：`none`、`travel-expert`、`elderly-novice`、`budget-student`、`non-native-speaker`，共 `6 × 5 = 30` 个 cell。
- 四个具名 persona 都是 38 个 MatrAIx 维度组成的复合画像，而且若干原本是 travel-oriented 示例画像被复用于 Shopping，因此 persona 之间会同时改变人口、领域、可访问性和行为等多个属性；`none` control 则直接发送完整 task 原文。这种设计可以观察完整人物画像下的自然交互，但不能把 persona 间差异归因到单一维度。
- 通用 persona prompt 允许 persona 按自己的表达习惯自然省略信息，agent 最多可使用 5 次 `ask_user` 追问。因此隐藏 rubric 是否进入对话，本身就是 Version 1 要观察的现象之一。
- main 默认要求 OpenRouter 上的 Qwen 和 OpenAI `gpt-5.5`，当前凭证不可用。经授权，persona、agent 和 inline judge 都替换为已配置 Azure endpoint 上的 `gpt-5.6-terra`；其余 prompt、规则和评分标准不变。
- 该部署不接受 main 默认的 temperature 0.7，因此使用唯一兼容值 1.0；`max_steps=50`、`max_tabs=8`、headless 模式保持记录在 artifact 中。
- 企业 Chrome 策略在第一次复用 profile 后禁止 remote debugging。为完成运行，每个 cell 通过命令行使用新的隔离 profile；没有修改代码逻辑。两次启动失败的历史 `error.txt` 被保留，对应 cell 后续都已有成功产出的 `result.json`。
- 运行完成后逐 cell 检查 403、Access Denied、Cloudflare、安全验证、DNS、超时与空页面是否阻断必需证据，再把 cell 分为保留或待重跑。

### 2.3 Version 2 的做法

- 使用 `main-shop` 的 `matched_pair_full_coverage.v1` 协议；参考 commit 为 `70e5443`。
- 每个 task 先挑选 3 个与购物行为相关的 persona axis，例如 price orientation、purchase risk、detail depth、time pressure、decision style 或 evidence verification。
- 本次共使用 6 类 axis：evidence verification、price orientation、purchase risk、decision style、time pressure 与 detail depth；12 个 positive/negative persona 中没有 `none` control。
- 每个 axis 构造 positive/negative 两个 profile。pair 内保持共享的 6 维行为 baseline、task、模型、prompt、限制和 replicate 不变，不引入 demographic 差异，只翻转目标 persona 字段；两臂共享原 task 的完整要求，但分别表达相反的偏好或行为倾向。
- full-coverage persona prompt 要求在初始消息中传达所有原始 rubric，并由 communication guardrail 检查；本次 36/36 通过。
- persona opening 预先物化并冻结；task、profile、prompt、model、browser、replicate 和 opening cache key 都以 snapshot/hash 记录，避免恢复运行时悄悄改变条件。
- pair 的先后顺序做了 counterbalancing，降低固定先后顺序带来的偏差。
- 每个 cell 使用独立显式 Chrome profile，`max_steps=50`、`max_tabs=20`、headless；persona、agent 和 inline judge 均为 Azure-compatible `gpt-5.6-terra`，temperature 1.0。
- task run 完成后，再对每个 cell 做两次相互独立的 experience judgement，以及一次 persona-fidelity judgement。
- 现有结果 JSON 没有直接嵌入 Git SHA；运行所用的三项 runner 修正随后在 rebase 后记录到 `main-shop@70e5443`。每个结果自身仍保存 task、profile、prompt 与 run configuration hash，用于复核。

### 2.4 两种方法最关键的差异

- Version 1 关注“不同通用 persona 自然会说出什么，以及 agent 对已说内容做得怎样”；隐藏要求可能没有被说出。
- Version 2 关注“在任务信息完全覆盖的条件下，一对相反 persona 倾向是否会产生稳定、可观测的行为差异”。
- Version 1 更接近开放式 persona interaction，但 completion score 会同时混入信息遗漏与 agent 执行能力。
- Version 2 用 full coverage 隔离了信息遗漏，却也降低了对“persona 是否自然选择说什么”的测量；因此另加 persona-fidelity judge 检查目标特征是否真的表达出来。

## 3. 评分标准

### 3.1 Task rubric：`met`

每个 task 被拆成固定的 R1–Rn。Judge 对每项独立判断：

- `met=true`：最终回答、操作轨迹和结束 tabs 中有足够证据表明要求实际完成。
- 要求“页面保持打开”时，结束 tabs 中必须存在对应页面。
- 报告价格、库存、规格或配送等网页事实时，agent 必须实际访问到能展示该信息的页面；只凭猜测或搜索片段不足以自动算完成。
- 总分公式：`score = met 的 rubric 数 / 全部 rubric 数`。
- 这 6 个 task 每跑一轮共有 34 个 rubric item，因此 Version 1 的总分母是 `34 × 5 = 170`，Version 2 是 `34 × 6 = 204`。
- 本报告的 `57/170` 与 `101/204` 是跨 cell 合并 rubric item 后的 micro score；它与“先算每个 cell 再简单平均”的 macro score 不是同一统计量。
- `trajectory_efficiency = (met / total) / max(steps, 1)` 是 artifact 中保留的辅助效率指标，不替代 task score。

### 3.2 Communication：`communicated`

Judge 对同一 rubric item 另做独立判断：

- `communicated=true`：persona 明确说出该要求，或语义上足够清楚，或 agent 通过追问把它确认出来。
- persona 没提、agent 也没问到的具体网站或细节，记为 `communicated=false`。
- 沟通覆盖率公式：`communicated 的 rubric 数 / 全部 rubric 数`。
- 已沟通内容完成率公式：`score_communicated = 在 communicated=true 的项目中 met=true 的数量 / communicated=true 的数量`；若没有任何已沟通项目，则为 `null`。
- `communicated` 衡量要求是否进入对话，不衡量回答质量；它不能替代 `met`。

### 3.3 Experience：P1–P5，仅 Version 2

Experience judge 站在具体 persona 的角度，以 1–5 分或 `n/a` 评分：

- P1 `asked_for`：是否交付此人实际说出或明确暗示的内容。
- P2 `readable_for_them`：语言、结构和细节是否适合这个人的词汇、技术熟悉度、注意力或可访问性需求。
- P3 `actionable`：此人能否凭答案、链接、价格、时间和保留页面直接采取下一步行动。
- P4 `gap_handling`：对 persona 未说但重要的信息，agent 是否通过追问、显式假设、风险提示或合理决策处理，而不是无声猜测。
- P5 `overall`：从该 persona 的整体感受看，是否被服务好；不是 P1–P4 的机械平均。
- 分值含义：5=充分满足且证据清楚；4=基本满足、仅小缺口；3=部分满足、有一个重要缺口；2=大部分失败；1=明显失败。
- 每个 cell 做两次独立 judgement，逐项并列报告并统计一致性，不把两次评分平均成一个看似更稳定的数字。
- Experience 不与 task score 混成一个总分；可读、礼貌的回答不能抵消未完成的 task。

### 3.4 Persona fidelity，仅 Version 2

Persona-fidelity judge 只检查 user/persona utterances 中的目标 persona attribute，不用 CUA 表现或 task 成败来替 persona 表达加分：

- 0：没有肯定证据。
- 1：只有弱、含混或间接证据。
- 2：目标倾向被清楚表达；只有此档记为 `expressed=true`。
- `contradicted` 单独记录：如果说法或行为明确朝目标的相反方向，该 target 必须记 0，不能被一个模糊正向信号抵消。
- pair separation 的严格条件是：同一 matched pair 的 positive 与 negative 两臂都必须得 2 分，而且证据显示实质性的相反行为，而不只是换了措辞。
- 自动汇总只能先标出 `separated_pending_evidence_review`；最终认定还需要人工核对两侧引用的 utterance 和实际行为。本报告列出的 2 对已经按该严格条件复核。
- communication guardrail 还要求原 task 的全部 rubric 被传达；未通过时，该 pair 不能用于解释 persona effect。

Repo 当前没有单独的 CUA-alignment verdict；P1、task score 与 persona fidelity 分别回答不同问题，不能重命名或合并成“alignment 分数”。

### 3.5 环境失败的计分规则

- 如果完成 rubric 所必需的网站被 403、Access Denied、CAPTCHA/安全验证、Cloudflare、DNS、持续超时或空页面阻断，这属于环境/网站失败，不属于 agent 能力失败。
- 这类 cell 的原始 artifact 和 judge 输出应保留，但在正式因果分析中标为 excluded/unscored，并在环境恢复后用相同 task、persona/arm、配置和 replicate 重跑。
- 不能因为最终 `score=0` 就自动判定 agent 执行失败；必须查看 trajectory，确认是 agent 决策问题还是外部环境阻断。
- 如果 agent 成功绕过非关键错误并取得完成 rubric 所需的证据，则不因轨迹中出现过 CAPTCHA、DNS 或超时字样而机械排除。

## 限制与下一步

- Version 1 需要在网站环境恢复后对 23 个被阻断的 cell 做 configuration-matched environment reattempt；如果没有复用原 persona opening，不能写成 exact rerun。在此之前，33.53% 只能作为原始运行统计，不能作为干净的能力估计。
- Version 2 同样需要对 29 个被阻断的 cell 重试；49.51% 也只是原始运行统计。其 opening 已预先冻结，所以应复用原 opening/hash 做 frozen-opening re-execution，且不得改 task、arm、模型、prompt、limits 或 replicate ID。
- Version 2 当前只有 `r1`。若按多重复设计扩展到 `r1`–`r3`，总规模应为 108 个 cell；在另外两个 replicate 完成前，不应声称 matched-pair effect 稳定。
- 两版都依赖实时网页，库存、价格、页面结构和反自动化策略会随时间变化。重跑时必须保留时间戳和完整配置，不应用新旧网页状态混合解释模型变化。
- 如果目标是回答“哪种方法更适合 persona evaluation”，Version 2 的可解释性更强，因为它同时提供 task completion、experience、persona expression 和 pair separation；如果目标是观察 persona 自然遗漏哪些需求，Version 1 的开放式对话更直接。两者测量的问题不同，可以并用，但不应把分数直接合并。

## 可复核产物

- 两版总索引：[`artifacts/shopping-comparison-versions.json`](artifacts/shopping-comparison-versions.json)
- Version 1 标注与环境审计摘要：[`artifacts/shopping-version-1-main-4a1c0f2/_comparison_version.json`](artifacts/shopping-version-1-main-4a1c0f2/_comparison_version.json)
- Version 2 标注与运行摘要：[`artifacts/shopping-results/_comparison_version.json`](artifacts/shopping-results/_comparison_version.json)
- Version 1 原始结果：[`artifacts/shopping-version-1-main-4a1c0f2`](artifacts/shopping-version-1-main-4a1c0f2)
- Version 2 原始结果：[`artifacts/shopping-results`](artifacts/shopping-results)
