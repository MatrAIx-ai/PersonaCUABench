# Shopping main / Setting 1 正式实验报告

> 状态：已完成预先设定的 `r1–r3` 三次正式重复。90/90 个唯一 task×arm cell 都有数值 task score 和 A/B experience judgement；逐 cell 环境审计为 `KEEP 37 / EXCLUDE_RERUN 53`。因此 raw grid 已完成，但环境校正后的能力估计仍未完成，不应把 90-cell raw 均值当成干净的模型分数。
>
> 版本定义：**Version 1 = `main` 基线**，即本次正式实验使用的版本；**Version 2 = 之前工作分支上的历史实验**，仅保留作历史对照，不属于本次 `r1–r3`，也不与本文结果合并统计。

本实验回答两个彼此分开的 persona 问题：完整 persona 画像是否通过任务改写与后续对话影响任务完成；即使任务结果相同，不同 persona 对可读性、可行动性和整体体验是否有不同评价。协议决策见 [Shopping main 实验计划](../../SHOPPING_MAIN_EXPERIMENT_PLAN.md)。

三次 raw 结果的 task-balanced/cell-macro completion 为 `0.371`，rubric-item micro 为 `189/510 = 0.371`。但 53/90 cell 的 required/communicated live-web evidence 被外部站点实质阻断，而 15 个 Minneapolis cell 还另有 `MAX_TABS=8` 的结构性 censor。最稳定的可解释信号不是一个 persona “赢了”，而是 persona 改写明显改变了原 rubric 进入对话的比例：`none=100%`，premium `99.0%`，busy `72.5%`，budget `63.7%`，cautious `47.1%`。在体验上，可读性 P2 最高（A/B `4.42/4.33`），可行动性 P3（`2.96/2.93`）和整体 P5（`3.21/3.13`）明显更低。

## 1. 结果

### 2026-09-26：Version 1 / Setting 1 / r1

r1 的日期块按 grid 启动时的 America/Los_Angeles 日期记为 `2026-09-26`；虽然运行和审计跨过午夜，整个 invocation 仍保留在同一日期目录中。

#### 1.1 当前状态与两种结果口径

- 计划规模：`6 tasks × (4 personas + none) = 30 cells`。
- 原始执行完整性：30/30 个唯一 cell 均生成可解析的 `result.json` 和数值 task-judge score。
- 历史启动错误：另有 2 次 Chrome 启动失败；对应 cell 后来均用新 profile 成功重跑。这两次只保留作运行证据，不是缺失 cell，也不属于下面 18 个环境排除。
- 环境有效性：人工逐 cell 审计后，`KEEP = 12/30`，`EXCLUDE_RERUN = 18/30`。
- 因此，下面的 30-cell completion 数字是**原始观察结果**，不是环境校正后的正式性能结论。18 个被阻断的 cell 虽已有原始分数，但在正式环境有效口径中应视为未评分/无结果，并在环境恢复后做 configuration-matched environment reattempt，不能把它们记为 agent 的 0 分或“执行失败”。如果 reattempt 重新采样 persona utterance，就不能称为 exact rerun；`r2/r3` 也是独立 formal replicates，不能回填 r1 的缺失 observation。
- 12 个保留 cell 在 task 和 persona 上严重不平衡，其宏平均 `0.2866`、rubric-item micro `19/68 = 0.2794` 只能描述保留子集，不能代表模型整体 Shopping 表现。

环境保留情况：

| Task | KEEP | EXCLUDE_RERUN | 说明 |
| --- | ---: | ---: | --- |
| Kobe 球鞋 | 3 | 2 | Sole Collector DNS 阻断影响 2 个明确需要该来源的 cell |
| Theory 礼服 | 0 | 5 | Theory/Akamai Access Denied，部分替代商品页也被阻断 |
| Augusta 二手 Toyota | 1 | 4 | Edmunds 403、Cars.com/其他站点验证墙或不可用页面 |
| Minneapolis 家庭车 | 2 | 3 | Cars.com、CryptPad 等出现验证墙、超时或不可操作页面；另有固定 tab 上限 |
| 英国订阅组合 | 5 | 0 | 错误域名等问题均被恢复或有可访问的正式来源 |
| 三车配件 | 1 | 4 | Temu 登录/安全验证阻断实际商品页 |
| **合计** | **12** | **18** | 环境排除等待同规格 environment reattempt |

