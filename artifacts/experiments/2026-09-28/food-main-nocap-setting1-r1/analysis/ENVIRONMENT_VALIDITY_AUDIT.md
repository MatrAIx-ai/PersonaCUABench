# Food r1 environment-validity audit — final freeze

Environment-decision audit timestamp: `2026-09-30T02:07:40.859Z`. SHA-256 provenance refresh: `2026-09-30T02:22:31.389Z`. Latest numeric grid: **30/30** selected cells. Final environment overlay: **KEEP 25 / EXCLUDE_RERUN 5 / unclassified 0**.

> Final-freeze interpretation: `EXCLUDE_RERUN` is the status name required by `food_main_setting1_analysis.py`. The five cells below are **retry-exhausted persistent exclusions**, not new rerun requests. Additional reruns requested: **0**.

## Post-freeze provenance refresh

Experience Judge A/B outputs were written into all 30 selected `result.json` files after the environment audit. This changed file bytes—and therefore every SHA-256—but did not change the selected task/persona/model paths or any environment-validity decision.

- Audit version: **4** (provenance-only refresh from version 3).
- Selected paths changed: **0**.
- Selected result hashes refreshed: **30**.
- Environment decisions changed: **0**.
- Status counts changed: **0**.
- The hashes in the ledger and persistent-exclusion detail below are the current post-Experience-Judge hashes.

## Decision rule

- `KEEP`: no material, unrecovered environment obstruction prevented required or persona-communicated evidence. Recovered errors, persona omission, weak source choice, incomplete navigation, and early stopping remain genuine execution outcomes.
- `EXCLUDE_RERUN`: a site/provider denial, verification wall, or unusable required page materially prevented required or persona-communicated evidence and no usable alternate evidence recovered it.
- Score does not determine environment validity. The raw score is never changed by this audit.
- Environment impact is kept narrower than the full set of unmet rubrics; mixed agent/navigation misses are not attributed to the environment.

## Selection and attempt counts

| Measure | Count |
| --- | ---: |
| Attempt directories discovered | 47 |
| Numeric scored attempts discovered | 42 |
| Latest numeric scored cells selected | 30 |
| Older duplicate numeric attempts | 12 |
| Historical error-only attempts | 5 |
| KEEP cells | 25 |
| Retry-exhausted EXCLUDE_RERUN cells | 5 |
| Additional reruns requested | 0 |

## Counts by task

| Task | Task ID prefix | KEEP | EXCLUDE_RERUN |
| ---: | --- | ---: | ---: |
| 1 | `082aa17f3e88` | 5 | 0 |
| 2 | `0ab48db60760` | 5 | 0 |
| 3 | `eb8a01554a84` | 5 | 0 |
| 4 | `5944875c7f32` | 5 | 0 |
| 5 | `18ddad3e0781` | 2 | 3 |
| 6 | `e20742e26a4d` | 3 | 2 |

## Latest 30-cell selection ledger

Every row is the exact latest scored attempt selected by the same timestamp/path tie-break used by `food_main_setting1_analysis.py`. `Attempts` counts numeric scored attempts reviewed for that cell. Full per-cell evidence and the machine-readable status live in the paired JSON audit.

