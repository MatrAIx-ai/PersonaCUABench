"""Persona users ask, a web agent does the work, a judge grades it.

Three LLMs, three roles:

    persona LLM   a MatrAIx persona holding an Odysseys task as its own hidden
                  need; says it in its own words, answers the agent's questions
                  in character
    CUA           a neutral tool-calling agent on a real Chrome; knows only what
                  the persona told it, may ask back (ask_user)
    judge         grades the task's own rubric against the trajectory, the final
                  answer and the tabs left open -- and, per rubric item, whether
                  the persona ever communicated that requirement at all

The hidden need is fixed per task; only how it is said varies with the persona.
Scoring each rubric item as met AND communicated keeps "the user never asked
for that" apart from "the agent could not do it".

    python odyssey/run.py --task 1 --persona elderly-novice
    python odyssey/run.py --all --persona none        # control: Odysseys text verbatim

Keys come from the repo's .env / env vars (OPENROUTER_API_KEY, OPENAI_API_KEY ...).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import persona as persona_lib  # noqa: E402  (odyssey/persona.py)

# Every model here speaks the OpenAI chat API; providers differ only in where
# they live and which env var holds the key.
PROVIDERS = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    "openai": ("OPENAI_API_KEY", None),          # None = the SDK's default endpoint
}


def load_dotenv(path: Path = REPO / ".env") -> None:
    """Read KEY=VALUE lines from the repo .env into the environment.

    The repo has no dotenv dependency and expects exported vars, so this is the
    one place that reads the file. Never overrides something already exported,
    and never writes the file back.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))

TASKS = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
PAGE_CHARS = 6000          # per read_page slice
MAX_TABS = 8
DEFAULT_PROFILE = HERE / ".chrome-profile"   # gitignored; keeps consent cookies

MAX_QUESTIONS = 5          # ask_user calls per run

AGENT_RULES = """
You are an assistant browsing the live internet in a real Chromium browser to
carry out a request from a user. Work through it yourself with the tools; never
claim you visited a page you did not open, and never invent numbers -- every
figure you report must come from text you actually read with read_page.

Users differ: some spell out exactly which sites and details they want, others
describe their situation loosely. If something you need is genuinely unclear,
you may ask the user with ask_user (at most {max_questions} questions) -- but do
not ask about what you can reasonably decide yourself.

How to work:
- For directions, use Google's official Maps URL form:
  https://www.google.com/maps/dir/?api=1&origin=<from>&destination=<to>&travelmode=transit
  (travelmode = transit | driving | walking | bicycling).
- For a specific place, use:
  https://www.google.com/maps/search/?api=1&query=<place+name>
  Do NOT hand-build /maps/place/<name> or /maps/dir/<a>/<b> URLs without the
  ?api=1 form -- Google silently drops you at a default location and the page
  you read will be empty.
- To search the web, open_tab on https://www.google.com/search?q=<url-encoded
  query>. Google sometimes answers with an "unusual traffic" / captcha page --
  if it does, fall back to https://html.duckduckgo.com/html/?q=<query> for the
  search, then open_tab the real result URL directly (metra.com, weather.com,
  booking.com ... ) so the source page itself is what stays open.
- Prefer navigating straight to a known site's URL over searching for it.
- read_page returns a slice of the page text; call it again with a larger
  offset to keep reading a long page.
- If a page blocks you, is empty, or shows a consent/captcha wall, try click on
  the consent button, or open a different source. Do not get stuck: after two
  failed attempts on one page, move on and say so in your summary.
- Leave open every tab the request asks you to keep open. Do not close them.
- When you are done, call finish with your complete final answer to the user.
""".strip().format(max_questions=MAX_QUESTIONS)

