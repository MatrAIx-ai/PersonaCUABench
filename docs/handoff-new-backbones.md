# 扩大执行 backbone：交接手册

我们已经跑完 9 个执行 backbone，现在扩到 19 个。你只需要跑分给你的新模型，跑法和之前完全一样：s1 主实验，每个模型 370 个 cell。已有结果一律不动、不重跑。

## 1. 名单

**已完成，不要重跑：**

| 模型 | 注册表 key |
|---|---|
| Claude Opus 5.5 | `opus-5.5` |
| GPT 6 Astra | `gpt-6-astra` |
| Gemini 3.8 Flash | `gemini-3.8-flash` |
| Grok 4.6 | `grok-4.6` |
| Kimi K3 | `kimi-k3` |
| MiniMax M3 | `minimax-m3` |
| Muse Glimmer 30B | `muse-glimmer-30b` |
| Qwen 3.8 27B | `qwen3.8-27b` |
| DeepSeek V4.1 Flash | `deepseek-v4.1` |

**新增，要跑：**

| 模型 | 注册表 key | OpenRouter id | 价格（$/Mtok，输入/输出） | 一个模型 370 cell 预估 |
|---|---|---|---|---|
| Claude Fable 5.1 | `fable-5.1` | `anthropic/claude-fable-5.1` | 10 / 50 | **约 $2,500** |
| Claude Sonnet 5.5 | `sonnet-5.5` | `anthropic/claude-sonnet-5.5` | 2 / 10 | 约 $500 |
| Claude Haiku 5.5 | `haiku-5.5` | `anthropic/claude-haiku-5.5` | 0.10 / 0.50 | 约 $25 |
| GPT 6 Luna | `gpt-6-luna` | `openai/gpt-6-luna` | 0.10 / 0.50 | 约 $25 |
| GPT 6 Sol | `gpt-6-sol` | `openai/gpt-6-sol` | 2 / 10 | 约 $200–500 |
| GPT 5.6 Terra | `terra` | 走共享 Azure | 免费 | $0 |
| Muse Spark 1.3 | `muse-spark-1.3` | `meta/muse-spark-1.3` | 1.25 / 4.25 | 约 $300 |
| Gemini 3.7 Flash | `gemini-3.7-flash` | `google/gemini-3.7-flash` | 0.75 / 3.75 | 约 $190 |
| GLM 5.3 Flash | `glm-5.3-flash` | `z-ai/glm-5.3-flash` | 0.15 / 0.50 | 约 $36 |
| Qwen 3.8 Flash | `qwen3.8-flash` | `qwen/qwen3.8-flash` | 0.15 / 0.47 | 约 $36 |

预估来自 `python src/models.py --estimate 370`，按每个 cell 0.6M 输入、15k 输出计算。实际成本随步数变化很大，以第 5 节实测为准。GPT 5.5 不在测试范围内。

## 2. 固定不变的设置

下面这些和前 9 个模型完全一致，不要改：

- **Persona 模拟用户和所有 judge**：GPT 5.6 Terra，走共享 Azure。
- **执行模型的 reasoning effort**：新模型统一用 **medium**，已经写在 `src/models.json` 各条目的 `reasoning_effort` 字段里。不要删，也不要改。这个设置只作用于执行模型，persona 和 judge 不受影响。
- temperature 1.0，最多 100 步，最多追问 5 次。
- `SETTING=s1`，不设 `NUDGE`，每次都带 `JUDGE_B=off`。

## 3. 准备

```bash
git clone git@github.com:MatrAIx-ai/PersonaCUABench.git && cd PersonaCUABench
git checkout main && git pull
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cp .env.example .env
```

`.env` 里要填：

1. `azure_api_key.txt`：放共享 Azure 的 key，我们私下发给你。Persona、judge 和 `terra` 都靠它。
2. 执行模型的接口，二选一：
   - **用 OpenRouter**（默认）：填 `OPENROUTER_API_KEY`，不用改代码。
   - **用你们自己的 API**：见第 4 节。

跑 `muse-spark-1.3` 并且走 OpenRouter 的话，先在 <https://openrouter.ai/settings/preferences> 完成一次 18+ 确认，否则所有调用都会返回 403。

## 4. 接入你们自己的 API

新模型在注册表里只配了 OpenRouter 路由（`"endpoint": null`）。要换成你们自己的接口，在 `src/models.json` 对应条目里把 `endpoint` 填上：

```json
"sonnet-5.5": {
  "label": "Claude Sonnet 5.5",
  "endpoint": {
    "model": "你们 API 里的模型 id",
    "base_url_env": "SONNET_BASE_URL",
    "api_key_env": "SONNET_API_KEY",
    "key_required": true
  },
  ...
  "reasoning_effort": "medium"
}
```