| Task | Arm | Status | Attempts | Score / communicated | Steps / stop | Unmet communicated | Environment-impacted | Selected result | Current SHA-256 |
| ---: | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| 1 | Control (`none`) | **KEEP** | 1 | 0.75 / 0.75 | 20 / `no_tool_call` | R3 | — | `results/082aa17f3e88/none__gpt-5.6-terra__20260928T213351Z/result.json` | `63ca8330faf8a5ad1c47ef7ad78a73bb587e1b6b1617286884224c504e7af96b` |
| 1 | P1 Budget Novice (`food-budget-novice`) | **KEEP** | 1 | 1 / 1 | 14 / `no_tool_call` | — | — | `results/082aa17f3e88/food-budget-novice__gpt-5.6-terra__20260928T215230Z/result.json` | `abb0a2609f404b7681c30b06896c499aec0749da3e52823098999f98345646ef` |
| 1 | P2 Cautious Dietary Planner (`food-cautious-dietary-planner`) | **KEEP** | 1 | 0.75 / 0.75 | 31 / `finish` | R3 | — | `results/082aa17f3e88/food-cautious-dietary-planner__gpt-5.6-terra__20260928T223839Z/result.json` | `bde583605d92081150b3a40a109e32fc1fa4cb57ec0df747124f675e86ebef17` |
| 1 | P3 Busy Host (`food-busy-host`) | **KEEP** | 1 | 1 / 1 | 20 / `finish` | — | — | `results/082aa17f3e88/food-busy-host__gpt-5.6-terra__20260928T221632Z/result.json` | `73c53df65b24c92d624cf1ed7ce6616f06b5d83aa1ead29f5f629bcff1512837` |
| 1 | P4 Culinary Researcher (`food-culinary-researcher`) | **KEEP** | 1 | 1 / 1 | 17 / `finish` | — | — | `results/082aa17f3e88/food-culinary-researcher__gpt-5.6-terra__20260930T001448Z/result.json` | `0a2ad690d2ae4625065b3fe8e7e8c16b746b93e8a6fbbd3492cf196c437a1413` |
| 2 | Control (`none`) | **KEEP** | 1 | 0.75 / 0.75 | 18 / `finish` | R2 | — | `results/0ab48db60760/none__gpt-5.6-terra__20260928T213759Z/result.json` | `6da41ddd7352d23dd2146b7b4438dbec2271bf0f51ff1f1f920eb5f1a0fe7cd8` |
| 2 | P1 Budget Novice (`food-budget-novice`) | **KEEP** | 1 | 0.75 / 1 | 16 / `finish` | — | — | `results/0ab48db60760/food-budget-novice__gpt-5.6-terra__20260928T215600Z/result.json` | `bf8f4ab31f616f2878f79381810b86b578b134a43a38576dc5c1a950c3303822` |
| 2 | P2 Cautious Dietary Planner (`food-cautious-dietary-planner`) | **KEEP** | 1 | 0.75 / 0.667 | 21 / `finish` | R2 | — | `results/0ab48db60760/food-cautious-dietary-planner__gpt-5.6-terra__20260928T224615Z/result.json` | `68ee629c39ffa598338bb411580f7f89c0a78621350688d610de46c751e2b5f0` |
| 2 | P3 Busy Host (`food-busy-host`) | **KEEP** | 1 | 0.75 / 0.667 | 14 / `finish` | R2 | — | `results/0ab48db60760/food-busy-host__gpt-5.6-terra__20260928T222253Z/result.json` | `c8464e344bba4154bd95af70271fb402fea7e3b60e3cb2be3830755e55072a6d` |
| 2 | P4 Culinary Researcher (`food-culinary-researcher`) | **KEEP** | 1 | 0.75 / 0.75 | 27 / `finish` | R2 | — | `results/0ab48db60760/food-culinary-researcher__gpt-5.6-terra__20260930T001857Z/result.json` | `f2c0ee3e9f9d75b48ab0c531e4494866e9ccfa0776fa786c1b06cf4a045d0045` |
| 3 | Control (`none`) | **KEEP** | 1 | 1 / 1 | 30 / `finish` | — | — | `results/eb8a01554a84/none__gpt-5.6-terra__20260928T213944Z/result.json` | `9ad939a28e65e75a3b343e74ded5b68baac32bfbb420de6623b93a34346da511` |
| 3 | P1 Budget Novice (`food-budget-novice`) | **KEEP** | 1 | 0.75 / 1 | 19 / `finish` | — | — | `results/eb8a01554a84/food-budget-novice__gpt-5.6-terra__20260928T215739Z/result.json` | `e08ae7bf3a7f483f42ffe4946318a95737c445e74b14a21e187d90f32ac148e8` |
| 3 | P2 Cautious Dietary Planner (`food-cautious-dietary-planner`) | **KEEP** | 1 | 0.75 / 1 | 23 / `finish` | — | — | `results/eb8a01554a84/food-cautious-dietary-planner__gpt-5.6-terra__20260928T224952Z/result.json` | `d265a2a567a8ac6a539c2c654a887a126a045cdb2b65713a71103dc45131992f` |
| 3 | P3 Busy Host (`food-busy-host`) | **KEEP** | 1 | 0.75 / 1 | 11 / `finish` | — | — | `results/eb8a01554a84/food-busy-host__gpt-5.6-terra__20260928T222426Z/result.json` | `76c924ff7f068d6759ce0e10258dcebd8f99c7e7dc954bd9f684d92ffef42c6c` |
| 3 | P4 Culinary Researcher (`food-culinary-researcher`) | **KEEP** | 1 | 0.25 / 0.333 | 19 / `finish` | R1, R2 | — | `results/eb8a01554a84/food-culinary-researcher__gpt-5.6-terra__20260930T002222Z/result.json` | `a2f4542e289dd4c273734ff5624555b944ac4105d56e10fde7c6ee434f14625b` |
| 4 | Control (`none`) | **KEEP** | 1 | 0.714 / 0.714 | 16 / `no_tool_call` | R4, R6 | — | `results/5944875c7f32/none__gpt-5.6-terra__20260928T214437Z/result.json` | `a9761a770cda35fb18fc16aa11378172ccc3258061696f2a4197431034a55026` |
| 4 | P1 Budget Novice (`food-budget-novice`) | **KEEP** | 1 | 0.571 / 0.667 | 20 / `no_tool_call` | R4, R6 | — | `results/5944875c7f32/food-budget-novice__gpt-5.6-terra__20260928T220250Z/result.json` | `8eee54c205755023d507b3fd26152fb39af13c881c06d8f9b797a05daa22efb1` |
| 4 | P2 Cautious Dietary Planner (`food-cautious-dietary-planner`) | **KEEP** | 1 | 0.571 / 0.8 | 20 / `no_tool_call` | R2 | — | `results/5944875c7f32/food-cautious-dietary-planner__gpt-5.6-terra__20260928T225616Z/result.json` | `c61f5006eab68da00dc3c789ae9a860a36e863a182fb83c00e196b847711c30f` |
| 4 | P3 Busy Host (`food-busy-host`) | **KEEP** | 1 | 0.429 / 0.75 | 19 / `finish` | R7 | — | `results/5944875c7f32/food-busy-host__gpt-5.6-terra__20260928T222734Z/result.json` | `6d7d2860bc4c2912652617ddeae2440dbe3ef3b2dbba96185a448683c41bb8de` |
| 4 | P4 Culinary Researcher (`food-culinary-researcher`) | **KEEP** | 2 | 0.857 / 1 | 32 / `no_tool_call` | — | — | `results/5944875c7f32/food-culinary-researcher__gpt-5.6-terra__20260930T003947Z/result.json` | `6bd961ca2eff451f71f38f78aafe91b6c9f94486bfcb3484fa4d1c341018bb94` |
| 5 | Control (`none`) | **EXCLUDE_RERUN** (exhausted) | 3 | 0.25 / 0.25 | 26 / `finish` | R2, R3, R4 | R2 | `results/18ddad3e0781/none__gpt-5.6-terra__20260930T013337Z/result.json` | `244749edeec428132448e601482e36adebc787544da35276b1c77e863fb23229` |
| 5 | P1 Budget Novice (`food-budget-novice`) | **EXCLUDE_RERUN** (exhausted) | 3 | 0 / 0 | 29 / `finish` | R3, R4 | R4 | `results/18ddad3e0781/food-budget-novice__gpt-5.6-terra__20260930T013620Z/result.json` | `d5d3d9fa0da256b108a8db3d5f15a8764b2e1ec247ea355589b5708bc5b82281` |
| 5 | P2 Cautious Dietary Planner (`food-cautious-dietary-planner`) | **EXCLUDE_RERUN** (exhausted) | 3 | 0.25 / 0.333 | 28 / `finish` | R3, R4 | R3, R4 | `results/18ddad3e0781/food-cautious-dietary-planner__gpt-5.6-terra__20260930T014204Z/result.json` | `abaa294e6b542451472c428fc5ed0b973bf73747d1c99314cbe58f352e146396` |
| 5 | P3 Busy Host (`food-busy-host`) | **KEEP** | 1 | 0.25 / 0.333 | 26 / `finish` | R1, R4 | — | `results/18ddad3e0781/food-busy-host__gpt-5.6-terra__20260928T222943Z/result.json` | `19bacaea45eb0b1848e458ab1b029c889ff065c3786d182b2cae09290493cbbb` |
| 5 | P4 Culinary Researcher (`food-culinary-researcher`) | **KEEP** | 2 | 0.75 / 1 | 42 / `finish` | — | — | `results/18ddad3e0781/food-culinary-researcher__gpt-5.6-terra__20260930T010127Z/result.json` | `c2046f001e5462c65f266852cb94791ad6b5054b5523349120fd74748099668e` |
| 6 | Control (`none`) | **EXCLUDE_RERUN** (exhausted) | 3 | 0.571 / 0.571 | 54 / `finish` | R1, R3, R5 | R3 | `results/e20742e26a4d/none__gpt-5.6-terra__20260930T014627Z/result.json` | `d8f15cfda7a65340e32a242b8032da2c8bb8abebfc838834cd3c07061d0cd851` |
| 6 | P1 Budget Novice (`food-budget-novice`) | **KEEP** | 1 | 0 / 0 | 13 / `finish` | R7 | — | `results/e20742e26a4d/food-budget-novice__gpt-5.6-terra__20260928T221359Z/result.json` | `199478555433ac2453bacc63d5c13b78087195ab0080fadd9590760f3f402c71` |
| 6 | P2 Cautious Dietary Planner (`food-cautious-dietary-planner`) | **KEEP** | 1 | 0.286 / 0.4 | 35 / `no_tool_call` | R1, R4, R5 | — | `results/e20742e26a4d/food-cautious-dietary-planner__gpt-5.6-terra__20260930T001048Z/result.json` | `a25ae9aa7d2eff5fa825d183012ea6c612b0406e94d690cfe3d9666cd8ac38c9` |
| 6 | P3 Busy Host (`food-busy-host`) | **KEEP** | 1 | 0.429 / 1 | 21 / `finish` | — | — | `results/e20742e26a4d/food-busy-host__gpt-5.6-terra__20260928T223341Z/result.json` | `46878c632494d1b5a5198e4b98102ac038e2d88e19ff501032e08c9ce88e9948` |
| 6 | P4 Culinary Researcher (`food-culinary-researcher`) | **EXCLUDE_RERUN** (exhausted) | 3 | 0.429 / 0.429 | 57 / `finish` | R3, R4, R5, R6 | R3 | `results/e20742e26a4d/food-culinary-researcher__gpt-5.6-terra__20260930T015630Z/result.json` | `78907d7eeea072480db6b482e9d1facb1e76ed0203785793f5c3a5104422845d` |