TOOLS = [
    {"type": "function", "function": {
        "name": "open_tab",
        "description": "Open a URL in a NEW browser tab and return its title and the first slice of page text.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "Full URL including https://"}},
            "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "goto",
        "description": "Navigate an EXISTING tab to a new URL (replaces what it was showing).",
        "parameters": {"type": "object", "properties": {
            "tab_id": {"type": "integer"}, "url": {"type": "string"}},
            "required": ["tab_id", "url"]}}},
    {"type": "function", "function": {
        "name": "read_page",
        "description": f"Read {PAGE_CHARS} more characters of a tab's visible text, starting at offset.",
        "parameters": {"type": "object", "properties": {
            "tab_id": {"type": "integer"},
            "offset": {"type": "integer", "description": "Character offset, default 0"}},
            "required": ["tab_id"]}}},
    {"type": "function", "function": {
        "name": "click",
        "description": "Click the first element in a tab whose visible text contains the given string.",
        "parameters": {"type": "object", "properties": {
            "tab_id": {"type": "integer"}, "text": {"type": "string"}},
            "required": ["tab_id", "text"]}}},
    {"type": "function", "function": {
        "name": "type_text",
        "description": "Type into a tab's input field (CSS selector) and optionally press Enter.",
        "parameters": {"type": "object", "properties": {
            "tab_id": {"type": "integer"}, "selector": {"type": "string"},
            "text": {"type": "string"}, "press_enter": {"type": "boolean"}},
            "required": ["tab_id", "selector", "text"]}}},
    {"type": "function", "function": {
        "name": "list_tabs",
        "description": "List every open tab with its id, title and current URL.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "close_tab",
        "description": "Close a tab. Do not close tabs the request asked you to keep open.",
        "parameters": {"type": "object", "properties": {"tab_id": {"type": "integer"}},
                       "required": ["tab_id"]}}},
    {"type": "function", "function": {
        "name": "ask_user",
        "description": "Ask the user a clarifying question and get their reply.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string"}}, "required": ["question"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Deliver the final answer to the user and end the session.",
        "parameters": {"type": "object", "properties": {
            "summary": {"type": "string", "description": "The complete final answer."}},
            "required": ["summary"]}}},
]


