# Community / Beauty / Fitness Persona 选择计划

## 原则

- MatrAIx 当前提供的是结构化 persona schema 和采样器，不是固定人物名录；这里按 schema 组合可复现的 archetype。
- 每个任务选 3 个 persona，主要拉开年龄、教育、技术熟练度、领域经验、细节偏好和风险/隐私态度。
- 每个任务额外运行 `none` 控制组；3 个 persona 使用完全相同的维度集合，只改变取值。
- 不用性别、种族等与任务无关的属性制造差异。

## Persona 分配

| 任务 | Persona 1 | Persona 2 | Persona 3 | 主要对比 |
|---|---|---|---|---|
| Odysseys `2cb0ed2a5df6` Baltimore event night | `event-pro`：35–44，硕士，数字原生，酒店/活动策划经验，细节导向 | `young-casual-planner`：18–24，大学在读，数字原生，低耐心，只关心约会是否方便 | `older-city-visitor`：65–74，中学教育，技术谨慎，偏好简短说明 | 专业用户会明确“官网、URL、分标签页”；普通/年长用户可能只说想安排一晚，容易漏掉页面验证要求 |
| Odysseys `140960bb7293` Chapel Hill pantry loop | `community-organizer`：45–54，本科，长期志愿者，熟悉社区资源，细节高 | `keto-budget-shopper`：25–34，职业教育，技术熟练，低碳饮食、价格敏感 | `older-local-errand-runner`：65–74，中学教育，技术谨慎，只要实用路线 | 三者分别强调 pantry 真实性、Publix 肉食 BOGO、简单路线；跨域子任务的遗漏率应明显不同 |
| Odysseys `f979f723a3f6` Pokémon gift | `pokemon-collector`：13–17，中学阶段，数字原生，收藏/游戏兴趣高，熟悉商品名 | `practical-parent`：35–44，本科，技术舒适，预算与库存敏感，领域知识一般 | `gift-grandparent`：65–74，中学教育，技术勉强，对 Pokémon 陌生，风险规避 | 收藏者会精确说系列和版本；家长重价格/备选；祖辈可能只说“宝可梦卡礼物”，最可能触发追问 |
| Odysseys `d3250da48cc7` coordinated holiday bundle | `gift-stylist`：25–34，硕士，电商/设计经验，高审美、细节高 | `busy-budget-parent`：35–44，本科，家有未成年孩子，低耐心，重视价格和当日自提 | `traditional-grandparent`：65–74，中学教育，技术谨慎，家庭价值高，偏好线下购买 | 分别强调搭配完整性、预算/时效、礼物是否合适；多商店约束的表达完整度会不同 |
| Odysseys `e7596a6d6079` Colorado children outreach | `nonprofit-program-manager`：35–44，硕士，非营利行业资深，分析型、细节高 | `student-volunteer`：18–24，大学在读，数字原生，志愿服务热情但领域经验少 | `cautious-local-donor`：55–64，中学教育，技术谨慎，对机构和统计口径持验证态度 | 专业者会明确官网、项目名和收入口径；学生偏使命叙事；捐赠者更关心可信度和通俗结论 |
| Odysseys `946321e8a978` toddler Christmas + Grinch nails | `craft-beauty-creator`：25–34，本科，年轻孩子家长，手工/美妆经验高，视觉和细节导向 | `busy-first-time-parent`：25–34，职业教育，新手家长，低耐心，重视低脏乱和安全 | `caregiver-grandparent`：65–74，中学教育，照看孙辈，技术勉强，对网购美甲材料不熟 | 分别强调教程复现、幼儿安全省事、简单可执行；“幼儿活动”和“美甲产品”两部分权重会明显变化 |
| ClawBench `794` StyleSeat haircut booking | `beauty-power-user`：25–34，本科，数字原生，美妆行业/平台熟悉，风险平衡 | `budget-student-client`：18–24，大学在读，价格敏感，低耐心，倾向最快预约 | `low-tech-senior-client`：65–74，中学教育，技术勉强，信任度低、风险规避 | 对评分、价格、距离、最早时段及“直接提交预约”的容忍度不同，预期产生明显完成/满意度差异 |
| ClawBench `1102` Strava post | `strava-cyclist`：25–34，本科，骑行爱好者，社交媒体积极，数字原生 | `privacy-conscious-rider`：45–54，硕士，规律骑行，技术舒适但隐私价值高 | `older-fitness-beginner`：65–74，中学教育，偶尔锻炼，技术谨慎、反感社交媒体 | 同一句发帖需求下，三者对公开发布、受众范围和是否需要确认的态度差异最大 |

## 建模维度

所有 persona 共用一套核心维度：

`age_bracket`、`highest_education`、`life_stage`、`tech_savviness`、`socioeconomic_band`、`cog_detail_orientation`、`cog_patience`、`cog_precision_of_language`、`pref_detail_brief_vs_full`、`decision_style`、`risk_tolerance`、`trust_level`、`lstyle_shopping_style`、`skill_budgeting`。

按任务补充但仍保证同一任务的 3 人完全一致：

- Community：`val_community`、`topic_volunteering`、`lstyle_volunteering`、`lifex_service_history`、`ind_nonprofit`。
- 家庭/礼物：`val_family`、`demo_parental_status`、`lifex_parenting_journey`、`topic_collecting`、`lstyle_fashion_sense`。
- Beauty：`ind_beauty_cosmetics`、`val_beauty_aesthetics`、`trait_appreciation_of_beauty`。
- Fitness/Strava：`topic_fitness`、`topic_cycling`、`sport_cycling`、`lstyle_exercise_freq`、`topic_social_media`、`att_social_media`、`val_privacy`。

## 实施顺序

1. 把 6 个 Odysseys 完整任务按上述 Task ID 写入 `odyssey/tasks.json`；ClawBench 两项单独建 task adapter，避免混用不同执行环境。
2. 在 `make_personas.py` 中录入上述 profiles，并用 `dimensions.json` 校验所有取值。
3. 每个任务先运行 3 个 persona 的 `--preview`；检查表达是否明显不同，但核心需求不被改写。
4. 每个任务运行 `none + 3 personas`。比较 `score`、`score_communicated`、追问次数、完成步数和最终满意度。
5. 若 3 条 preview 只是语气不同、信息完整度近似，则优先调整 `tech_savviness`、领域经验、细节偏好、信任/风险和隐私态度，不随意增加无关人口属性。

参考：[MatrAIx Personas](https://matraix.ai/personas/)、[Odysseys 数据集](https://github.com/ljang0/Odysseys/blob/main/data/odysseys.json)、[ClawBench Tasks](https://claw-bench.com/tasks)。