## Persistent unresolved cells after retry exhaustion

Each of these five cells has three numeric scored attempts (initial run plus two same-configuration retries). The latest attempt is frozen below; no further retry is requested.

### Task 5 — Control

- Status: **EXCLUDE_RERUN / EXHAUSTED_UNRESOLVED**; additional rerun requested: **no**.
- Latest result: `results/18ddad3e0781/none__gpt-5.6-terra__20260930T013337Z/result.json`
- Current SHA-256: `244749edeec428132448e601482e36adebc787544da35276b1c77e863fb23229`
- Numeric scored attempts reviewed: **3**; latest score: **0.25**; communicated score: **0.25**.
- Unmet communicated rubrics: R2, R3, R4. Environment-impacted rubrics: **R2**.
- Material blocker: Date-specific OpenTable search returned Access Denied; Mamma Maria and Grill 23 OpenTable listings returned Access Denied.
- Evidence: Final-freeze attempt steps 0 and 4: the date-specific OpenTable search and both the Mamma Maria and Grill 23 OpenTable listings returned Access Denied; step 6 date-specific booking endpoints also returned provider errors. Official sites, Maps, and a default-date SevenRooms view recovered restaurant context but not the visibly open OpenTable listing required by R2.
- Causal decision: Communicated R2 explicitly requires an open OpenTable listing, so the unrecovered source-specific block independently invalidates the cell. R3/R4 also remained unmet, but are not attributed to environment here because their availability gaps are mixed with navigation. The third scored attempt remains unresolved.