# --------------------------------------------------------------------------- #
# Browser
# --------------------------------------------------------------------------- #
def _browser_user_agent() -> str:
    """A real Chrome UA for the installed Chrome.

    Headless Chrome advertises "HeadlessChrome" in its UA and sites act on it:
    metra.com's CDN answers 403 to every page for a headless UA and 200 for the
    same headless browser with this one overridden. A block like that does not
    look like a block in the results -- it looks like an agent that failed to
    find anything.
    """
    import shutil

    version = "153.0.0.0"
    candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  shutil.which("google-chrome"), shutil.which("google-chrome-stable"),
                  shutil.which("chrome")]
    for binary in filter(None, candidates):
        try:
            out = subprocess.run([binary, "--version"],
                                 capture_output=True, text=True, timeout=10).stdout
            major = out.strip().split()[-1].split(".")[0]
            if major.isdigit():
                version = f"{major}.0.0.0"
                break
        except Exception:
            continue
    return (f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{version} Safari/537.36")


class Browser:
    """A handful of tab operations over a real Chromium page set."""

    def __init__(self, headless: bool = False, nav_timeout_ms: int = 40000,
                 profile_dir: str | os.PathLike = DEFAULT_PROFILE):
        from playwright.sync_api import sync_playwright

        # The real installed Chrome with a persistent profile, not the bundled
        # headless shell: sites reject the shell outright, and a profile that
        # survives runs keeps consent/captcha cookies so a wall solved by hand
        # once does not come back every run.
        self._pw = sync_playwright().start()
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=headless,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            user_agent=_browser_user_agent(),
            args=[
                "--disable-blink-features=AutomationControlled",
                # Every tool here reads inner_text, never pixels, so image
                # decoding is pure memory cost -- and these pages are all
                # photos. The rest trims processes this run never uses.
                "--blink-settings=imagesEnabled=false",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--mute-audio",
                # The rubrics require tabs to stay OPEN, so tabs cannot be
                # closed to save memory -- but they can share renderers. With
                # site isolation off and a hard renderer cap, 8 open tabs cost
                # 3 processes instead of 8. Text extraction is unaffected.
                "--renderer-process-limit=3",
                "--disable-features=site-per-process,IsolateOrigins",
                "--js-flags=--max-old-space-size=256",
            ],
        )
        self._ctx.set_default_timeout(nav_timeout_ms)
        self._tabs: dict[int, object] = {}
        self._next_id = 1
        # A persistent context opens with one blank page; reuse it as tab 1.
        self._spare = self._ctx.pages[0] if self._ctx.pages else None

    def _text(self, page, offset: int = 0) -> str:
        try:
            body = page.inner_text("body")
        except Exception as exc:  # a page that never settles still has a URL
            return f"[could not read page text: {exc}]"
        body = re.sub(r"\n{3,}", "\n\n", body)
        slice_ = body[offset:offset + PAGE_CHARS]
        more = "" if offset + PAGE_CHARS >= len(body) else (
            f"\n\n[...{len(body) - offset - PAGE_CHARS} more chars; "
            f"read_page with offset={offset + PAGE_CHARS} for the rest]")
        return (slice_ or "[no text at this offset]") + more

    def _settle(self, page, max_wait: float = 15.0) -> None:
        """Wait until the page's visible text stops growing.

        A fixed 1s sleep let Google Maps place pages be read at 87 characters --
        the agent saw a blank page and could not report what the rubric asked
        for, which looks in the results exactly like an agent that did not try.
        These are SPAs: readiness is when the text settles, not when the
        document loads.
        """
        try:
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        # "Non-empty and unchanged" is not enough: a cross-country route sits
        # at 1 character for two seconds while it computes, which reads as
        # stable. Require some actual content before believing the page is
        # done; fall through at the deadline for pages that really are sparse.
        deadline, last, stable = time.monotonic() + max_wait, -1, 0
        while time.monotonic() < deadline:
            time.sleep(0.5)
            try:
                size = len(page.inner_text("body"))
            except Exception:
                continue
            stable = stable + 1 if size == last else 0
            last = size
            if stable >= 3 and size >= 200:   # 1.5s unchanged, with content
                return

    def _page(self, tab_id: int):
        page = self._tabs.get(int(tab_id))
        if page is None:
            raise KeyError(f"no tab {tab_id}; open tabs: {sorted(self._tabs)}")
        return page

    def open_tab(self, url: str) -> str:
        if len(self._tabs) >= MAX_TABS:
            return f"[tab limit {MAX_TABS} reached; close a tab first]"
        page, self._spare = (self._spare, None) if self._spare else (self._ctx.new_page(), None)
        tab_id, self._next_id = self._next_id, self._next_id + 1
        self._tabs[tab_id] = page
        try:
            page.goto(url)
        except Exception as exc:
            return f"tab {tab_id} opened but navigation failed: {exc}"
        self._settle(page)
        return f"tab {tab_id} | {page.title()} | {page.url}\n\n{self._text(page)}"

    def goto(self, tab_id: int, url: str) -> str:
        page = self._page(tab_id)
        try:
            page.goto(url)
        except Exception as exc:
            return f"navigation failed: {exc}"
        self._settle(page)
        return f"tab {tab_id} | {page.title()} | {page.url}\n\n{self._text(page)}"

    def read_page(self, tab_id: int, offset: int = 0) -> str:
        page = self._page(tab_id)
        return f"tab {tab_id} | {page.url}\n\n{self._text(page, int(offset or 0))}"

    def click(self, tab_id: int, text: str) -> str:
        page = self._page(tab_id)
        try:
            page.get_by_text(text, exact=False).first.click()
        except Exception as exc:
            return f"click failed: {exc}"
        self._settle(page)
        return f"clicked {text!r}; tab {tab_id} now at {page.url}\n\n{self._text(page)}"

    def type_text(self, tab_id: int, selector: str, text: str, press_enter: bool = False) -> str:
        page = self._page(tab_id)
        try:
            page.fill(selector, text)
            if press_enter:
                page.press(selector, "Enter")
        except Exception as exc:
            return f"typing failed: {exc}"
        self._settle(page)
        return f"typed into {selector}; tab {tab_id} now at {page.url}\n\n{self._text(page)}"

    def list_tabs(self) -> str:
        return json.dumps(self.open_tabs(), indent=2)

    def close_tab(self, tab_id: int) -> str:
        page = self._tabs.pop(int(tab_id), None)
        if page is None:
            return f"no tab {tab_id}"
        page.close()
        return f"closed tab {tab_id}"

    def open_tabs(self) -> list[dict]:
        out = []
        for tab_id, page in sorted(self._tabs.items()):
            try:
                out.append({"tab_id": tab_id, "title": page.title(), "url": page.url})
            except Exception:
                out.append({"tab_id": tab_id, "title": "[closed]", "url": ""})
        return out

    def close(self) -> None:
        for closer in (self._ctx.close, self._pw.stop):
            try:
                closer()
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# Agent loop
# --------------------------------------------------------------------------- #
def _client(model: str, provider: str = ""):
    from openai import OpenAI

    provider = provider or ("openai" if model.startswith(("gpt-", "o1", "o3", "o4"))
                            else "openrouter")
    if provider not in PROVIDERS:
        raise SystemExit(f"unknown provider {provider!r}; known: {sorted(PROVIDERS)}")
    key_env, base_url = PROVIDERS[provider]
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise SystemExit(f"no API key for provider {provider!r}: set {key_env} "
                         f"(in the repo-root .env, or exported)")
    return OpenAI(api_key=key, base_url=base_url), provider