环境判定不是简单按关键词自动归类：只有当 403、Access Denied、CAPTCHA/Cloudflare、DNS、持续超时、空页或不可操作页面实质阻断 required/communicated evidence 时才排除；若运行已恢复，或被阻断页面与 persona 实际要求无关，则保留为 agent/protocol outcome。

#### 1.2 原始 task completion（全部 30 个数值 cell）

以下是未经环境有效性过滤的原始分数；列顺序为六道固定 Shopping task。

| Arm | Kobe | Theory | Augusta | Minneapolis | UK 订阅 | 配件 | 6-task 宏平均 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `none` control | 0.800 | 0.500 | 0.200 | 0.375 | 0.600 | 0.714 | **0.5315** |
| Budget young parent | 0.200 | 0.500 | 0.000 | 0.000 | 0.400 | 0.714 | **0.3023** |
| Busy parent | 0.200 | 0.250 | 0.000 | 0.000 | 0.400 | 0.714 | **0.2607** |
| Cautious retiree | 0.000 | 0.250 | 0.000 | 0.125 | 0.000 | 0.714 | **0.1815** |
| Premium researcher | 0.600 | 0.250 | 0.000 | 0.250 | 0.800 | 0.714 | **0.4357** |

30-cell 原始总体结果：

- cell-macro task completion：`0.3423`；rubric-item micro：`59/170 = 0.3471`。
- 平均 communicated-rubric coverage：`0.7721`；micro coverage：`130/170 = 0.7647`。
- communicated-only cell-macro：`0.4045`（29 个有定义的 cell）；micro：`58/130 = 0.4462`。
- 相对同 task 的 `none`，四个 persona 的 completion mean delta 分别为 budget `-0.229`、busy `-0.271`、cautious `-0.350`、premium `-0.096`。这只是单 replicate、且受 live-web 阻断影响的描述性结果，不能据此给稳定 persona 排名。

原始结果中，control completion 最高，premium 次之；但这不等于 persona 越简单越好。特别是 budget 的 communicated-only 宏平均为 `0.5428`，高于其完整任务分数 `0.3023`，原因是它平均只传达了 62.5% 的原 rubric。communicated-only score 不能替代完整任务完成度。

#### 1.3 Persona experience judge（全部 30 个 raw cells）

30/30 个数值 cell 都完成两次相互独立的 `gpt-5.6-terra` experience judgement。A/B 是同一 deployment 的重复采样，用于 self-consistency，不是 cross-model agreement；两次评分保持分开，不与 task score 合成。

| 维度 | Judge A mean | Judge B mean | Exact agreement | Within-one agreement |
| --- | ---: | ---: | ---: | ---: |
| P1 asked-for fit | 3.2667 | 3.1333 | 24/30 | 30/30 |
| P2 readable for them | 4.4667 | 4.3333 | 22/30 | 30/30 |
| P3 actionable | 2.9667 | 2.9333 | 25/30 | 30/30 |
| P4 gap handling | 3.2414（n=29） | 3.4000（n=30） | 19/29 | 28/29 |
| P5 overall | 3.2333 | 3.1000 | 24/30 | 30/30 |
| **全部共同数值判断** | — | — | **114/149 = 76.5%** | **148/149 = 99.3%** |

上表基于未经环境过滤的全部 30 个 raw cells，不是 12 个 `KEEP` cells 的 experience 汇总。可读性是最高维度，actionability 最低，与网页阻断、tab 容量以及缺少可核验 live page 的运行记录一致。没有任何 cell 达到完整原始任务 `judgement.score == 1.0`，所以“任务完美完成后 persona 是否仍然不满意”的预注册主切片目前为空。只有两个 cell 的 communicated-only score 为 1.0：budget/Kobe 和 cautious/accessories；它们的 P5 都是 `Judge A=4, Judge B=4`（满分 5），但前者完整任务只完成 `1/5`，后者只完成 `5/7`，不能称作原始任务完美完成。

#### 1.4 r1 的结构性限制

Minneapolis 任务要求保留约 15 个独立 listing tab 再加一个 CryptPad Sheet，而未修改的 main 固定 `MAX_TABS=8`。因此全部 5 个 Minneapolis cell 都受到 protocol-capacity censoring；即使网站完全可用，也不可能逐字满足同时保留全部 tab 的要求。