### Task 5 — P1 Budget Novice

- Status: **EXCLUDE_RERUN / EXHAUSTED_UNRESOLVED**; additional rerun requested: **no**.
- Latest result: `results/18ddad3e0781/food-budget-novice__gpt-5.6-terra__20260930T013620Z/result.json`
- Current SHA-256: `d5d3d9fa0da256b108a8db3d5f15a8764b2e1ec247ea355589b5708bc5b82281`
- Numeric scored attempts reviewed: **3**; latest score: **0**; communicated score: **0**.
- Unmet communicated rubrics: R3, R4. Environment-impacted rubrics: **R4**.
- Material blocker: Date-specific Mare OpenTable listing returned Access Denied.
- Evidence: Final-freeze attempt steps 3–4: Mare's official reservation page explicitly routes booking through OpenTable, while the date-specific Mare OpenTable URL returned Access Denied; another official booking click still exposed no inventory. A Mamma Maria SevenRooms check concerned a backup, not selected Mare, and therefore did not recover R4.
- Causal decision: The provider block cleanly censors the availability component of communicated R4. R3/Ostra remains mixed with widget navigation, and uncommunicated R1/R2 are not environment grounds. The third scored attempt remains unresolved.

### Task 5 — P2 Cautious Dietary Planner

- Status: **EXCLUDE_RERUN / EXHAUSTED_UNRESOLVED**; additional rerun requested: **no**.
- Latest result: `results/18ddad3e0781/food-cautious-dietary-planner__gpt-5.6-terra__20260930T014204Z/result.json`
- Current SHA-256: `abaa294e6b542451472c428fc5ed0b973bf73747d1c99314cbe58f352e146396`
- Numeric scored attempts reviewed: **3**; latest score: **0.25**; communicated score: **0.333**.
- Unmet communicated rubrics: R3, R4. Environment-impacted rubrics: **R3, R4**.
- Material blocker: Grill 23 and Ostra OpenTable listings returned Access Denied; SevenRooms/Resy alternatives were unusable and official booking controls exposed no inventory.
- Evidence: Final-freeze attempt step 2: the selected Grill 23 and Ostra OpenTable listings both returned Access Denied. Their official booking controls exposed no inventory; the attempted Grill 23 SevenRooms and Ostra Resy alternatives were not found. Official pages and Maps recovered fit and price context, but no selectable next-two-day inventory.
- Causal decision: The direct booking-provider blocks materially censor the availability requirements in communicated R3 and R4. Uncommunicated R2 is not used. The third scored attempt remains unresolved.