然后在 `.env` 里填这两个变量。只要填了，就会优先走你们的接口，OpenRouter 只作为后备。变量名可以自己定。

**接口要求**：OpenAI 风格的 `POST /chat/completions`，带 `messages`、`tools`、`max_completion_tokens`，返回 `choices[0].message.tool_calls` 和 `usage`。

**effort 怎么传过去**：走你们自己的接口时，effort 以 OpenAI 的标准参数 `reasoning_effort: "medium"` 发送。如果你们的 API 用的是别的名字或格式，只需要改 `src/run.py` 里 `metered()` 中处理 effort 的那几行。不要在其他地方另加一套逻辑。

**接口不兼容时**：需要额外 header 或不同鉴权的，改 `src/run.py` 的 `_client()`；完全不是 OpenAI 格式的，参考 `src/responses_shim.py` 写一个转换层。`RUNNING.md` 的 "If your endpoint is not OpenRouter" 一节有完整说明。不管改了什么，都请告诉我们改了哪里。

## 5. 开跑前检查

任何一步失败都先停下，把输出发给我们，不要开始跑 grid。

```bash
bash scripts/check_all.sh                  # 必须打印 all offline checks passed
python src/models.py                       # 确认你的模型解析到了预期的路由
python scripts/check_models.py <key>       # 一次真实的两轮工具调用，花费约 0.1 美分
```

然后试跑三个 cell：

```bash
python src/run.py --suite odysseys --task 1 --persona none --model <key> --headless
python src/run.py --suite real --task 1 --persona none --model <key> --headless
python src/run.py --suite odysseys --task 1 --persona travel-senior --model <key> --headless
```

**确认 effort 真的生效了**。打开任意一个 `result.json`，`run_config.agent.reasoning_effort` 应该是 `"medium"`：

```bash
python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['run_config']['agent'].get('reasoning_effort'))" <result.json 路径>
```

跑 10–20 个 cell 后，运行 `python src/cost_report.py src/results/s1`，把平均每个 cell 的成本发给我们，再继续跑完。Fable 5.1 尤其要先报成本。

## 6. 跑 grid

```bash
DRY_RUN=1 JUDGE_B=off SETTING=s1 MODELS="<key>" JOBS=4 bash src/run_all.sh   # 先只列出 cell，应为 370 个
JUDGE_B=off SETTING=s1 MODELS="<key>" JOBS=4 bash src/run_all.sh
```

- 每个 worker 约占 1.5 GB 内存，Chrome 崩溃就调小 `JOBS`。
- 可以重复运行：已完成的 cell 会跳过，中断后原样重跑同一条命令即可续上。
- `terra` 作为执行模型走的是共享 Azure，和所有人的 persona、judge 共用限流。跑 `terra` 时 `JOBS` 不要超过 2。

## 7. 跑完之后

```bash
python src/simulator_satisfaction.py --results src/results/s1 --workers 8
python src/report.py src/results/s1 --suite odysseys
python src/report.py src/results/s1 --suite real
python src/report_simulator_satisfaction.py src/results/s1
python src/cost_report.py src/results/s1 --csv cells.csv
```

上传到共享 Google Drive 时，**每个模型的结果先打成一个压缩包再传**，不要直接拖整个目录。上一批直接上传的目录里，有 334 个 `result.json` 大小恰好是 256 KiB，6 个模型的 `shots/` 整批不在 Drive 上。

```bash
tar -czf s1-<key>-$(date +%Y%m%d).tar.gz src/results/s1 logs cells.csv
```

`src/results/` 已被 gitignore，不要提交到 git，也不要删减里面的内容。

## 8. 常见问题

| 现象 | 处理 |
|---|---|
| `models.py` 显示 `(x)` | 那条路由的变量没填 |
| `check_models.py` 失败，模型只回了文字 | 模型没调用工具，或接口的 tool call 格式不兼容，见第 4 节 |
| OpenRouter 返回 `403 ... 18+` | 账号没做 18+ 确认，见第 3 节 |
| `run_config.agent.reasoning_effort` 不是 `medium` | 不要继续跑，把 `result.json` 发给我们 |
| cell 显示 `UNJUDGED (...)` | 结果已保存，用 `python src/judge_all.py src/results/s1` 补判 |
| cell 停在 `max_steps` | 正常，记下来即可，不要调高上限 |

十分钟内解释不了的问题，把 `logs/cells/` 里对应的日志和 `result.json` 发给我们。