def extract_json(text: str) -> dict | None:
    """The JSON object in a model reply, tolerating ``` fences or prose around it."""
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _create_with_retry(client, *, attempts: int = 5, **kwargs):
    """One chat call, retrying the transient provider failures.

    A shared-pool 429 is the normal weather on an aggregated endpoint, and a
    single one used to kill a whole grid run mid-browse. Retries on rate limits,
    5xx and connection drops; anything else (a bad model id, a bad key) is a
    real error and is raised immediately.
    """
    import openai as openai_sdk

    retryable = (openai_sdk.RateLimitError, openai_sdk.APIConnectionError,
                 openai_sdk.InternalServerError)
    for attempt in range(attempts):
        try:
            return client.chat.completions.create(**kwargs)
        except retryable as exc:
            if attempt == attempts - 1:
                raise
            delay = 5 * 2 ** attempt          # 5, 10, 20, 40s
            print(f"  [{type(exc).__name__}] retrying in {delay}s "
                  f"({attempt + 1}/{attempts - 1})", flush=True)
            time.sleep(delay)


PERSONA_USER_RULES = """
You need help with something, and you are about to ask an AI assistant that can
browse the web to do it for you.

Below is a complete checklist of what would fully satisfy you. An expert wrote
it, not you: its website names, step order and instructions about tabs are the
expert's, and most people would never phrase a request like that. Use it only
to know what you are after.

Now ask for help the way YOU actually would, given who you are:
- Talk about your situation and what you want to find out or decide -- not a
  step-by-step procedure, unless you are the kind of person who writes those.
- Mention a specific website, tool or technical step only if someone with your
  background would know it and care about it. Otherwise describe what you want
  in your own terms, or leave it out.
- Say as much or as little as you really would. Leaving things unsaid that you
  would not think to mention is fine -- the assistant can ask.
- Use your own vocabulary and tone.

When the assistant asks you something, answer as yourself, truthfully according
to the checklist -- including details you left out at first, if you are asked
about them. If it asks about something the checklist does not settle, answer
the way you plausibly would. Keep replies short and natural. Never say you are
an AI, a simulation, or that you were given a task or a checklist.

# What would fully satisfy you (the expert's checklist -- not your words)
{goal}
""".strip()