这个限制：

- 不计入 `EXCLUDE_RERUN`，因为用相同 main 配置重跑不能修复确定性的容量冲突；
- 不能全部归因给 execution model；
- 在跨 persona、跨 replicate 或跨版本解读 Minneapolis R2/R7 时必须单独标注。

#### 1.5 r1 证据与产物

- [r1 RUN_MANIFEST](2026-09-26/shopping-main-setting1-r1/RUN_MANIFEST.md)
- [冻结的六道 task](2026-09-26/shopping-main-setting1-r1/inputs/tasks.json)
- [冻结的 runtime 配置](2026-09-26/shopping-main-setting1-r1/inputs/runtime-config.json)
- [r1 完整结果审计](2026-09-26/shopping-main-setting1-r1/analysis/R1_RESULT_AUDIT.md)
- [环境有效性逐 cell 审计](2026-09-26/shopping-main-setting1-r1/analysis/ENVIRONMENT_VALIDITY_AUDIT.md)
- [机器可读环境有效性 ledger](2026-09-26/shopping-main-setting1-r1/analysis/ENVIRONMENT_VALIDITY_AUDIT.json)
- [dated post-hoc 分析](2026-09-26/shopping-main-setting1-r1/analysis/shopping-main-setting1-r1-formal-posthoc-2026-09-26.md)
- [repo-native experience 后报告](2026-09-26/shopping-main-setting1-r1/analysis/report-after-experience.txt)

### 2026-09-27：Version 1 / Setting 1 / r2

r2 的 grid 于 `2026-09-27T08:08:03Z` 开始，`10:07:49Z` 结束；30/30 个唯一 cell 均生成数值分数，没有 `error.txt`、provider/API 失败或重跑。两次 experience judge 也完成 30/30。

#### 1.6 原始 task completion（全部 30 个数值 cell）

| Arm | Kobe | Theory | Augusta | Minneapolis | UK 订阅 | 配件 | 6-task 宏平均 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `none` control | 0.400 | 0.250 | 0.200 | 0.250 | 1.000 | 0.714 | **0.4690** |
| Budget young parent | 0.200 | 0.250 | 0.000 | 0.125 | 0.000 | 0.571 | **0.1910** |
| Busy parent | 0.400 | 0.500 | 0.200 | 0.125 | 0.600 | 0.714 | **0.4232** |
| Cautious retiree | 0.200 | 0.750 | 0.000 | 0.125 | 0.200 | 0.714 | **0.3315** |
| Premium researcher | 0.600 | 0.500 | 0.200 | 0.125 | 0.600 | 0.714 | **0.4565** |

- cell/task-macro completion：`0.3742`；rubric-item micro：`63/170 = 0.3706`。
- communication coverage：cell-macro `0.7838`，micro `132/170 = 0.7765`。
- communicated-only completion：cell-macro `0.4512`，micro `62/132 = 0.4697`。
- 相对同 task 的 `none`，completion mean delta 分别为 budget `-0.278`、busy `-0.046`、cautious `-0.138`、premium `-0.013`。
- r2 首次出现完整原始 task 满分：`none × UK 订阅`，其 P5 为 Judge A `4`、Judge B `3`。

#### 1.7 环境有效性

逐 cell 审计结果为 `KEEP = 11/30`、`EXCLUDE_RERUN = 19/30`。环境保留子集仅覆盖 5 道 task，且 arm 极不平衡；其 cell-macro `0.429`、rubric micro `25/62 = 0.403`只能用作描述，不能当作环境校正后的总体估计。

r2 没有运行级 API 或 Chrome 失败；19 个排除来自已产生分数的 trajectory 中，required/communicated evidence 被 DNS、Access Denied、verification wall、持续 timeout 或不可操作页面实质阻断。它们保留为 raw observation，在 environment-valid 口径中视为无结果，不记为 agent execution failure。五个 Minneapolis cell 仍另外标记 `MAX_TABS=8` 结构性 censor。

#### 1.8 Persona experience judge（全部 30 个 raw cells）

