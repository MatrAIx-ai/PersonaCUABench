# Food Persona 结果快照（2026-09-29 23:09 PDT）

分支：`codex/food-main-2026-09-28`。这是进行中的结果快照，不是三轮正式实验的最终结论。

| 重复 | 日期块 | 原始数值格 | 环境审计 | 体验 Judge A+B | 状态 |
| --- | --- | ---: | --- | --- | --- |
| r1 | 2026-09-28 | 30/30 | 25 KEEP、5 EXCLUDE_RERUN | 30/30 | 已完成审计，5 格网页环境阻断未解决 |
| r2 | 2026-09-29 | 30/30，另保留 2 个数值重跑尝试 | 30 格尚未最终分类 | 0/30 | 环境重跑／审计进行中 |
| r3 | 2026-09-29 | 0/30 | 尚未开始 | 尚未开始 | 已冻结输入，待运行 |

当前合计 60/90 个计划格有数值结果。请从 [Food HTML 结果页](../FOOD_MAIN_SETTING1_FORMAL_RESULTS.html) 查看当前汇总，并在引用分数时保留页面上的 `Preliminary / incomplete` 标记。r1 的已审计分析见 [FOOD_R1_FINAL.md](../2026-09-28/food-main-nocap-setting1-r1/analysis/FOOD_R1_FINAL.md)；每次尝试的原始 `result.json`、日志、输入快照和环境有效性记录都保存在各自的日期目录。旧的 cap-8 pilot 与正式 no-cap 网格分开保存。

本次另包含 [跨场景 Persona HTML 树](PERSONA_SCENARIO_TREE.html) 和 [Markdown 版](PERSONA_SCENARIO_TREE.md)。这两份图表整理的是人物与任务的设计关系，不是实验得分。

实验设置沿用 `main@4a1c0f2` 的任务、浏览器工具、提示词和评分逻辑；Food 正式网格仅将人工 tab 数上限设为 `ODYSSEY_MAX_TABS=0`。这一设置区别已写入 [实验计划](../../../FOOD_MAIN_EXPERIMENT_PLAN.md)。
