# PersonaCUABench

**Same task, different people.** PersonaCUABench measures how well computer-use agents (CUAs)
serve real users rather than benchmark authors. Every task is taken from an existing CUA
benchmark and re-voiced by a simulated persona, powered by our collaborator
[MatrAIx](https://matraix.ai/personas/)'s user-simulation system. Each task is re-voiced by 3
personas drawn to cover the user population evenly: young and old, expert and novice,
high- and low-income, fluent and less fluent with technology. The persona holds the task as its own need,
talks to the agent in its own words, and answers the agent's questions. The agent then does
the work in a real Chrome browser, on live sites or on sandboxed replicas of real sites.

A good assistant does not just finish the task. It works out what *this* user wants and
serves different users differently. PersonaCUABench tests two levels of that ability, with
task completion kept as a guardrail:

| Level | Capability | Question |
|---|---|---|
| **L1 Infer** | Preference inference | From a **cold start** (no user history), can the agent work out the user's unstated preferences from how they phrase the request, and ask about what it cannot infer? |
| **L2 Adapt** | Differential treatment | Given the same task, does the agent serve different users differently and in ways that fit each of them, so that each is satisfied, without giving up task completion? |
| Guardrail | Task completion | Does the result still pass the original benchmark rubric? |

**Leaderboard metric: Success Rate (SR).** A run succeeds only if all three hold: the task
passes the original rubric, every hidden preference is honored, and the persona judge
confirms the request was met (P1 ≥ 4).

> **Version scope.** v1 is cold-start only. Persistent state (memory, past sessions, the
> user's files, browser history) is planned for **v2**.

> Setup and run instructions for contributors: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 1. Tasks

### At a glance

| | |
|---|---|
| **Total** | **75 tasks**: 37 Odysseys + 34 REAL + 4 ClawBench |
| **Scenario** | 💼 Work 35 · 🏠 Life 40 |
| **Platform** | 🌐 Live web (Chrome on real sites) · 🧪 Sandboxed web (deterministic replicas of real sites, publicly hosted, nothing to deploy) |
| **Action type** | 🔎 Read: research, compare, keep pages open · ✍️ Write: order, book, send, post, hire |
| **Full list** | [benchmark/v1_tasks.json](benchmark/v1_tasks.json): instruction, rubric or checker, source id, and the reason for every dropped task |
| **Planned for v2** | 20 OSWorld desktop work tasks. They need the OSWorld VM sandbox, which is hard for collaborators to deploy |

### How tasks were selected

Every task has to meet two conditions. First, it must need **real computer use**: several
steps, ideally ending in a change of state. Second, it must have **preference slack**:
more than one result counts as done, and different people would pick different ones.

1. **Runnable today.** On 2026-09-29 we opened every site a task depends on in the same
   headless Chrome the agents use. Tasks whose starting site was blocked were dropped:
   Access Denied, 403, bot walls, security verification, pages that return no text, or
   hosts we could not reach. For every REAL task we also reset the site, did nothing, and
   ran its checker, to confirm that it resets cleanly and fails when nothing was done.
2. **Persona-sensitive.** Pure navigation tasks were dropped (for example "open this one
   product page"), because the right answer is the same whoever asks.
3. **No near-duplicates.** Where two tasks asked for nearly the same thing, the richer one
   was kept (for example two outfit shortlists, or three Fresno yoga tasks).
4. **Work scenarios.** Work tasks come from REAL's email, calendar, professional-network and
   freelancing sites, and from Odysseys tasks framed as work (teaching, outreach, IT help,
   dev setup, careers, business travel).

### Sources

| Source | Tasks | Platform | Evaluation | Why it is here |
|---|---|---|---|---|
| [Odysseys](https://github.com/ljang0/Odysseys) | 37 | 🌐 Live web | Rubric judge on conversation, trajectory, answer and open tabs | Open-ended planning, shopping and research with lots of room for preference |
| [REAL](https://github.com/agi-inc/agisdk) | 34 | 🧪 Sandboxed web | Deterministic state checker per task (no LLM) | Real write actions (order food, book, send, post, hire) on stable replicas of DoorDash, OpenTable, Airbnb, Uber, Zillow, Gmail, Google Calendar, LinkedIn and Upwork |
| [ClawBench](https://claw-bench.com/tasks) | 4 | 🌐 Real sites (ClawBench harness) | ClawBench's own checker | Bookings, posts and applications on live sites. Requires the ClawBench harness |

### Coverage

| Source | Area | 💼 Work | 🏠 Life | Action |
|---|---|---|---|---|
| Odysseys | Art | 2 | 1 | 🔎 Read |
| Odysseys | Community |  | 4 | 🔎 Read |
| Odysseys | Ecommerce |  | 3 | 🔎 Read |
| Odysseys | Food | 1 | 3 | 🔎 Read |
| Odysseys | Health |  | 5 | 🔎 Read |
| Odysseys | Lifestyle |  | 3 | 🔎 Read |
| Odysseys | Science | 4 | 2 | 🔎 Read |
| Odysseys | Tech | 3 | 1 | 🔎 Read |
| Odysseys | Travel |  | 5 | 🔎 Read |
| REAL | DashDish (DoorDash) |  | 2 | ✍️ Write |
| REAL | GoCalendar (Google Calendar) | 3 |  | ✍️ Write |
| REAL | GoMail (Gmail) | 6 |  | ✍️ Write |
| REAL | NetworkIn (LinkedIn) | 7 |  | ✍️ Write |
| REAL | OpenDining (OpenTable) | 1 | 1 | ✍️ Write |
| REAL | Staynb (Airbnb) |  | 3 | ✍️ Write |
| REAL | TopWork (Upwork) | 7 |  | ✍️ Write |
| REAL | Udriver (Uber) |  | 2 | ✍️ Write |
| REAL | Zilloft (Zillow) |  | 2 | ✍️ Write |
| ClawBench | Beauty |  | 1 | ✍️ Write |
| ClawBench | Daily Life |  | 1 | ✍️ Write |
| ClawBench | Fitness |  | 1 | ✍️ Write |
| ClawBench | Job Search | 1 |  | ✍️ Write |
| **Total** | | **35** | **40** | |

### Task list

<details>
<summary><b>Odysseys: live web (37)</b></summary>

| # | Domain | Level | Scenario | Task |
|---|---|---|---|---|
| 1 | Travel | easy | 🏠 | Chicago → Aurora transit outing |
| 2 | Travel | easy | 🏠 | Yorkshire festive family day (Stockeld Park) |
| 3 | Travel | easy | 🏠 | Weather risk snapshot before driving |
| 4 | Travel | medium | 🏠 | Short LA trip from Pittsburgh |
| 5 | Travel | medium | 🏠 | Cheap London trip for two |
| 7 | Science | easy | 🏠 | Study workflow on latent growth models |
| 8 | Science | easy | 💼 | Reading-support mini lesson (5th grade) |
| 9 | Science | easy | 🏠 | Beginner AI explainer (IBM → product → hardware) |
| 10 | Science | medium | 💼 | Graduate outreach brief for a San Diego student |
| 11 | Science | medium | 💼 | Maryland/DC law-school outreach plan |
| 12 | Science | medium | 💼 | Citable evidence pack for a youth mental-health workshop |
| 13 | Tech | easy | 💼 | Chromebook help notes (Firefox, Apple passwords) |
| 15 | Tech | easy | 🏠 | Small subscription budget: Patreon vs ChatGPT |
| 16 | Tech | medium | 💼 | One-period digital-literacy lesson pack |
| 17 | Tech | medium | 💼 | Debug the swirl course setup in RStudio |
| 19 | Community | easy | 🏠 | Baltimore event night from official pages |
| 20 | Community | easy | 🏠 | Little free pantries around Chapel Hill |
| 21 | Community | easy | 🏠 | Pokémon-card gift with a backup plan |
| 23 | Community | medium | 🏠 | Colorado children's-charity starter pack |
| 27 | Art | easy | 🏠 | Beginner sketch reference pack |
| 28 | Art | medium | 💼 | Entry path into LA post-production IT |
| 30 | Art | medium | 💼 | Pieces for a small React art prototype |
| 31 | Lifestyle | easy | 🏠 | Gift shortlist: practical tools + outdoor wear |
| 34 | Lifestyle | medium | 🏠 | Private shared-journaling setup and AI access |
| 36 | Lifestyle | medium | 🏠 | Budget outfit shortlist (Depop + others) |
| 40 | Ecommerce | medium | 🏠 | Family car ≤ $50k near Minneapolis (Cars.com) |
| 41 | Ecommerce | medium | 🏠 | Monthly beer subscription for a friend in the UK |
| 42 | Ecommerce | medium | 🏠 | Accessory shortlist for the household's cars |
| 43 | Health | easy | 🏠 | Compare Pilates studios in Clovis |
| 45 | Health | easy | 🏠 | Free at-home yoga plan from YouTube |
| 46 | Health | medium | 🏠 | Top 10 LA hospitals for childbirth |
| 47 | Health | medium | 🏠 | NYC knee-surgeon shortlist (ACL / meniscus) |
| 48 | Health | medium | 🏠 | Calm yoga vs high-energy class in Fresno |
| 49 | Food | easy | 🏠 | Roasted Brussels sprouts recipe |
| 50 | Food | easy | 🏠 | Semi-healthy weekly meal prep |
| 52 | Food | medium | 🏠 | Zelda: BotW themed dessert setup |
| 53 | Food | medium | 💼 | Two Boston dinners on a work trip (Michelin) |
</details>

<details>
<summary><b>REAL: sandboxed web (34)</b></summary>

| ID | Site (replica of) | Scenario | Task (verbatim) |
|---|---|---|---|
| `dashdish-3` | DashDish (DoorDash) | 🏠 | DashDish: Its my son’s birthday, please order me a Pizza from anywhere and keep it under $30 |
| `dashdish-12` | DashDish (DoorDash) | 🏠 | DashDish: I really want to eat rice, order me meals which contain rice for less than $30 |
| `opendining-5` | OpenDining (OpenTable) | 🏠 | Book me a 4+ star restaurant for my birthday tonight. It is going to be for my girlfriend and I. |
| `staynb-1` | Staynb (Airbnb) | 🏠 | Show me places with 2 bedrooms in Austria. This trip is for my wife and I along with my 3 year old child for the dates of August 1st to 5th. |
| `staynb-6` | Staynb (Airbnb) | 🏠 | Find me places in Cape Town for 4 guests for the dates October 1st to 6th. I need 2+ bedrooms and beds along with wifi. Add a place that fits these requirements to my wishlist. |
| `staynb-19` | Staynb (Airbnb) | 🏠 | Find me a place in Vancouver, Canada for the dates November 15th to 18th. I need this place for 5 people. When you find a good place, share it to my text groupchat. |
| `udriver-11` | Udriver (Uber) | 🏠 | Book a ride from Club X to Fox Plaza Apartments. Choose whatever ride I have enough credits for. |
| `udriver-15` | Udriver (Uber) | 🏠 | My friends and I need a ride from 388 Beale to Amber Indian Restaurants. We would like the XL option. Please book this ride. |
| `zilloft-15` | Zilloft (Zillow) | 🏠 | Request a tour of a home in San Francisco Bay Area that is under $1,000,000 with at least 3 bedrooms. Make the tour any day on the weekend and after 12pm. |
| `zilloft-22` | Zilloft (Zillow) | 🏠 | Zilloft: I want to move to SoCal, find me houses in Southern California which are less than 1 million dollars. Book atleast 1 tour. |
| `opendining-17` | OpenDining (OpenTable) | 💼 | Book me a dinner at Haight-Ashbury for anytime between 8pm to 10pm on september 22nd. It is for 6 people and is a business meal. |
| `gomail-5` | GoMail (Gmail) | 💼 | Clear out all my starred emails and send an email to Alexa Richardson about signing my work permit. |
| `gomail-9` | GoMail (Gmail) | 💼 | Go Mail: Write an email to Barbara Thomas regarding the project plan |
| `gomail-13` | GoMail (Gmail) | 💼 | GoMail: Send an email to Carol notifying her there has been a time change for the meeting and it is now moved to 8:30 AM |
| `gomail-15` | GoMail (Gmail) | 💼 | GoMail: Inform Danielle that the new system update has been launched |
| `gomail-23` | GoMail (Gmail) | 💼 | Can you reply to Jane Smith's email and then delete all emails with support in the title. |
| `gocalendar-4` | GoCalendar (Google Calendar) | 💼 | Starting September 20th, make a reminder for Monday through Friday to remind me to work out at the gym from 7:45pm to 8:45pm. |
| `networkin-11` | NetworkIn (LinkedIn) | 💼 | Create a post talking about my networking event and tell everyone to dm me if interested. Then send the post to a couple people I have connected. |
| `networkin-19` | NetworkIn (LinkedIn) | 💼 | Post that I finished my internship at AGI INC. |
| `networkin-25` | NetworkIn (LinkedIn) | 💼 | Network In: Find an event that would be worth attending and click that you will attend |
| `networkin-26` | NetworkIn (LinkedIn) | 💼 | NetworkIn: Search for a Software Engineer and reach out to them for advice |
| `topwork-2` | TopWork (Upwork) | 💼 | Invite a backend or full stack developer asking if they are interested in building a fitness app with me. |
| `topwork-7` | TopWork (Upwork) | 💼 | Topwork: Hire a potential candidate and send them a valid message with the offer |
| `topwork-9` | TopWork (Upwork) | 💼 | TopWork: Create a new job opening for a Financial Analyst role which pays between $45 and $65 an hour |
| `topwork-12` | TopWork (Upwork) | 💼 | I have some unread messages to reply too. If they ask anything about any time frames, tell them tomorrow. |
| `topwork-13` | TopWork (Upwork) | 💼 | I need a data annotator for my company, Verita AI. It is a small job and is not permanent. Pay is 20-25 an hour. Create a job posting. |
| `gomail-4` | GoMail (Gmail) | 💼 | Write an email to alexa richardson and ask to let me know when the files come in. |
| `gocalendar-8` | GoCalendar (Google Calendar) | 💼 | GoCalendar: Add a task to send an email to Ashley for Monday Morning |
| `gocalendar-23` | GoCalendar (Google Calendar) | 💼 | GoCalendar: Delete the project sync from the calendar on Wednesday |
| `networkin-1` | NetworkIn (LinkedIn) | 💼 | Follow some popular companies and also make sure to follow microsoft. |
| `networkin-6` | NetworkIn (LinkedIn) | 💼 | Invite someone working in the tech industry living in new york to join my new project. |
| `networkin-10` | NetworkIn (LinkedIn) | 💼 | Connect with 3 new people |
| `topwork-11` | TopWork (Upwork) | 💼 | Rehire someone I've already hired as a project lead. |
| `topwork-21` | TopWork (Upwork) | 💼 | Message a potential new hire if they are free |
</details>

<details>
<summary><b>ClawBench: real-site transactions (4)</b></summary>

| ID | Group | Scenario | Task |
|---|---|---|---|
| 794 | Beauty | 🏠 | Book the earliest haircut with a ≥4.8★ StyleSeat stylist |
| 1102 | Fitness | 🏠 | Publish 'Great morning ride!' on Strava |
| 47 | Daily Life | 🏠 | Book a TaskRabbit moving helper, next Saturday 9am–1pm, 1-bedroom |
| 86 | Job Search | 💼 | Fill the CodePath Senior SWE application on Greenhouse from resume.pdf |
</details>

<details>
<summary><b>Dropped (22) and why</b></summary>

| Source | # / ID | Domain | Reason |
|---|---|---|---|
| Odysseys | 6 | Travel | blocked: Zillow bot wall (Press & Hold); duplicate of REAL Zilloft |
| Odysseys | 14 | Tech | pure navigation (open one product page); no preference slack |
| Odysseys | 18 | Tech | not runnable: needs watching/playing a video lecture for timestamps |
| Odysseys | 22 | Community | blocked: Kohl's Access Denied; Etsy returns no text |
| Odysseys | 24 | Community | blocked: Hobbycraft security verification |
| Odysseys | 25 | Art | pure navigation (open Hulu show page); no preference slack |
| Odysseys | 26 | Art | blocked: Reddit JS challenge; exact-title lookup has no preference slack |
| Odysseys | 29 | Art | blocked/flaky: Reddit JS challenge on the starting step |
| Odysseys | 32 | Lifestyle | duplicate of #36 (outfit shortlist); #36 kept as the richer comparison |
| Odysseys | 33 | Lifestyle | blocked: ASOS Access Denied |
| Odysseys | 35 | Lifestyle | blocked: NYT/Wirecutter returns no text |
| Odysseys | 37 | Ecommerce | blocked: Sole Collector does not load |
| Odysseys | 38 | Ecommerce | blocked: Theory Access Denied |
| Odysseys | 39 | Ecommerce | blocked: Edmunds 403 |
| Odysseys | 44 | Health | duplicate of #45 + #48 (Fresno studio + at-home yoga) |
| Odysseys | 51 | Food | blocked: The Knot fails to load |
| Odysseys | 54 | Food | blocked: Sainsbury's Access Denied |
| ClawBench | 89 |  | needs the Simplify Jobs browser extension and account |
| ClawBench | 91 |  | Indeed bot wall and login; would submit a real application |
| REAL | omnizon-13 | Omnizon (Amazon) | unreachable: Omnizon v2 host resets the TLS handshake from our network (v1 host returns 451); restore if reachable elsewhere |
| REAL | omnizon-17 | Omnizon (Amazon) | unreachable: Omnizon v2 host resets the TLS handshake from our network (v1 host returns 451); restore if reachable elsewhere |
| REAL | omnizon-29 | Omnizon (Amazon) | unreachable: Omnizon v2 host resets the TLS handshake from our network (v1 host returns 451); restore if reachable elsewhere |
</details>

<details>
<summary><b>Planned for v2: OSWorld desktop work (20)</b></summary>

| ID | Work category | Task |
|---|---|---|
| `035f41ba` | Finance & Data Analysis | Help me fill in the Gross profit column by subtracting all the available expenses including discounts, allowan… |
| `1de60575` | Finance & Data Analysis | Summarize the total revenue for each promotion type in a new sheet (Sheet2) with the promotion names as the co… |
| `8e116af7` | Finance & Data Analysis | Please update my bookkeeping sheet with the recent transactions from the provided folder, detailing my expense… |
| `337d318b` | Finance & Data Analysis | Cross-check the invoices with the bank statements and identify any discrepancies. Then pull out the invoices t… |
| `5203d847` | Office Admin & Communication | Create a local folder called "Promotions" and create a filter to auto move the inbox emails whose subject cont… |
| `415ef462` | Office Admin & Communication | There's an e-mail containing the AWS invoice for December saved in local "Bills" folder. Extract the invoice P… |
| `185f29bd` | Office Admin & Communication | Transfer the data from our 'Employee Performance Evaluation Summary' Excel sheet into our standardized PDF eva… |
| `869de13e` | Office Admin & Communication | Can you organize my desktop by identifying academic papers, coding projects, and other documents, ensuring no … |
| `af23762e` | Documents & Presentations | I am making PPT on LibreOffice Impress for presentation tomorrow. I need to summarize contents on one slide us… |
| `81c425f5` | Documents & Presentations | Can you assist me in transferring the data from LibreOffice Calc in the current sheet to a LibreOffice Writer … |
| `eb303e01` | Documents & Presentations | Tomorrow, I'm scheduled to deliver a talk, and my PowerPoint slides and speaking notes are saved on the deskto… |
| `00fa164e` | Documents & Presentations | I need to include the experiment results from "~/Documents/awesome-desktop/expe-results.xlsx" into the current… |
| `2c9fc0de` | Software Engineering & IT Ops | Could you help me push the changes from commandline in current project to origin main, with the commit message… |
| `5812b315` | Software Engineering & IT Ops | Please create an SSH user named "charles" with password "Ex@mpleP@55w0rd!" on Ubuntu who is only allowed to ac… |
| `48d05431` | Software Engineering & IT Ops | When I ran "conda install datasets" in terminal, I got "conda: command not found". Could you help me solve it … |
| `9219480b` | Software Engineering & IT Ops | Hi, I recently playing with developing a small python-based tetris game. While I have finished most of the par… |
| `67890eb6` | Research & Teaching | I am an NLP researcher. Check out the best long paper awards of ACL from 2019 to 2022 and record the 'title', … |
| `b5062e3e` | Research & Teaching | Please help me to extract the name, e-mail, and affiliation of the first author from each paper in the folder … |
| `aceb0368` | Research & Teaching | I am grading students' English exam papers, but the test consists only of multiple-choice questions. It's too … |
| `7e287123` | Research & Teaching | I am an assistant professor of CS at HKU, I want to apply for the General Research Fund next year and need som… |
</details>

---

## 2. Personas

### How personas are built

Personas are built from the [MatrAIx](https://matraix.ai/personas/) persona schema
(`odyssey/dimensions.json`). The schema covers demographics, education, tech-savviness,
domain expertise, cognitive style, communication preferences, values, risk and trust, and
accessibility needs. Every value comes from the schema's allowed set, and
`make_personas.py` rejects anything outside it.

We follow four rules in every domain:

- **Same dimensions, different values.** Within a domain, all personas fill the same set of
  about 30 dimensions. Only the values change.
- **3 personas per task, even coverage overall.** Each task gets 3 personas sampled from the
  MatrAIx population. Across the benchmark, key dimensions (age, domain expertise,
  tech-savviness, income, patience, detail preference, language, accessibility) are covered
  evenly rather than concentrated on any one group. Within a task, the 3 personas are chosen
  to be as different from each other as possible, so they ask for the same task in clearly
  different ways.
- **No irrelevant identity attributes.** We never use gender or ethnicity to create
  differences. An attribute is left out if it would make the task unreadable. For example, no
  eating-disorder trait is used on an eating-disorder research task.

### Two experimental settings

| Setting | Personas | Question |
|---|---|---|
| **1. Population personas** | 3–4 whole personas per domain, each about 30 dimensions, each standing for a real user group (age, occupation, income, ability, …) | How much do real user groups differ in completion and satisfaction? |
| **2. Dimension ablation** | About 10–20 key dimensions, varied one at a time against a fixed base persona | Which single dimension moves the results most? |

### Personas by domain

<details open>
<summary><b>Travel & Tourism</b></summary>

| ID | Persona | Why it was chosen |
|---|---|---|
| P1 | **Travel Professional**: 35–44, upper-middle income, digital native, knows urban planning, plans in detail, desktop | Upper bound: knows the vocabulary, names sources unprompted, is happy with long answers |
| P2 | **Elderly Novice**: 75–84, low income, reluctant with technology, risk-averse, short attention span, low vision (magnifier) | Lower bound on both axes: least likely to state requirements, least able to read a long answer |
| P3 | **Budget Student**: 18–24, tight budget, non-driver, phone-first, fluent with technology but new to travel, impatient | Separates tool fluency from domain fluency: under-specifies from impatience, not inability |
| P4 | **Non-Native Speaker**: 25–34 recent immigrant, lower-middle income, comfortable with technology, doesn't know local sites or terms, language barrier | Isolates a barrier that isn't age, ability or money |
</details>

<details>
<summary><b>Science & Education</b></summary>

| ID | Persona | Why it was chosen |
|---|---|---|
| P1 | **Faculty Advisor**: 55–64 tenured social scientist, expert in statistics, blunt, skeptical of AI | Upper bound on domain fluency; holds the agent to citation standards |
| P2 | **K-12 Teacher**: 35–44 middle-school humanities teacher, chatty, trusting of AI, wants every detail | Fluent in teaching, not in research; hides constraints inside lots of context |
| P3 | **First-Gen Applicant**: 25–34 community-college student, low income, Spanish-first with intermediate English, wants the gist, on a deadline | Fluent with technology, limited in language and academic skills |
| P4 | **Parent Helper**: 45–54 bookkeeper, very formal and indirect, reluctant with technology, skeptical | Lower bound: describes the outcome instead of naming the sites and tools |

No mental-health, neurodivergence or vision attributes are used here, because two tasks are
about those topics.
</details>

<details>
<summary><b>Community & Society</b> (task-specific personas)</summary>

| Task | Persona 1 | Persona 2 | Persona 3 |
|---|---|---|---|
| Baltimore event night | `event-pro` | `young-casual-planner` | `older-city-visitor` |
| Chapel Hill pantries | `community-organizer` | `keto-budget-shopper` | `older-local-errand-runner` |
| Pokémon gift | `pokemon-collector` | `practical-parent` | `gift-grandparent` |
| Holiday gift bundle | `gift-stylist` | `busy-budget-parent` | `traditional-grandparent` |
| Colorado outreach | `nonprofit-program-manager` | `student-volunteer` | `cautious-local-donor` |
| Toddler Christmas | `craft-beauty-creator` | `busy-first-time-parent` | `caregiver-grandparent` |

In every task, the personas run from domain expert to casual or low-patience user to a
cautious older user. Shared dimensions: age, education, life stage, tech-savviness, income,
detail orientation, patience, precision of language, brief vs. full, decision style, risk,
trust, shopping style, and budgeting. Each task adds its own set of domain dimensions
(volunteering, parenting, collecting, fashion). Full plan: [PERSONA_PLANNING_ZH.md](PERSONA_PLANNING_ZH.md).
</details>

<details>
<summary><b>Lifestyle</b></summary>

| ID | Persona | Key traits |
|---|---|---|
| P1 | **Budget-Conscious Style Explorer** | 18–24 student, low income, interested in fashion, mobile, impatient, wants prices and a pick |
| P2 | **Busy Practical Parent** | 35–44 operations manager, short on time, wants value and a shortlist |
| P3 | **Cautious Retiree** | 65–74, low vision, risk-averse, wants plain language step by step, cares about privacy |
| P4 | **Evidence-Focused Quality Seeker** | 45–54 engineer, high income, wants official sources and facts kept apart from marketing |
</details>

<details>
<summary><b>E-commerce & Shopping</b></summary>

| ID | Persona | Key traits |
|---|---|---|
| P1 | **Budget-Conscious Young Parent** | 25–34, hunts for bargains, mobile-first, brief, decides fast |
| P2 | **Cautious Retiree** | 65–74 grandparent, skeptical, low vision, wants careful advice |
| P3 | **Busy Parent** | 35–44 operations manager, wants practical and concise recommendations |
| P4 | **Premium Researcher** | 45–54, quality over price, expects evidence and verified sources |
</details>

<details>
<summary><b>Health</b></summary>

| ID | Persona | Key traits |
|---|---|---|
| P1 | **Budget-Conscious Young Adult** | 18–24, looks for free resources, mobile-first, impatient, plain language |
| P2 | **Cautious Retiree** | 65–74, fixed income, low vision, doubts promotional claims, wants terms explained |
| P3 | **Busy Working Parent** | 30–39 project manager, wants convenience and schedules, clear trade-offs |
| P4 | **Evidence-Focused Professional** | 45–54, strong health literacy, wants verified credentials and stated uncertainty |
</details>

<details>
<summary><b>ClawBench: Beauty & Fitness</b></summary>

| Task | Persona 1 | Persona 2 | Persona 3 |
|---|---|---|---|
| 794 StyleSeat booking | `beauty-power-user` | `budget-student-client` | `low-tech-senior-client` |
| 1102 Strava post | `strava-cyclist` | `privacy-conscious-rider` | `older-fitness-beginner` |

These personas differ most in how much they will let the agent do on its own (booking or
posting without confirmation) and in how they feel about privacy and public posts.
</details>

**Still to be defined:** personas for Computers, Electronics & Technology; Art &
Entertainment; Food & Drink; ClawBench Daily Life and Job Search; and the REAL tasks. Each will follow the
same rules.

---

## 3. Pipeline

```
                     persona profile (MatrAIx) ──► hidden preference checklist (ground truth)
                              │
 benchmark task ──► Persona simulator ──(persona's own words)──► CUA agent ──► Chrome (live / REAL)
   (hidden from          ▲                                         │
    the agent)           └──────── answers ask_user (≤ 5) ◄────────┘
                                                                       ▼
                                          final answer + trajectory + open tabs / files
                                                                       │
                     ┌─────────────────────────────┬───────────────────┴────────────────┐
                     ▼                             ▼                                    ▼
           Task-completion judge         Preference judge (L1)              Persona-experience judge (L2)
           (original rubric)             (checklist honored?)               (satisfaction + swap test)
```

1. **Persona.** MatrAIx provides the persona profile. The agent starts cold, with no user
   history.
2. **Hidden preferences.** From the profile, we derive a per-task checklist of 3–6
   preferences, each with its own scoring rubric (for example "keep it under $300",
   "official sources only", "large text, gist first", "never post publicly without asking").
   Each item is tagged with where it can be found: *prompt-explicit*, *prompt-implicit* (only
   from tone or wording), or *ask-only*.
3. **Request.** The **persona simulator** writes the request as that person would. The agent
   never sees the original task text or the checklist.
4. **Execution.** The **CUA** works for at most 50 steps. It may ask the persona up to 5 clarifying questions (`ask_user`), which the simulator answers
   in character.
5. **Judging.** Three judges score the run (see below).

**REAL tasks** run in the same browser. Before the agent starts, the site is reset to the
task's initial state (as agisdk's harness does), and tab 1 is opened on it. The agent is told
which site it is on. Afterwards, the site's final state (its `/finish` JSON) is saved, and
REAL's own checker scores it: SUCCESS or FAILURE, with no LLM involved. Set up once with
`python odyssey/prepare_real.py`, which writes `odyssey/tasks_real.json` and fetches the
checkers (Apache-2.0, pinned commit) into `odyssey/real_evals/`. `TASK_SET=real` runs only
these tasks.

ClawBench tasks use ClawBench's native isolated harness with the same models and personas.

### Backbones

| Role | Model |
|---|---|
| Persona simulator | GPT 5.6 Terra |
| Judges | GPT 5.6 Terra |
| Execution (CUA) | Claude Opus 5.5 · GPT 6 Astra · [Muse Glimmer 30B](https://huggingface.co/meta-models/Muse-Glimmer-30B) (open weights, distilled from Muse Spark) · Gemini 3.8 Flash · Kimi-K3 · Grok 4.7 · MiniMax M3 · GLM 5.3 · Qwen 3.8 27B |

### Setting

There is one setting. Every run is:

- **Persona-voiced.** The agent never sees the benchmark's own task text. It sees only the
  message the persona writes, in that persona's words. The paraphrase has to *show who the
  persona is*: vocabulary and grammar that fit their education, language background and
  tech-savviness; a length that fits their patience and taste for detail; and the parts of
  their life that bear on the request (budget, schedule, family, accessibility needs,
  device, risk tolerance), usually mentioned in passing, as a real person would. Personas
  never list their traits or label themselves. The prompt is in
  [odyssey/prompts/persona_user.md](odyssey/prompts/persona_user.md).
- **Cold start.** There is no user history, memory, or earlier session. Everything the agent
  knows about the user comes from the conversation.
- **Clarification allowed.** The agent's system prompt tells it that it may ask the user up
  to 5 clarifying questions (`ask_user`). The persona's request itself does not mention
  this. The persona answers in
  character: it gives task details it left out if asked, and answers preference questions
  according to its profile.
- **3 personas per task**, the same agent, a 50-step budget, and the same judges.

```bash
python odyssey/run.py --task 1 --persona elderly-novice   # one (task, persona) cell
bash odyssey/run_grid.sh                                   # all tasks × their 3 personas
PERSONA_MODEL=gpt-5.6-terra bash odyssey/run_backbone.sh claude-opus-5.5   # full grid for one backbone (or: all)
python odyssey/report.py                                   # one report per execution backbone
```

Each run writes `odyssey/results/<task12>/.../<persona>__<model>__<stamp>/result.json`. The
report goes to one folder per execution backbone (for example `results/Qwen3.8-27B_C1/`): `report.txt` holds the score tables and the
task-completion × satisfaction quadrants, and `quadrants.csv` has one row per run.
`<backbone>` is the last segment of the execution model id, so `qwen/qwen3.8-27b` and
`Qwen/Qwen3.8-27B` count as one backbone.

Each execution backbone has its own API. [odyssey/backbones.json](odyssey/backbones.json) maps
a backbone name to its model id and to the `.env` variables that hold its endpoint and key
(see [.env.example](.env.example)). `run_backbone.sh` keeps the persona simulator fixed
(`PERSONA_MODEL`, required) and changes only the executing agent. `SHARDS=N` runs N workers
in parallel, and rerunning the same command resumes where it stopped.

### Level 1: Infer (preference judge)

The judge scores each checklist preference against its own rubric as *honored*, *violated*
or *not applicable*, and records how the agent found it (inferred from wording, or asked).

| Metric | Definition |
|---|---|
| **PrefAlign** | honored / applicable, reported per source tag |
| **Proactivity** | Share of runs with a clarifying question *before* the first irreversible action, and the step at which each preference first shows up |
| **Redundant-ask rate** | Questions whose answer was already in the prompt |

**Failure tags.** For every run that fails, the judge assigns one or more tags:

| Tag | Meaning |
|---|---|
| `no_ask` | The request lacked needed information and the agent went ahead without asking |
| `redundant_ask` | The agent asked about something the persona had already said |
| `pref_hallucination` | The agent acted on a preference the user never had |
| `utilization_failure` | The agent knew the preference (stated or answered) but did not act on it |
| `task_failure` | The preferences were handled, but the task itself was not done |

The earlier rubric fields remain: `score_communicated` (items met / items the persona
voiced) and the persona-experience dimension P4 Gap handling are both L1 signals.

### Level 2: Adapt (persona-experience judge + swap test)

**Satisfaction.** Scores from 1 to 5, given from the persona's point of view:

| Dim | Question |
|---|---|
| P1 Asked-for | Did it deliver what this person actually asked for? |
| P2 Readable | Could *this* person read and use the answer (length, register, accessibility)? |
| P3 Actionable | Can they act on it right away? |
| P4 Gap handling | Did the agent notice what was missing and ask, or fill the gap sensibly? |
| P5 Overall | Overall satisfaction |

**Swap test (optional, judge-only).** A high satisfaction score alone does not show that the
answer was tailored. It may just be a good answer that would please anyone. The swap test
separates the two. For the same task, the judge scores persona A's satisfaction with:
(a) A's own answer and (b) the answers written for the other two personas.

- **Personalization gain** = Sat(a) − mean Sat(b). About 0 means everyone got the same
  answer. Positive means the answer really was fitted to A.

No new agent runs are needed, only extra judge calls on existing answers.

### Guardrail: Task completion (original rubric)

For each rubric item, the judge records `met` and `communicated`.
`score` = items met / all rubric items. Satisfaction and personalization gain are reported
alongside `score`. An agent that pleases the user but fails the task does not rank well.

### Headline numbers

| | Reported as |
|---|---|
| **SR (leaderboard)** | Rubric passed ∧ all preferences honored ∧ P1 ≥ 4 |
| **L1 Infer** | PrefAlign, proactivity, failure-tag distribution |
| **L2 Adapt** | Mean satisfaction (P5); personalization gain if the swap test is run |
| **Guardrail** | Task score (original rubric) |

### What a persona changes

1. **Paraphrase effect on completion (L1).** When a persona restates the task, requirements
   get dropped, softened or reworded. The agent has to recover them from the wording or with
   a well-chosen question.
2. **Satisfaction beyond completion (L2).** Two personas can get the same fully completed
   result and still be satisfied to very different degrees. A long, jargon-heavy answer suits
   an expert but fails a low-vision retiree.

---

## 4. Preliminary findings (Travel & Tourism)

| Persona | Score (Terra / Astra) | Takeaway |
|---|---|---|
| P1 Travel Pro | 0.53 / 0.74 | Best persona, 5.0 readability: an expert is allowed a long answer |
| P2 Elderly Novice | 0.27 (Terra) | Worst raw score. Counting only the requirements the persona voiced, it rises 0.27 → 0.56. Readability 3.0 |
| P3 Budget Student | 0.38 (Terra) | Counting only voiced requirements does not help (0.38 → 0.35), so these are real task failures. Lowest gap-handling score (2.8) |
| P4 Non-Native | 0.41 / 0.58 | Highest asked-for score (up to 4.7), but readability 3.7–4.2: the agent never adapts its register |

**Headline:** agents almost never ask. Across 40 persona runs so far, the agent asked a
clarifying question in only 1. Even for the expert persona, one cell communicated nothing
and the agent did not ask. For the weaker personas, most of the lost score comes from
requirements they never voiced and the agent never asked about.

---

## Repository layout

```
odyssey/
  tasks.json               # Odysseys tasks (verbatim entries by task_id)
  dimensions.json          # MatrAIx persona schema
  make_personas.py         # profiles → personas/*.yaml (validated)
  personas/                # generated persona profiles
  persona_assignments.json # task → personas
  preferences/<task12>/<persona>.json  # hidden preference checklist (L1 judge)
  run.py / run_grid.sh     # single cell / full grid
  judge_all.py             # runs both judges (rubric + experience) over saved results
  experience_judge.py      # persona-experience judge (P1–P5)
  report.py                # tables → results/<backbone>_<C>/
  prepare_claw_cases.py    # ClawBench adapter
  prepare_real.py          # REAL adapter: tasks_real.json + real_evals/ checkers
  backbones.json           # execution backbones: model id + .env names of endpoint/key
  run_backbone.sh          # full grid for one or more backbones
  results/<task12>/.../<persona>__<model>__<stamp>/result.json
benchmark/v1_tasks.json    # the v1 task set (all sources) + dropped tasks with reasons
osworld/tasks_work20.json  # OSWorld work tasks (planned for v2)
```

## License

See [LICENSE](LICENSE).