| 维度 | Judge A mean | Judge B mean | Exact agreement | Within-one agreement |
| --- | ---: | ---: | ---: | ---: |
| P1 asked-for fit | 3.3000 | 3.2333 | 22/30 | 30/30 |
| P2 readable for them | 4.4333 | 4.4000 | 27/30 | 30/30 |
| P3 actionable | 2.9667 | 2.8667 | 19/30 | 30/30 |
| P4 gap handling | 3.2667（n=30） | 3.3793（n=29） | 18/29 | 29/29 |
| P5 overall | 3.2667 | 3.1667 | 23/30 | 30/30 |
| **全部共同数值判断** | — | — | **109/149 = 73.2%** | **149/149 = 100.0%** |

#### 1.9 r2 证据与产物

- [r2 RUN_MANIFEST](2026-09-27/shopping-main-setting1-r2/RUN_MANIFEST.md)
- [r2 环境有效性审计](2026-09-27/shopping-main-setting1-r2/analysis/ENVIRONMENT_VALIDITY_AUDIT.md)
- [r2 机器可读 validity ledger](2026-09-27/shopping-main-setting1-r2/analysis/ENVIRONMENT_VALIDITY_AUDIT.json)
- [r2 dated post-hoc 分析](2026-09-27/shopping-main-setting1-r2/analysis/shopping-main-setting1-r2-formal-posthoc-2026-09-27.md)
- [r2 repo-native experience 报告](2026-09-27/shopping-main-setting1-r2/analysis/report-after-experience.txt)

### 2026-09-27：Version 1 / Setting 1 / r3

r3 于 `2026-09-27T10:10:09Z` 开始，`12:04:23Z` 结束。30/30 个唯一 cell 均生成数值分数，没有 `error.txt`、provider/API 失败或重跑；30/30 也都完成两次 experience judgement。

#### 1.10 原始 task completion（全部 30 个数值 cell）

| Arm | Kobe | Theory | Augusta | Minneapolis | UK 订阅 | 配件 | 6-task 宏平均 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `none` control | 0.400 | 0.250 | 0.000 | 0.375 | 0.800 | 0.714 | **0.4232** |
| Budget young parent | 0.200 | 0.750 | 0.000 | 0.125 | 0.800 | 0.714 | **0.4315** |
| Busy parent | 0.200 | 0.250 | 0.200 | 0.125 | 0.600 | 0.714 | **0.3482** |
| Cautious retiree | 0.200 | 0.750 | 0.000 | 0.250 | 0.400 | 0.714 | **0.3857** |
| Premium researcher | 0.400 | 0.750 | 0.200 | 0.125 | 0.200 | 0.714 | **0.3982** |

- cell/task-macro completion：`0.3973`；rubric-item micro：`67/170 = 0.3941`。
- communication coverage：cell-macro `0.7588`，micro `128/170 = 0.7529`。
- communicated-only completion：cell-macro `0.5407`（28 个有定义的 cell），micro `65/128 = 0.5078`。
- 相对同 task 的 `none`，completion mean delta 分别为 budget `+0.008`、busy `-0.075`、cautious `-0.037`、premium `-0.025`。这些与 r1/r2 差异很大，不应单独用 r3 排 persona 名次。

#### 1.11 环境有效性与 experience

r3 逐 cell 审计为 `KEEP = 14/30`、`EXCLUDE_RERUN = 16/30`。KEEP 子集的 cell-macro `0.3742`、rubric micro `28/77 = 0.3636`；它在 task/persona 上仍严重不平衡，只能描述保留样本。全部 5 个 Minneapolis cell 另标记结构性 censor。

| 维度 | Judge A mean | Judge B mean | Exact agreement | Within-one agreement |
| --- | ---: | ---: | ---: | ---: |
| P1 asked-for fit | 3.2000 | 3.3333 | 22/30 | 30/30 |
| P2 readable for them | 4.3667 | 4.2667 | 23/30 | 30/30 |
| P3 actionable | 2.9333 | 3.0000 | 24/30 | 30/30 |
| P4 gap handling | 3.3667 | 3.3000 | 11/30 | 29/30 |
| P5 overall | 3.1333 | 3.1333 | 26/30 | 30/30 |
| **全部共同数值判断** | — | — | **106/150 = 70.7%** | **149/150 = 99.3%** |

r3 没有完整原始 task 满分 cell；communicated-perfect 有 5/30，但不能用它回答“原 task 完美完成后是否满意”。

#### 1.12 r3 证据与产物

