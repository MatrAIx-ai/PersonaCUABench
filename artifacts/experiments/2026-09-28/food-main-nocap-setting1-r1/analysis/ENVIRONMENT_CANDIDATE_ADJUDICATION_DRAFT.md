# Food r1 environment-candidate adjudication (draft)

This is a read-only manual adjudication of the eleven completed cells classified
as `ENVIRONMENT_EXCLUSION_CANDIDATE` by `food_result_audit.py` after the grid
reached 30/30 unique numeric results. It does not change any result, trajectory,
profile, or run configuration.

Decision rule: exclude and rerun only when an environment blocker materially
prevented evidence required by a persona-communicated rubric and the run did not
recover with usable equivalent evidence. A transient/recovered error, a dead or
incorrect link, poor source selection, failure to navigate a usable interface, or
early stopping remains a genuine agent/task outcome and is kept.

## Summary

- **KEEP:** 4 cells
- **EXCLUDE_RERUN:** 7 cells

## Task 4 — BOTW dessert setup (`5944875c7f32`)

### `food-budget-novice` — KEEP

- Result: score 0.571; 20 steps; `no_tool_call`; unmet communicated R4 and R6.
- Sally's and IGN initially timed out but were later readable, so those failures
  recovered.
- R4 failed because the selected YouTube frame video was unavailable and the agent
  stopped on an exact-title Google results page instead of opening another actual
  X-Carve frame source.
- R6 failed because the chosen Apple URL redirected to the generic iPad guide even
  though a usable Google result for the correct Apple help page remained available.
- These are source-selection/navigation and early-stop outcomes, not unrecovered
  environment obstruction. Hidden R3 details were not persona-communicated.

### `food-busy-host` — KEEP

- Result: score 0.429; 19 steps; `finish`; unmet communicated R7.
- A `help.easel.com` page produced `ERR_NAME_NOT_RESOLVED`, but the run recovered
  with an accessible Inventables Easel page. Other initial dead links were replaced
  by usable IGN, Dole, and Apple pages.
- R7 failed because the agent did not identify or leave open the required chocolate
  comparison recipe. That omission is unrelated to the recovered Easel DNS error.

### `food-cautious-dietary-planner` — KEEP

- Result: score 0.571; 20 steps; `no_tool_call`; unmet communicated R2.
- The D23 URL first timed out and then resolved as a genuine 404. A usable Google
  Dole Whip results page remained available, but the agent stopped without opening
  another live recipe page.
- IGN, King Arthur, and Zelda Wiki timeout cases were readable later or replaced by
  alternatives. R2 is therefore a stale-source/early-stop failure, not persistent
  cross-site obstruction.

### `food-culinary-researcher` — EXCLUDE_RERUN

- Result: score 0.857; 31 steps; `finish`; unmet communicated R4.
- The persona explicitly requested a credible custom photo-frame-style X-Carve
  source. A targeted Google site query timed out and later entered Google's block
  page; the corresponding DuckDuckGo query hit a human-verification challenge;
  several Inventables/X-Carve URLs repeatedly timed out.
- The run could open only a generic Inventables signs-use-case page. It produced a
  plausible workflow but never recovered the specifically required custom-frame
  source, exactly matching the R4 failure.
- Other initial Apple/Sally/BOTW errors recovered and are not exclusion grounds.

## Task 5 — Boston dinners (`18ddad3e0781`)

The relative two-day window is evaluated from each cell's run date: September
28–29 for the first four cells below and September 29–30 for the culinary-researcher
cell.

### `none` — EXCLUDE_RERUN

- Result: score 0.75; 15 steps; `finish`; unmet communicated R2.
- R2 explicitly required a romantic Boston restaurant sourced through OpenTable.
  Mamma Maria's OpenTable page returned `Access Denied`.
- Google and the official restaurant site supplied ambiance, price, and hours, but
  did not replace the rubric's required, visually verifiable OpenTable listing.
  R1, R3, and R4 passed.

### `food-budget-novice` — EXCLUDE_RERUN

- Result: score 0.25; 17 steps; `finish`; unmet communicated R3.
- The persona asked for next-two-day availability. Both relevant OpenTable pages
  returned `Access Denied`; Google Maps Reserve and the official reservation route
  did not expose concrete dates or time slots.
- The answer explicitly reported that the provider blocked the live availability
  view. The missing R3 availability evidence was therefore materially censored.

### `food-busy-host` — KEEP

- Result: score 0.25; 26 steps; `finish`; unmet communicated R1 and R4.
- Mistral's OpenTable page was denied, but the agent recovered through Google
  Reserve and found concrete September 28 slots, so the affected availability
  requirement R3 passed.
- R1 failed because the agent omitted a Michelin or equivalent independent
  fine-dining source.
- For R4, Google Reserve defaulted to September 30; the agent failed to navigate to
  September 28/29 and did not try the usable SevenRooms alternative. This is an
  execution omission, not a consequence of the recovered Mistral/OpenTable block.

### `food-cautious-dietary-planner` — EXCLUDE_RERUN

- Result: score 0.0; 33 steps; `finish`; unmet communicated R3 and R4.
- Mooo's official page initially timed out and its OpenTable page returned
  `Access Denied`. No usable live reservation interface or September 28/29
  availability evidence was recovered, directly causing communicated R3 to fail.
