# r2 environment-validity adjudication — DRAFT before retries

Generated: `2026-09-30T05:40:16Z`

This is a reviewer draft for the original 30-cell r2 grid. It is **not** the
final environment-validity audit and must not be used as the final KEEP-only
overlay. A final audit must be regenerated after matched retries and must hash
the final selected `result.json` files.

## Integrity

- Expected grid: 30 cells (6 tasks × 5 arms).
- Latest numeric cells present: 30/30.
- Duplicate numeric cells at this snapshot: 0.
- Schema-invalid numeric cells: 0.
- Historical error-only attempts at this snapshot: 0.

## Review rule

Recommend `RERUN` only when a concrete external environment signal—such as an
Access Denied page, human-verification wall, Google unusual-traffic page, DNS
failure, or actual target-page navigation failure—materially caused a rubric
that the persona utterance communicated to remain unmet, and the run did not
recover for that requirement. A low score, hidden requirement omitted by a
persona paraphrase, wrong URL, stale redirect, failure to open an available
alternative, or generic click/navigation strategy problem is `KEEP`.

## Exact matched-rerun list (10 cells)

1. T3 `eb8a01554a84` / `none` — `RERUN`; impacted `R3`. The Google Instant
   Pot mulligatawny search returned `/sorry/`; the recipe was reached only via
   DuckDuckGo. The judge explicitly identified this blocked Google route as
   the remaining R3 defect.
2. T3 `eb8a01554a84` / `food-busy-host` — `RERUN`; impacted `R3`. The Google
   mulligatawny search returned unusual-traffic verification; the actual
   Feasting at Home recipe and its ingredients/steps were otherwise present.
3. T3 `eb8a01554a84` / `food-culinary-researcher` — `RERUN`; impacted `R3`.
   The Google mulligatawny search was blocked; the actual Simply Happy Foodie
   page and recipe content were recovered through DuckDuckGo, leaving only the
   required Google provenance unmet. The separate R1 miss is not attributed to
   the environment.
4. T4 `5944875c7f32` / `none` — `RERUN`; impacted `R1`. The initial Google BOTW
   guide search returned `/sorry/`, so the complete Game8 guide was reached by
   DuckDuckGo. R2–R7 passed.
5. T4 `5944875c7f32` / `food-budget-novice` — `RERUN`; impacted `R1`. The Google
   BOTW search was blocked; the eventual Game8/IGN guide came from fallback
   search. The Sally's omission is a separate execution/persona-paraphrase
   outcome and is not an environment exclusion reason.
6. T4 `5944875c7f32` / `food-cautious-dietary-planner` — `RERUN`; impacted
   `R1`. The complete Game8 guide was opened after DuckDuckGo because the
   Google search returned `/sorry/`; the judge identified exactly that route
   mismatch.
7. T5 `18ddad3e0781` / `none` — `RERUN`; impacted `R2`. The Mare OpenTable
   search/listing pages returned explicit `Access Denied`, so the communicated
   OpenTable evidence could not be preserved. R3 and R4 recovered through
   official/Tock pages.
8. T5 `18ddad3e0781` / `food-cautious-dietary-planner` — `RERUN`; impacted
   `R3`. Grill 23's booking path routed to OpenTable, whose listing returned
   explicit `Access Denied`; the answer consequently could not verify four-seat
   availability for the next two days. Mamma Maria's separate SevenRooms check
   recovered R4.
9. T6 `e20742e26a4d` / `none` — `RERUN`; impacted `R3`. The Kitchn search page
   and two specific spiral-ham article URLs all returned human-verification /
   automation-denied pages. The answer explicitly declined to claim a verified
   Kitchn method.
10. T6 `e20742e26a4d` / `food-culinary-researcher` — `RERUN`; impacted `R3`.
    The specific Kitchn spiral-ham article returned an automation-denied page;
    the answer explicitly said it could not extract the preparation, heating,
    and finishing method. R7 is a downstream content consequence, while R4/R5
    have independent execution defects.

## Material false positives kept (10 reviewed candidates)

- T1 / `food-cautious-dietary-planner` — `KEEP`: Google was blocked for the
  recipe search, but R1/R2/R4 passed; R3 failed only because video playback was
  not started.
- T2 / `none` — `KEEP`: Google fallback recovered the required pages; R2 failed
  only because the final answer shortened the exact chili title.
- T2 / `food-busy-host` — `KEEP`: R1–R3 were not communicated by the persona
  paraphrase; communicated R4 failed because the agent selected non–Feel Good
  Foodie dessert URLs, not because of the environment.
- T2 / `food-cautious-dietary-planner` — `KEEP`: fallback recovered every
  required page; R2 failed only because the final answer shortened the exact
  title.
- T4 / `food-busy-host` — `KEEP`: the Dole Whip defect followed a guessed URL
  that resolved to a 404 despite usable search results; the mirroring defect
  followed an Apple deep link that recovered by redirecting to a generic guide.
  Neither communicated miss is materially caused by the earlier transient
  `Page.goto` timeouts.
- T5 / `food-budget-novice` — `KEEP`: the Mooncusser defect followed a generic
  Michelin booking-partnership click and no completed live-control navigation;
  Mamma Maria's SevenRooms flow worked for one date, while failure to test the
  second date and omission of price are execution defects. OpenTable denial
  maps to uncommunicated R2.
- T5 / `food-culinary-researcher` — `KEEP`: Three 1 One was selected despite no
  published price and its already-open reservation surface was not explored;
  Mamma Maria's official pages were available and the run did not try its
  official SevenRooms path. The guessed OpenTable URL primarily maps to
  uncommunicated R2.
- T6 / `food-budget-novice` — `KEEP`: Google challenge was bypassed; the misses
  are unsupported starter/product selections and incomplete page preservation,
  with no target-page access denial tied to a communicated unmet rubric.
- T6 / `food-busy-host` — `KEEP`: Google challenge was bypassed; misses are
  incomplete/incorrect product evidence and organization, not a demonstrated
  target-page block.
- T6 / `food-cautious-dietary-planner` — `KEEP`: The Kitchn source constraint
  was not communicated. The run reached first-party Sainsbury's, M&S, and Boots
  surfaces; remaining misses came from staying on hubs/search pages and failed
  product-card interaction strategy rather than a target URL access denial.

The remaining ten cells were clean successes, recovered environment signals,
or genuine agent outcomes without a communicated unmet rubric materially caused
by an external blocker. Therefore this draft snapshot recommends **20 KEEP / 10
RERUN**.