- [r3 RUN_MANIFEST](2026-09-27/shopping-main-setting1-r3/RUN_MANIFEST.md)
- [r3 环境有效性审计](2026-09-27/shopping-main-setting1-r3/analysis/ENVIRONMENT_VALIDITY_AUDIT.md)
- [r3 机器可读 validity ledger](2026-09-27/shopping-main-setting1-r3/analysis/ENVIRONMENT_VALIDITY_AUDIT.json)
- [r3 dated post-hoc 分析](2026-09-27/shopping-main-setting1-r3/analysis/shopping-main-setting1-r3-formal-posthoc-2026-09-27.md)
- [r3 repo-native experience 报告](2026-09-27/shopping-main-setting1-r3/analysis/report-after-experience.txt)

### r1–r3 跨重复汇总

#### 1.13 完整性与原始结果

| Replicate | Raw numeric | Raw macro | Rubric micro | Coverage macro | Communicated-only macro | KEEP | EXCLUDE_RERUN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r1 | 30/30 | 0.3423 | 59/170 = 0.3471 | 0.7721 | 0.4045 | 12 | 18 |
| r2 | 30/30 | 0.3742 | 63/170 = 0.3706 | 0.7838 | 0.4512 | 11 | 19 |
| r3 | 30/30 | 0.3973 | 67/170 = 0.3941 | 0.7588 | 0.5407 | 14 | 16 |
| **合计/合并** | **90/90** | **0.3713** | **189/510 = 0.3706** | **0.7716** | **0.4644（n=87）** | **37** | **53** |

r1 另有 2 个历史 Chrome-launch error-only attempts；它们的目标 cell 后来用新 profile 成功产出分数，所以不是 90 个计划 cell 中的缺失值。r2/r3 没有错误 attempt。

合并 raw arm 结果：

| Arm | Cells | Completion mean | 相对 `none` 的 paired Δ | W / T / L | Rubric-micro communication coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `none` | 18 | **0.475** | — | — | 1.000 |
| Budget young parent | 18 | 0.308 | -0.166 | 1 / 6 / 11 | 0.637 |
| Busy parent | 18 | 0.344 | -0.131 | 2 / 6 / 10 | 0.725 |
| Cautious retiree | 18 | 0.300 | -0.175 | 2 / 4 / 12 | 0.471 |
| Premium researcher | 18 | 0.430 | -0.044 | 5 / 5 / 8 | 0.990 |

这个表的 paired delta 是 raw end-to-end signal，不是环境校正后的 persona 因果效应。`none` 的 3 个 KEEP cell 全是 UK 订阅题，因此能同时要求 `none` 与某 persona 都 KEEP 的 environment-valid paired support 实际上仅来自同一道 UK task。KEEP-only arm mean 不可直接横向排名。

#### 1.14 合并 experience 与两个 Persona factor

| 维度 | Judge A mean / median | Judge B mean / median | A `≥4` | B `≥4` | Exact | Within one |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 asked-for fit | 3.26 / 3 | 3.23 / 3 | 31/90 | 30/90 | 68/90 | 90/90 |
| P2 readable for them | 4.42 / 4 | 4.33 / 4 | 84/90 | 82/90 | 72/90 | 90/90 |
| P3 actionable | 2.96 / 3 | 2.93 / 3 | 27/90 | 25/90 | 68/90 | 90/90 |
| P4 gap handling | 3.29 / 3（n=89） | 3.36 / 3（n=89） | 32/89 | 36/89 | 48/88 | 86/88 |
| P5 overall | 3.21 / 3 | 3.13 / 3 | 33/90 | 27/90 | 73/90 | 90/90 |
| **全部共同数值判断** | — | — | — | — | **329/448 = 73.4%** | **446/448 = 99.6%** |

- Persona Factor 1：完整画像显著改变了 communication coverage，并伴随 raw completion 差异。premium 几乎保留全部 rubric，其 completion 也最接近 control；cautious 平均只传达 47.1% rubric，其完整 task score 低，但对已传达项的 micro completion 为 `29/48 = 0.604`。这说明“persona 影响完成度”中包含需求遗漏这条路径，不能只看最终 task score。
- Persona Factor 2：90 个 raw cell 中只有 1 个完整 task 满分（r2 `none × UK 订阅`，P5 A/B=`4/3`），没有具名 persona 的 full-task-perfect cell。因此“任务都完美完成后，不同 persona 是否仍有满意度差异”这个预注册主问题**当前无法回答**。11 个 communicated-perfect cell 的 P5 A/B 均值为 `3.91/3.73`，只是次级切片，不能替代 full-task-perfect 比较。
- Judge 一致性：A/B 是同一 Terra deployment 的重复采样。总体 within-one 很高，但 P4 的 exact agreement 只有 `48/88`，所以不应把单次 P4 当成高精度标签。