### Task 6 — Control

- Status: **EXCLUDE_RERUN / EXHAUSTED_UNRESOLVED**; additional rerun requested: **no**.
- Latest result: `results/e20742e26a4d/none__gpt-5.6-terra__20260930T014627Z/result.json`
- Current SHA-256: `d8f15cfda7a65340e32a242b8032da2c8bb8abebfc838834cd3c07061d0cd851`
- Numeric scored attempts reviewed: **3**; latest score: **0.571**; communicated score: **0.571**.
- Unmet communicated rubrics: R1, R3, R5. Environment-impacted rubrics: **R3**.
- Material blocker: The Kitchn baked-ham and spiral-ham articles returned human-verification Access Denied.
- Evidence: Final-freeze attempt steps 10 and 16: both The Kitchn baked-ham and spiral-ham articles displayed Access Denied / Please verify you are a human. Search-result snippets and alternate engines recovered only partial index text, not a visible Kitchn article; the final answer explicitly disclosed that limitation.
- Causal decision: Communicated R3 requires preparation, heating, and finishing guidance verified from a visible The Kitchn article. The persistent anti-automation wall independently censors that evidence. R1/R5 are separate source-selection outcomes. The third scored attempt remains unresolved.

### Task 6 — P4 Culinary Researcher

- Status: **EXCLUDE_RERUN / EXHAUSTED_UNRESOLVED**; additional rerun requested: **no**.
- Latest result: `results/e20742e26a4d/food-culinary-researcher__gpt-5.6-terra__20260930T015630Z/result.json`
- Current SHA-256: `78907d7eeea072480db6b482e9d1facb1e76ed0203785793f5c3a5104422845d`
- Numeric scored attempts reviewed: **3**; latest score: **0.429**; communicated score: **0.429**.
- Unmet communicated rubrics: R3, R4, R5, R6. Environment-impacted rubrics: **R3**.
- Material blocker: The Kitchn spiral-ham article returned human-verification Access Denied.
- Evidence: Final-freeze attempt step 7: following the search result to The Kitchn's spiral-ham comparison article immediately produced human verification / automation denial. The answer therefore relied on search-result summary text rather than a visible article; no open tab recovered the article body.
- Causal decision: Communicated R3 requires visible Kitchn article guidance, and the third scored attempt still could not access it. R4/R5/R6 remain separate product-page and navigation outcomes. The third scored attempt remains unresolved.

## Validation

Command:

```bash
.venv/bin/python artifacts/experiments/food_main_setting1_analysis.py \
  artifacts/experiments/2026-09-28/food-main-nocap-setting1-r1 \
  --output-prefix /tmp/food-r1-post-experience-hash-validation
```

Observed output:

```text
selected_numeric_scored_cells=30 execution_integrity_excluded_attempts=17 error_attempts=5
environment_keep_cells=25 environment_exclude_rerun_cells=5 environment_unclassified_selected_numeric_cells=0
```

A separate integrity check confirmed all 30 selected paths exist and every recorded SHA-256 exactly matches the current file bytes. The latest selection paths are unchanged.

## Freeze and artifact integrity

- Freeze status: `CLOSED_AFTER_RETRY_EXHAUSTION`.
- The all-numeric 30-cell result remains separate from the 25-cell KEEP-only environment overlay.
- This provenance refresh changed only `ENVIRONMENT_VALIDITY_AUDIT.json` and this Markdown rendering.
- It did not modify raw results, trajectories, persona profiles, `run.py`, secrets, or `RUN_MANIFEST.json`.
- Post-freeze annotations that change `result.json` bytes require another hash-only provenance refresh. A future numeric attempt that changes latest selection requires a new full environment audit.