- SRV's missing price/page evidence under R4 is an additional agent issue, but it
  does not change the environment-exclusion decision.

### `food-culinary-researcher` — EXCLUDE_RERUN

- Result: score 0.5; 39 steps; `finish`; unmet communicated R4.
- SevenRooms successfully supplied Mamma Maria's romantic-townhouse evidence and
  September 29/30 availability, so those parts recovered.
- The persona also explicitly requested an expected price range. Repeated Mamma
  Maria homepage/menu attempts failed with DNS errors or timeouts; Google entered
  its block page, and DuckDuckGo/Resy paths also suffered DNS failures. No menu or
  equivalent current price evidence was recovered, directly causing R4 to fail.
- Ostra's OpenTable failure is not an exclusion ground because the corresponding
  business-dinner rubric R3 passed.

## Task 6 — UK Christmas menu and gifts (`e20742e26a4d`)

### `none` — EXCLUDE_RERUN

- Result: score 0.429; 74 trajectory entries; `no_tool_call`; unmet communicated
  R1, R3, R4, and R5.
- The Kitchn spiral-ham article returned a human-verification/access-denied page.
  Google snippets let the agent state a plausible method, but no usable copy of the
  required Kitchn article was opened, so the method could not be verified and R3
  failed.
- That is a material unrecovered blocker for a communicated requirement. The name
  mismatch under R1 and missing product-page evidence under R4/R5 are separate
  agent/source-selection failures and are not themselves exclusion grounds.

### `food-culinary-researcher` — EXCLUDE_RERUN

- Result: score 0.286; 51 trajectory entries; `finish`; unmet communicated R1,
  R3, R4, R5, and R6. All seven rubrics were persona-communicated.
- The decisive blocker is The Kitchn spiral-ham article in tab 19. It returned
  `Access to this page has been denied` and `Please verify you are a human` because
  the site detected automation.
- The answer explicitly states that it relied on a search-result summary. No usable
  copy of the required Kitchn article was opened, so the visible-article evidence
  required by R3 was not recovered.
- R1 is separately attributable to opening only one clearly gluten-free starter
  page and leaving two items' gluten status unconfirmed. R4 reflects opening only
  one of three selected M&S product pages. For R5/R6, Boots search pages were
  accessible but the agent repeatedly failed to open the selected product cards.
  These are agent/source-navigation outcomes, not additional exclusion grounds.
- Google, DuckDuckGo, and later Bing also displayed challenge pages, but the run
  recovered through direct retailer pages and usable Bing results for most other
  research. The direct unrecovered Kitchn block is the clean causal basis.

## Sanity check of newly completed non-candidates

### Task 6 `food-cautious-dietary-planner` — KEEP

- Google and some DuckDuckGo/Bing searches showed anti-bot challenges that are not
  currently matched by every scanner pattern, but first-party Sainsbury's, M&S,
  and Boots pages remained usable.
- R1 failed because the three opened recipe pages did not visibly prove consistent
  gluten-free status/name matching; R4/R5 failed because the agent left category
  or search pages rather than individual selected product pages. These failures
  were not materially caused by an unrecovered environment block.

### Task 1 `food-culinary-researcher` — KEEP

- Google entered its unusual-traffic page, but the run recovered through
  DuckDuckGo and direct EatingWell, Le Creuset, YouTube, and inspection-source
  pages. All rubrics passed; no material unresolved environment issue remains.

### Task 2 `food-culinary-researcher` — KEEP

- Google, DuckDuckGo, and some Bing searches challenged the browser, but the run
  recovered through site APIs and direct recipe pages for Ambitious Kitchen and
  Feel Good Foodie.
- The only unmet communicated rubric, R2, failed because the final answer shortened
  the visible recipe title by omitting `You'll Ever Eat`; that is an answer-fidelity
  error unrelated to the search blocks.

### Task 3 `food-culinary-researcher` — KEEP

- Google and one later DuckDuckGo query were blocked, but the run recovered the
  usable The Knot Minneapolis directory, Surdyk's The Knot profile, Surdyk's
  first-party pages, and a mulligatawny recipe.
- R1 failed because only one vendor profile was opened rather than at least five;
  R2 failed because Surdyk's was omitted from the displayed shortlist despite its
  profile being open. Both are execution/output omissions, not unrecovered web
  blockage.

All four newly completed successful result JSON files have internally consistent
step/trajectory counts, rubric totals, met/communicated counts, and scores. One
artifact-hygiene note does not affect adjudication: Task 1 P4's attempt-2 log also
contains text from an earlier `APIConnectionError` attempt and NUL bytes, and a
later failed-attempt directory exists after the successful result. The selected
successful `result.json` itself is valid and should remain the cell result.

## Exact rerun set

- Task 4: `food-culinary-researcher`
- Task 5: `none`
- Task 5: `food-budget-novice`
- Task 5: `food-cautious-dietary-planner`
- Task 5: `food-culinary-researcher`
- Task 6: `none`
- Task 6: `food-culinary-researcher`

All other completed candidates listed above should remain in the formal sample.