完整合并计算与机器可读输出见 [r1–r3 combined post-hoc](2026-09-27/shopping-main-setting1-r1-r3-combined-posthoc-2026-09-27.md) 及其 [JSON](2026-09-27/shopping-main-setting1-r1-r3-combined-posthoc-2026-09-27.json)。

## 2. 具体是怎么做的

### 2.1 代码与版本冻结

- 本文的 Version 1 指 `main@4a1c0f2` 的**核心执行与评测协议**：runner、persona runtime、agent/persona/judge prompts、原始 task judge 以及 Haoming person-side experience judge 逻辑。不能把它写成“全部使用 main 默认 setting”，因为模型兼容配置和实验输入都另有冻结记录。
- Shopping 实验输入 materialize 在 `6ea6482`：精确六题、四个 Shopping persona YAML 和生成器中的数据常量；没有修改 runner、tool loop、judge rubric 或打分逻辑。
- 本次 Version 1 / Setting 1 的 `r1–r3` 是独立的正式三重复。旧目录 `artifacts/shopping-version-1-main-4a1c0f2` 虽也使用 main-baseline 协议和同一六题，却是使用 `none` 加四个通用/旅行向 persona 的历史批次；它不是本次 r1 或 r0，也不并入本次 aggregate。
- Version 2 是 `main-shop` 分支的 `matched_pair_full_coverage.v1` 历史实验，以 `70e5443` 为代码来源参考，只有其独立 namespace 中的 r1（36 cells）。它与 Version 1 的 r1 标签不属于同一实验序列；历史结果及旧 V1/V2 比较保存在 `artifacts/shopping-results` 与 `SHOPPING_V1_V2_EVALUATION_REPORT.md`，不与本文结果合并统计。
- 每个日期/replicate 独立保存 manifest、完整输入快照、结果、日志和分析，避免切分支或网页随时间变化后无法复现。

### 2.2 Task 与 persona 的对应关系

采用完整笛卡尔积，而不是“一种人格只配一道题”：

```text
每个 replicate
  ├── none × 6 tasks
  ├── shopping-budget-young-parent × 6 tasks
  ├── shopping-cautious-retiree × 6 tasks
  ├── shopping-busy-parent × 6 tasks
  └── shopping-premium-researcher × 6 tasks
```

这使同一 task 内可以把 persona arm 与 `none` 配对比较，避免把 task/site 难度误当成 persona 效应。四个 persona 全部使用同一组 32 个 MatrAIx schema dimensions，只改变值；每个 profile 都与六题中已有的家庭/车辆事实兼容。

| Persona | 主要对比信号 | 为什么适合 Shopping 六题 |
| --- | --- | --- |
| Budget young parent | 预算敏感、手机优先、低耐心、快速决策 | 检验价格/促销、简洁表达，以及低耐心下是否漏掉硬约束 |
| Cautious retiree | 技术谨慎、风险规避、低视力、偏好稳妥证据 | 检验页面可读性、风险提示、复杂 tab 和下一步是否可操作 |
| Busy parent | deadline、家庭实用性、价值权衡、低耐心 | 与家庭车/多车配件等场景吻合，并检验有限时间内的信息取舍 |
| Premium researcher | 高细节、强研究、证据核验、质量优先 | 检验多来源、规格/fitment、premium choice 和复杂比较 |
| `none` | 原 task 原文 | 提供不经过 persona 改写/后续 persona reply 的配对基线 |

这里测的是四个具体、手工构造 profile prompt 的 bundle effect，不能外推为对应人口群体的平均表现。单一维度的因果归因属于另行设计的 Setting 2。

### 2.3 模型角色与 API 可用性

当日按配置好的 Azure endpoint 做了真实 API preflight；不含 credential/endpoint secret 的完整证据记录见 [2026-09-27 API / model preflight](2026-09-27/API_MODEL_PREFLIGHT.md)。为保持其余标准和 main 逻辑不变，只使用通过未修改 Chat Completions tool loop 的模型进行正式执行。