class PersonaUser:
    """The person asking: a persona LLM holding the Odysseys task as its need.

    With no persona (the control arm) the opening message is the Odysseys task
    verbatim -- exactly the original benchmark -- and follow-up questions are
    answered by the same LLM without a profile.
    """

    def __init__(self, task: dict, persona_path: Path | None, model: str,
                 provider: str = "", temperature: float = 0.7):
        self.client, self.provider = _client(model, provider)
        self.model, self.temperature = model, temperature
        rules = PERSONA_USER_RULES.format(goal=task["confirmed_task"])
        if persona_path is None:
            system = "You are a person.\n\n" + rules
        else:
            system = persona_lib.persona_system_prompt(persona_path, role="a person") + \
                "\n\n# Right now\n\n" + rules
        self.messages = [{"role": "system", "content": system}]
        if persona_path is None:
            self.opening = task["confirmed_task"]
            self.messages += [{"role": "user", "content": "What do you ask the assistant?"},
                              {"role": "assistant", "content": self.opening}]
        else:
            self.opening = self._say("Write the message you send the assistant. "
                                     "Only the message itself.")
            if not self.opening:
                raise RuntimeError("persona LLM produced no opening request")
        self.transcript = [{"role": "user", "text": self.opening}]

    def _say(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        resp = _create_with_retry(self.client, model=self.model, messages=self.messages,
                                  temperature=self.temperature)
        text = (resp.choices[0].message.content or "").strip()
        self.messages.append({"role": "assistant", "content": text})
        return text

    def reply(self, question: str) -> str:
        answer = self._say(f"The assistant asks you: {question}\n\nReply as yourself.") \
            or "(no answer)"
        self.transcript += [{"role": "assistant", "text": question},
                            {"role": "user", "text": answer}]
        return answer

    def info(self) -> dict:
        return {"model": self.model, "provider": self.provider}


def run_agent(task: dict, user: PersonaUser, model: str, *, max_steps: int,
              headless: bool, temperature: float,
              profile_dir: str | os.PathLike = DEFAULT_PROFILE,
              provider: str = "") -> dict:
    client, provider = _client(model, provider)
    # The CUA carries no persona: it knows the user only through what they say.
    messages = [{"role": "system", "content": AGENT_RULES},
                {"role": "user", "content": user.opening}]
    questions = 0

    browser = Browser(headless=headless, profile_dir=profile_dir)
    trajectory: list[dict] = []
    answer, stop_reason, empty_turns = "", "max_steps", 0
    try:
        for step in range(max_steps):
            resp = _create_with_retry(
                client, model=model, messages=messages, tools=TOOLS,
                temperature=temperature)
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            calls = msg.tool_calls or []
            if not calls and not (msg.content or "").strip():
                # Neither a tool call nor a word. That is an API hiccup, not a
                # result: scoring it would record a transient failure as this
                # persona's performance. Retry the turn; give up only if the
                # model stays mute.
                messages.pop()
                empty_turns += 1
                if empty_turns >= 3:
                    stop_reason = "no_model_output"
                    break
                time.sleep(3)
                continue
            empty_turns = 0
            if not calls:
                # No tool call and no finish: treat the plain text as the answer.
                answer, stop_reason = (msg.content or "").strip(), "no_tool_call"
                break
            for call in calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if name == "finish":
                    answer, stop_reason = str(args.get("summary", "")).strip(), "finish"
                    result = "ok"
                elif name == "ask_user":
                    questions += 1
                    result = (user.reply(str(args.get("question", "")))
                              if questions <= MAX_QUESTIONS else
                              f"[question limit {MAX_QUESTIONS} reached -- decide yourself]")
                else:
                    fn = getattr(browser, name, None)
                    try:
                        result = fn(**args) if fn else f"unknown tool {name}"
                    except Exception as exc:
                        result = f"{type(exc).__name__}: {exc}"
                trajectory.append({"step": step, "tool": name, "args": args,
                                   "result_preview": str(result)[:400]})
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": str(result)[:PAGE_CHARS + 500]})
            if stop_reason == "finish":
                break
        if not answer and stop_reason != "no_model_output":
            # Out of budget with nothing said. Asking once for the summary is
            # what separates "found little" from "found things but never got to
            # report them" -- otherwise the judge scores an empty string and
            # every content rubric fails for a reason that is not the agent's
            # findings.
            stop_reason = "max_steps_summarised"
            messages.append({"role": "user", "content":
                             "You are out of time. Give your final answer now, "
                             "using only what you actually found."})
            try:
                final = _create_with_retry(client, model=model, messages=messages,
                                           temperature=temperature)
                answer = (final.choices[0].message.content or "").strip()
            except Exception as exc:
                answer, stop_reason = "", f"max_steps_no_summary ({type(exc).__name__})"
        open_tabs = browser.open_tabs()
    finally:
        browser.close()

    return {"answer": answer, "stop_reason": stop_reason, "steps": len(trajectory),
            "max_steps": max_steps, "trajectory": trajectory, "open_tabs": open_tabs,
            "conversation": user.transcript, "user": user.info(),
            "arm": {"model": model, "provider": provider, "temperature": temperature}}


# --------------------------------------------------------------------------- #
# Judge
# --------------------------------------------------------------------------- #
JUDGE_PROMPT = """You are grading a web agent against a fixed rubric. A user \
asked the agent for help in their own words; the agent browsed the live \
internet and produced a final answer.

For each rubric item decide two things independently:

- met: was the requirement actually satisfied, by evidence in the final answer, \
the action log and the tabs left open? A requirement that a page be left open is \
met only if that page appears in the open tabs. A reported figure counts only if \
the agent actually visited a page that would show it. Judge this the same way \
whether or not the user asked for it.
- communicated: did the conversation make this requirement known to the agent -- \
said explicitly, or implied clearly enough that a reasonable assistant would act \
on it? A specific site or detail the user never mentioned and the agent never \
asked about is NOT communicated.

Do not reward or penalise tone, personality, verbosity or writing style.

## What the user actually needed (hidden from the agent)
{task}

## Conversation between the user and the agent
{conversation}

## Rubric
{rubric}

## Agent's final answer
{answer}

## Action log (tool calls the agent made)
{actions}

## Tabs left open at the end
{tabs}

Return ONLY a JSON object, one entry per rubric id:
{{"R1": {{"met": true, "communicated": true, "reason": "<one sentence citing the evidence>"}}, ...}}"""


def judge_run(task: dict, run: dict, *, judge_model: str, judge_provider: str) -> dict:
    client, _ = _client(judge_model, judge_provider)
    rubric = "\n".join(
        f"- {rid}: {r['requirement']}\n  verification: {r['verification']}"
        for rid, r in task["rubrics"].items())
    actions = "\n".join(
        f"{t['step']}. {t['tool']}({json.dumps(t['args'], ensure_ascii=False)[:200]}) -> "
        f"{t['result_preview'][:160]}" for t in run["trajectory"]) or "(no actions)"
    conversation = "\n".join(
        f"{'USER' if t['role'] == 'user' else 'AGENT'}: {t['text']}"
        for t in run.get("conversation") or []) or "(none)"
    prompt = JUDGE_PROMPT.format(
        task=task["confirmed_task"], conversation=conversation, rubric=rubric,
        answer=run["answer"] or "(the agent produced no final answer)",
        actions=actions, tabs=json.dumps(run["open_tabs"], indent=2))

    # A reasoning judge on a long trajectory can spend its whole budget thinking
    # and return an empty string, so the budget is generous and an unusable
    # answer is retried rather than thrown -- the browse it grades cost minutes.
    # No temperature: reasoning models such as gpt-5.5 accept only the default,
    # and they take max_completion_tokens, not max_tokens.
    verdicts, last_error = None, ""
    for attempt in range(3):
        try:
            resp = _create_with_retry(client, model=judge_model,
                                      messages=[{"role": "user", "content": prompt}],
                                      max_completion_tokens=8000)
            parsed = extract_json(resp.choices[0].message.content or "")
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            parsed = None
        if parsed:
            verdicts = parsed
            break
        print(f"  [judge returned nothing usable] attempt {attempt + 1}/3", flush=True)
        time.sleep(3)

    if verdicts is None:
        # Grading failed; the run itself is still worth keeping.
        return {"judge_model": judge_model, "error": last_error or "empty judge response",
                "verdicts": {}, "met": None, "total": len(task["rubrics"]),
                "score": None, "trajectory_efficiency": None}
    return {"judge_model": judge_model, "verdicts": verdicts,
            **score_verdicts(task, verdicts, run["steps"])}


def score_verdicts(task: dict, verdicts: dict, steps: int) -> dict:
    """score over every rubric item, plus score over only the communicated ones.

    The second number is what the agent could fairly be held to: an item the
    persona never voiced and the agent never asked about is a gap in the
    conversation, not in the agent's ability to do the work.
    """
    ids = list(task["rubrics"])
    v = {rid: verdicts.get(rid) or {} for rid in ids}
    met = sum(bool(v[r].get("met")) for r in ids)
    said = [r for r in ids if bool(v[r].get("communicated"))]
    met_said = sum(bool(v[r].get("met")) for r in said)
    total = len(ids)
    return {"met": met, "total": total,
            "score": round(met / total, 3) if total else 0.0,
            "communicated": len(said),
            "score_communicated": round(met_said / len(said), 3) if said else None,
            "trajectory_efficiency": round(met / total / max(steps, 1), 4) if total else 0.0}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _is_scored(path: Path) -> bool:
    """True only for a result that actually carries a score.

    A run whose judge failed writes a result.json with score None; treating that
    as done would make the failure permanent on every resume.
    """
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (rec.get("judgement") or {}).get("score") is not None


def resolve_tasks(spec: str | None, run_all: bool) -> list[dict]:
    if run_all or not spec:
        return TASKS
    picked = []
    for token in spec.split(","):
        token = token.strip()
        if token.isdigit():
            picked.append(TASKS[int(token) - 1])
        else:
            hits = [t for t in TASKS if t["task_id"].startswith(token)]
            if not hits:
                raise SystemExit(f"no task matching {token!r}")
            picked.append(hits[0])
    return picked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", help="1-6, a task_id prefix, or a comma-separated list")
    ap.add_argument("--all", action="store_true", help="run all 6 tasks")
    ap.add_argument("--persona", default="elderly-novice",
                    help="the user asking: a name under odyssey/personas/ (omit .yaml), "
                         "or 'none' for the Odysseys task text verbatim")
    ap.add_argument("--model", default="qwen/qwen3.8-27b", help="the CUA doing the work")
    ap.add_argument("--provider", default="openrouter",
                    help="override routing for --model, e.g. openrouter for a "
                         "qwen id served somewhere other than DashScope")
    ap.add_argument("--persona-model", default="qwen/qwen3.8-27b",
                    help="the LLM playing the persona user")
    ap.add_argument("--persona-provider", default="openrouter")
    ap.add_argument("--judge-model", default="gpt-5.5")
    ap.add_argument("--judge-provider", default="",
                    help="default: openai for gpt-*/o* ids, openrouter otherwise")
    # 30 demonstrably truncates the medium tasks before the agent can finish.
    ap.add_argument("--max-steps", type=int, default=50)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--headless", action="store_true",
                    help="no browser window (recommended; required on a server without a display)")
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE),
                    help="Chrome user-data dir; reused across runs so a captcha "
                         "solved by hand once keeps working")
    ap.add_argument("--no-judge", action="store_true", help="run the agent only")
    ap.add_argument("--preview", action="store_true",
                    help="only print what the persona would say to open each task -- "
                         "no browser, no judge; check this before paying for a grid")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip a cell that already has a judged result, so an "
                         "interrupted grid resumes by re-running the same command")
    ap.add_argument("--out", default=str(HERE / "results"))
    args = ap.parse_args()
    load_dotenv()

    persona_path = HERE / "personas" / f"{args.persona}.yaml"
    if args.persona != "none" and not persona_path.is_file():
        raise SystemExit(f"no persona at {persona_path}")
    judge_provider = args.judge_provider      # "" -> inferred from the model id

    if args.preview:
        for task in resolve_tasks(args.task, args.all):
            user = PersonaUser(task, None if args.persona == "none" else persona_path,
                               args.persona_model, args.persona_provider,
                               temperature=args.temperature)
            print(f"\n=== {task['task_id'][:12]} [{task['level']}] persona={args.persona} "
                  f"({len(user.opening.split())} words; Odysseys original "
                  f"{len(task['confirmed_task'].split())}) ===\n{user.opening}")
        return

    for task in resolve_tasks(args.task, args.all):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # A model id like "qwen/qwen3.8-27b" would otherwise split the run
        # directory across an extra path level.
        safe_model = args.model.replace("/", "-")
        cell = Path(args.out) / task["task_id"][:12]
        if args.skip_existing and any(
            _is_scored(d / "result.json")
            for d in cell.glob(f"{args.persona}__{safe_model}__*")
        ):
            print(f"skip {task['task_id'][:12]} [{task['level']}] persona={args.persona} "
                  f"-- already has a result")
            continue
        out_dir = cell / f"{args.persona}__{safe_model}__{stamp}"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {task['task_id'][:12]} [{task['level']}] persona={args.persona} "
              f"model={args.model} ===")

        try:
            user = PersonaUser(task, None if args.persona == "none" else persona_path,
                               args.persona_model, args.persona_provider,
                               temperature=args.temperature)
            print(f"  user says: {user.opening[:300]!r}", flush=True)
            run = run_agent(task, user, args.model, max_steps=args.max_steps,
                            headless=args.headless, temperature=args.temperature,
                            profile_dir=args.profile, provider=args.provider)
        except Exception as exc:  # a dead task must not take the grid with it
            print(f"FAILED: {type(exc).__name__}: {exc}")
            (out_dir / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n",
                                               encoding="utf-8")
            continue
        record = {"task_id": task["task_id"], "level": task["level"],
                  "persona": args.persona, "run": run}
        if run["stop_reason"] == "no_model_output":
            # Not a result. Leave it unscored so a resume retries the cell.
            record = {"task_id": task["task_id"], "level": task["level"],
                      "persona": args.persona, "run": run,
                      "judgement": {"error": "model returned no output", "verdicts": {},
                                    "met": None, "total": len(task["rubrics"]),
                                    "score": None}}
            (out_dir / "result.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"UNSCORED: model returned no output -> {out_dir / 'result.json'}")
            continue
        if not args.no_judge:
            try:
                record["judgement"] = judge_run(task, run, judge_model=args.judge_model,
                                                judge_provider=judge_provider)
            except Exception as exc:  # never lose a completed browse to the judge
                record["judgement"] = {"error": f"{type(exc).__name__}: {exc}",
                                       "verdicts": {}, "met": None,
                                       "total": len(task["rubrics"]), "score": None}
            j = record["judgement"]
            if j.get("score") is None:
                print(f"UNJUDGED ({j.get('error')})  "
                      f"(steps {run['steps']}, stop={run['stop_reason']})")
            else:
                print(f"score {j['met']}/{j['total']} = {j['score']}  "
                      f"communicated {j['communicated']}/{j['total']} "
                      f"-> score on those {j['score_communicated']}  "
                      f"(steps {run['steps']}, asked {(len(run['conversation']) - 1) // 2}, "
                      f"stop={run['stop_reason']})")
        (out_dir / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"-> {out_dir / 'result.json'}")


if __name__ == "__main__":
    main()