| 候选 | 当日 preflight | 正式使用决定 |
| --- | --- | --- |
| `gpt-5.6-terra` | HTTP 200；persona text、两轮 function-tool loop、judge JSON 均通过；API 返回模型 revision `gpt-5.6-terra-2026-07-09` | simulator、executor、task judge、experience judge A/B 全部固定使用；temperature 必须为 1 |
| `gpt-6-astra` | 普通文本与 judge 可用，但在未修改 main 的 Chat Completions function-tool 路径失败 | 不作为 executor；否则必须改 runner，违反本次冻结条件 |
| Claude Opus 5.5、Muse Spark 1.1、Gemini V4 Pro、Kimi-K3、Grok 4.7、MiniMax M3、GLM 5.3、Qwen 3.8 27B | 测试的 Azure deployment alias 均返回 404 DeploymentNotFound | 当日不可运行，不做无记录替换 |

当日没有配置可用的 OpenAI 或 OpenRouter credential，所以没有第二 provider。基于用户允许的 fallback，Terra 是唯一既可调用、又能在不改 main 逻辑前提下完成 browser tool loop 的正式 execution backbone。这个结果只说明当前 endpoint/deployment availability，不说明其他模型本身不支持该任务。

### 2.4 每个 replicate 的运行流程

1. 冻结精确 upstream Shopping task、4 个 persona YAML、4 份 prompt 和 runtime 配置，并记录 SHA-256。
2. 用 Terra preview 全部 `4 personas × 6 tasks = 24` 个 persona openings；检查硬约束没有改变、没有发明地点/预算/deadline、表达可区分且不泄露 profile/rubric。
3. 顺序运行 30 个 task × arm cell。persona simulator 生成 opening，并在 `ask_user` 时继续按 persona 回复；所以实验因素是完整 persona-mediated conversation，不只是第一句 paraphrase。
4. executor 在 live web 中运行，配置 `max_steps=50`、`MAX_TABS=8`、headless；原始 task judge 按冻结 rubric 判断每个 item 的 `met` 与 `communicated`。结果中的 `run.steps` 是记录的 tool-action 数，因 runner 的计数方式可高于配置值，不应把它误读成最多只有 50 条 trajectory 记录。
5. 每个 cell 再由 Terra 独立调用两次 experience judge，保留 A/B，不做平均替代原分。
6. 运行 repo-native report，再做 dated post-hoc 分析和逐 cell 环境有效性人工审计。
7. 环境阻断 cell 保留原 artifact，标记 `EXCLUDE_RERUN`，在同一 origin replicate 下做 configuration-matched environment reattempt；不得覆盖旧 attempt，也不得用独立的 r2/r3 回填 r1。只有复用实际 opening（并记录相同 opening hash）时，才进一步称为 frozen-opening re-execution；未冻结 opening 时不使用 “exact rerun”。

r1 运行中发现 Chrome 企业策略禁止复用已启动的 remote-debugging profile。首个共享 profile cell 成功后，两个后续 launch attempt 失败，因此 orchestration 改为**每个 cell 一个全新的 profile path**。`run.py`、prompt、工具逻辑和评分均未改动；两个失败 attempt 被保留，目标 cell 已成功重跑。r2/r3 继续使用每-cell新 profile，避免把已知启动策略问题重复引入实验。

### 2.5 日期与重复

- 正式设计为 3 个独立 replicate；每个 replicate 30 个 cell，已全部完成。
- 日期 block 取 grid/replicate invocation 在 America/Los_Angeles 的启动日期，跨午夜不自动移动已有目录。
- r1 位于 `2026-09-26`；r2、r3 位于 `2026-09-27` 各自目录。
- live-web 的库存、价格、页面结构和反机器人策略会变化，因此日期是实验 block，不能忽略。
- 本报告同时保留每个 replicate 和跨 replicate paired summary；不使用单一 replicate 做稳定人格排名。
- r1/r2/r3 的排除 cell 不互相回填。三次中 Theory、Edmunds、Cars.com、Sole Collector 和 Temu 的阻断重复出现，表明主要是持续性 site-level availability 问题；在环境变化前继续重新采样 opening 不能产生 r1 的环境修复值。

## 3. 评分标准是什么

### 3.1 Original task completion

每个 task 的冻结 rubric 有 `T_i` 个 item。task judge 对每个 item 分别判断：

- `met`：浏览/操作/最终交付是否满足该 item；
- `communicated`：persona-mediated conversation 是否明确要求了该 item。

设满足数为 `M_i`，communicated 数为 `C_i`，同时满足且 communicated 数为 `MC_i`：

```text
task completion score       = M_i / T_i
communication coverage      = C_i / T_i
communicated-only completion = MC_i / C_i   （C_i = 0 时无定义）
```

三者必须分栏报告。语气、人格、礼貌和文风不进入 original task completion；communicated-only completion 不能代替完整任务分数。

### 3.2 Persona Factor 1：对完成度的影响

同一 replicate、execution model 和 task 内，把每个具名 persona 与 `none` 做 paired comparison，报告：

- task score delta；
- communication coverage delta；
- communicated-only score delta；
- 哪些原始 rubric 被 persona 表达遗漏；
- clarification 数、steps 和 stop reason。

由于 main 中 persona 既改写 opening，也回答后续 `ask_user`，结果解释为完整 persona-mediated conversation effect，不宣称是纯 opening paraphrase 的因果效应。

### 3.3 Persona Factor 2：P1–P5 experience

每项为 1–5 或 `n/a`：

- P1 `asked_for`：是否交付此 persona 实际提出的内容；
- P2 `readable_for_them`：对这个 persona 是否易读；
- P3 `actionable`：能否凭回答和保留页面继续行动；
- P4 `gap_handling`：是否处理未明说但重要的缺口；
- P5 `overall`：这个 persona 是否总体被服务好。

优先报告分布、中位数、`score ≥ 4` 比例、A/B exact agreement 和 within-one agreement；均值仅作 repo-compatible 次级指标。主 satisfaction 切片限定为 `judgement.score == 1.0`。`score_communicated == 1.0` 是另一个次级切片，不能冒充“完整任务完美完成”。

### 3.4 环境有效性与失败分类

`result.json` 和数值 judge score 只证明 execution integrity，不自动证明该 cell 有公平的网页环境。正式结论使用以下分类：

- `KEEP`：环境足以完成 persona 实际要求；即使 agent 选错站、漏掉 rubric、没选尺寸、早停或没有尝试建表，也保留为 agent/protocol outcome。
- `EXCLUDE_RERUN`：403/Access Denied、CAPTCHA/Cloudflare、DNS、持续超时/崩溃、空页或不可操作页面实质阻断 required/communicated evidence。保存原 artifact，正式分析中不计分；环境恢复后在 origin replicate 下做 configuration-matched environment reattempt。
- Provider 层 429、无权限、无效 deployment/model ID 或不支持 tool call 同样属于无结果/基础设施失败，修复后做同规格 environment reattempt，不直接算 agent execution failure。
- 可恢复的瞬时错误、无关页面被阻断，或已有可访问且符合要求的替代来源，不足以自动排除。
- `MAX_TABS=8` 与 Minneapolis 任务的冲突是结构性 protocol limitation，单独标记为 censored，不与临时环境失败混为一类。

### 3.5 汇总规则

- 主 completion：task-balanced macro；次级报告 rubric-item micro。
- 每个汇总必须同时给 valid N、excluded N 和 exclusion rate。
- task completion、communication、persona experience、运行效率分别报告，**不构造一个加权总分**。
- persona effect 在同 task/replicate 内与 `none` 配对；跨 replicate 保留每次结果，再汇总 paired distribution。
- r1 的 18 个环境排除 cell 获得 environment-valid reattempt 前，不发布 environment-corrected 总体 Shopping 分数；r2/r3 的独立 replicate 结果不能填补这个空缺。
- 这四个 profile 每组只有一个手工实例，所以结论限定为 archetype-level bundle effect；不能写成某年龄、职业或收入人群的总体效果。

---

结论边界：三次 raw grid、两路 experience judge、逐 cell validity audit 和 dated post-hoc 均已完成；53 个环境排除仍需在站点可用时做 origin-replicate configuration-matched reattempt。当日只有 Terra 兼容未修改 main tool loop，因此本文没有 cross-model execution 结论。Setting 2 的单维度对照也不在本次 Setting 1 的 90-cell 范围内。
