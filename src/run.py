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

    python src/run.py --list-suites
    python src/run.py --suite shopping --task 1 --persona travel-senior
    python src/run.py --all --persona none        # default suite, verbatim control

Keys come from the repo's .env / env vars (OPENROUTER_API_KEY, OPENAI_API_KEY ...).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import jmespath  # noqa: E402  the query language some REAL checks are written in
import models as model_registry  # noqa: E402  (src/models.py)
import responses_shim  # noqa: E402  (src/responses_shim.py)
import persona as persona_lib  # noqa: E402  (src/persona.py)
import task_router  # noqa: E402

# Every model here speaks the OpenAI chat API; providers differ only in where
# they live and which env var holds the key.
PROVIDERS = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    "openai": ("OPENAI_API_KEY", None),          # None = the SDK's default endpoint
}
# Each model in the registry that has its owner's own endpoint becomes a
# provider of its own, named after the model. The base URL is read at call time
# rather than here, so a .env loaded later still takes effect.
for _key, _entry in model_registry.MODELS.items():
    _endpoint = _entry.get("endpoint") or {}
    if _endpoint.get("base_url_env"):
        PROVIDERS[_key] = (_endpoint.get("api_key_env", ""), None)

def provenance() -> dict:
    """Which code, browser and machine produced a result.

    A score is only reproducible with the commit that computed it, and the
    browser identity matters as much as the model: the bundled Chromium and a
    real Chrome are blocked by different sites, which shows up as an agent that
    "failed" rather than as an environment difference.
    """
    import platform
    import shutil

    def git(*args: str) -> str | None:
        try:
            out = subprocess.run(("git", *args), cwd=REPO, capture_output=True,
                                 text=True, timeout=10)
        except Exception:
            return None
        return out.stdout.strip() or None if out.returncode == 0 else None

    try:                      # the package exposes no __version__ attribute
        import importlib.metadata
        playwright_version = importlib.metadata.version("playwright")
    except Exception:
        playwright_version = None
    channel = os.environ.get("CHROME_CHANNEL", "chrome").strip() or None
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        # Uncommitted edits mean the commit alone does not describe this run.
        "dirty": bool(git("status", "--porcelain")),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "playwright": playwright_version,
        "browser": {"channel": None if os.environ.get("CHROME_PATH") else channel,
                    "executable": os.environ.get("CHROME_PATH") or None,
                    "user_agent": _browser_user_agent()},
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

PROMPTS = HERE / "prompts"


def prompt(name: str) -> str:
    """The text of src/prompts/<name>.md, without its leading HTML comment.

    Prompts live as files so they can be read and revised without touching the
    pipeline; the comment at the top of each one documents its placeholders and
    is stripped here so it never reaches a model.
    """
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return re.sub(r"\A<!--.*?-->\s*", "", text, flags=re.S).strip()


TASK_CATALOG = task_router.TaskCatalog.load()
DEFAULT_TASK_SUITE = TASK_CATALOG.default_suite
# Backward-compatible import surface for tests and notebooks.  It now means
# "the manifest's default suite", rather than the hard-coded tasks.json file.
TASKS = DEFAULT_TASK_SUITE.tasks
REAL_EVALS = HERE / "real_evals"   # deterministic state checkers, vendored
PAGE_CHARS = 6000          # per read_page slice
MAX_TABS = 8
DEFAULT_PROFILE = HERE / ".chrome-profile"   # gitignored; keeps consent cookies

MAX_QUESTIONS = 5          # ask_user calls per run
MAX_RETRIES = 3            # provider retries per call, and mute turns per run
# Consecutive tool-free turns before a run is called over. One is a progress
# note; three in a row is a model that has stopped working.
MAX_TEXT_TURNS = 3


def task_for_record(record: dict) -> tuple[dict, str]:
    """Return the run's frozen task, with a marked legacy fallback."""
    task_id = record.get("task_id")
    snapshot = record.get("task_snapshot")
    if (isinstance(snapshot, dict) and snapshot.get("task_id") == task_id
            and snapshot.get("confirmed_task") and snapshot.get("rubrics")):
        expected_hash = record.get("task_sha256")
        if (expected_hash and expected_hash != task_router.canonical_sha256(snapshot)):
            raise ValueError(f"frozen task snapshot hash mismatch for {task_id!r}")
        return snapshot, "frozen_snapshot"
    suite_id = (record.get("suite_id") or record.get("task_suite")
                or (record.get("suite_snapshot") or {}).get("id"))
    try:
        task, _ = TASK_CATALOG.find_task(task_id, suite_id=suite_id)
    except task_router.TaskRoutingError as exc:
        raise ValueError(
            f"task {task_id!r} is not recoverable from the frozen run or task catalog: {exc}"
        ) from exc
    return task, "unverified_current_tasks"

AGENT_RULES = prompt("agent").format(max_questions=MAX_QUESTIONS)
# An experimental arm, off by default: the neutral prompt measures how often a
# model asks on its own, and that number is a finding. Turning this on measures
# something else -- whether it can ask well when told to -- so the two must
# never be mixed in one comparison, and the run config records which was used.
PROACTIVE_NUDGE = prompt("agent_proactive_nudge").format(
    max_questions=MAX_QUESTIONS)

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
                 profile_dir: str | os.PathLike = DEFAULT_PROFILE,
                 shots_dir: str | os.PathLike | None = None):
        from playwright.sync_api import sync_playwright

        # The real installed Chrome with a persistent profile, not the bundled
        # headless shell: sites reject the shell outright, and a profile that
        # survives runs keeps consent/captcha cookies so a wall solved by hand
        # once does not come back every run.
        #
        # A machine where Chrome cannot be installed (no root) sets
        # CHROME_CHANNEL=chromium to use Playwright's own download, or
        # CHROME_PATH to an extracted Chrome binary. Both are a fallback: some
        # sites treat the bundled build differently, so record which one a run
        # used when comparing results across machines.
        self._pw = sync_playwright().start()
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        executable = os.environ.get("CHROME_PATH", "").strip()
        channel = os.environ.get("CHROME_CHANNEL", "chrome").strip()
        browser_choice = ({"executable_path": executable} if executable
                          else {"channel": channel} if channel else {})
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            **browser_choice,
            headless=headless,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            user_agent=_browser_user_agent(),
            args=[
                "--disable-blink-features=AutomationControlled",
                # The tools read inner_text, never pixels, so image decoding is
                # pure memory cost -- unless screenshots are being kept, where a
                # page without its images is useless to look at.
                *([] if shots_dir else ["--blink-settings=imagesEnabled=false"]),
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
        self._shots_dir = Path(shots_dir) if shots_dir else None
        if self._shots_dir:
            self._shots_dir.mkdir(parents=True, exist_ok=True)
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

    def shot(self, label: str, tab_id: int | None = None) -> dict | None:
        """A JPEG of what the page looked like, for reading a trajectory later.

        The agent never sees these -- it works from text -- but a person
        auditing a run cannot tell a captcha wall from an empty page in a text
        log, and that distinction decided several scores. A failure to capture
        is not a failure of the step, so it is recorded and swallowed.
        """
        if self._shots_dir is None:
            return None
        page = self._tabs.get(int(tab_id)) if tab_id is not None else None
        if page is None:
            page = next(iter(reversed(list(self._tabs.values()))), None)
        if page is None:
            return None
        name = f"{len(list(self._shots_dir.glob('*.jpg'))):03d}-{label}.jpg"
        path = self._shots_dir / name
        try:
            page.screenshot(path=str(path), type="jpeg", quality=55)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        return {"file": f"shots/{name}", "bytes": path.stat().st_size}

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
        # Most specific match first, and only visible elements: "Send" must hit
        # the Send button, not a hidden label or a "Sent" folder containing it.
        # (From the main line: the first version clicked the first text match,
        # which is why agents reported "I clicked the pizza and nothing opened".)
        candidates = (page.get_by_role("button", name=text, exact=True),
                      page.get_by_role("link", name=text, exact=True),
                      page.get_by_text(text, exact=True),
                      page.get_by_role("button", name=text),
                      page.get_by_text(text, exact=False))
        last_error = None
        for attempt in range(2):          # a page still rendering gets one more look
            if attempt:
                time.sleep(1.5)
            for locator in candidates:
                try:
                    for index in range(min(locator.count(), 10)):
                        element = locator.nth(index)
                        if element.is_visible():
                            element.click(timeout=10000)
                            self._settle(page)
                            return (f"clicked {text!r}; tab {tab_id} now at {page.url}"
                                    f"\n\n{self._text(page)}")
                except Exception as exc:
                    last_error = exc
        if last_error and "intercepts pointer events" in str(last_error):
            return (f"click failed: {text!r} is visible but covered by another "
                    f"element, such as an open dialog or overlay. Read the page "
                    f"and deal with that first.")
        if last_error:
            return f"click failed on {text!r}: {str(last_error).splitlines()[0]}"
        return f"click failed: no visible element matching {text!r}"

    # A selector that matches nothing otherwise waits out the context's whole
    # 40s and returns a Playwright call log the model cannot act on. Eight
    # seconds is long enough for a real field to appear and short enough that a
    # wrong guess costs a moment instead of a minute.
    TYPE_TIMEOUT_MS = 8000

    def type_text(self, tab_id: int, selector: str, text: str, press_enter: bool = False) -> str:
        page = self._page(tab_id)
        try:
            page.fill(selector, text, timeout=self.TYPE_TIMEOUT_MS)
            if press_enter:
                page.press(selector, "Enter", timeout=self.TYPE_TIMEOUT_MS)
        except Exception as exc:
            return f"typing failed: {self._why_typing_failed(page, selector, exc)}"
        self._settle(page)
        return f"typed into {selector}; tab {tab_id} now at {page.url}\n\n{self._text(page)}"

    def _why_typing_failed(self, page, selector: str, exc: Exception) -> str:
        """The reason in terms the model can act on, not a Playwright call log."""
        try:
            field = page.locator(selector)
            count = field.count()
        except Exception:
            return f"{selector!r} is not a usable selector: {exc}"
        if count == 0:
            return (f"nothing on the page matches {selector!r}. Read the page and "
                    f"use a selector that is actually there.")
        try:
            first = field.first
            if first.get_attribute("readonly") is not None or not first.is_editable():
                return (f"{selector} exists but cannot be typed into -- it is "
                        f"read-only. Click it and use whatever it opens (a date "
                        f"picker, a dropdown) instead of typing.")
        except Exception:
            pass
        if count > 1:
            return (f"{selector!r} matches {count} elements, so it is ambiguous. "
                    f"Narrow it, e.g. \"{selector} >> nth=0\".")
        return str(exc).split("\nCall log:")[0]

    def list_tabs(self) -> str:
        return json.dumps(self.open_tabs(), indent=2)

    def close_tab(self, tab_id: int) -> str:
        page = self._tabs.pop(int(tab_id), None)
        if page is None:
            return f"no tab {tab_id}"
        page.close()
        return f"closed tab {tab_id}"

    # A REAL sandbox keeps its state in this browser, and exposes two control
    # pages: /config loads a task's initial state and /finish renders the
    # current state as JSON. Underscored because the agent must never see them
    # as tools -- resetting or reading state is the harness's job, not its own.
    def _real_reset(self, url: str, task_ref: str) -> None:
        """Load the task's initial state, as agisdk's own harness does."""
        page = self._ctx.new_page()
        try:
            page.goto(f"{url}/config?run_id=0&task_id={task_ref}&latency=0")
            page.wait_for_load_state("networkidle")
            page.goto(f"{url}/finish")
        finally:
            page.close()

    def _real_state(self, url: str) -> dict:
        """The site's final state: the JSON its /finish page renders."""
        page = self._ctx.new_page()
        try:
            page.goto(f"{url}/finish")
            page.wait_for_load_state("networkidle")
            return json.loads(page.wait_for_selector("pre").inner_text())
        finally:
            page.close()

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
def _provider_config(provider: str) -> tuple[str, str | None]:
    """Resolve a provider key and endpoint without ever logging the secret."""
    if provider not in PROVIDERS:
        raise SystemExit(f"unknown provider {provider!r}; known: {sorted(PROVIDERS)}")

    def read_key(direct_names: tuple[str, ...], file_names: tuple[str, ...]) -> str:
        key = next(
            (os.environ.get(name, "").strip() for name in direct_names
             if os.environ.get(name, "").strip()),
            "",
        )
        if key:
            return key
        for name in file_names:
            raw_path = os.environ.get(name, "").strip()
            if not raw_path:
                continue
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = REPO / path
            try:
                key = path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise SystemExit(f"cannot read {name} at {path}: {exc}") from exc
            if not key:
                raise SystemExit(f"{name} points to an empty file: {path}")
            return key
        return ""

    endpoint = (model_registry.MODELS.get(provider) or {}).get("endpoint")
    if endpoint:
        # A model reached through its owner's own vendor endpoint.
        base_url = os.environ.get(endpoint.get("base_url_env", ""), "").strip()
        if not base_url:
            raise SystemExit(
                f"provider {provider!r} needs {endpoint.get('base_url_env')} "
                f"(see .env.example)")
        key = read_key((endpoint.get("api_key_env", ""),),
                       (f"{endpoint.get('api_key_env', '')}_FILE",))
        if not key and endpoint.get("key_required", True):
            raise SystemExit(
                f"provider {provider!r} needs {endpoint.get('api_key_env')} "
                f"(set it, or point *_API_KEY_FILE at a file holding it)")
        return key or "not-required", base_url

    # Keep Azure credentials paired with the Azure endpoint.  Otherwise a stale
    # exported OPENAI_API_KEY could accidentally be sent to an Azure URL (or the
    # reverse) because dotenv intentionally does not override shell variables.
    if provider == "openai":
        azure_base_url = os.environ.get("AZURE_OPENAI_BASE_URL", "").strip()
        azure_configured = azure_base_url or any(
            os.environ.get(name, "").strip()
            for name in ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_KEY_FILE")
        )
        if azure_configured:
            if not azure_base_url:
                raise SystemExit(
                    "Azure credentials are configured but AZURE_OPENAI_BASE_URL is missing"
                )
            key = read_key(
                ("AZURE_OPENAI_API_KEY",), ("AZURE_OPENAI_API_KEY_FILE",)
            )
            names = "AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_KEY_FILE"
            base_url = azure_base_url
        else:
            key = read_key(("OPENAI_API_KEY",), ("OPENAI_API_KEY_FILE",))
            names = "OPENAI_API_KEY, OPENAI_API_KEY_FILE"
            base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    else:
        key = read_key(("OPENROUTER_API_KEY",), ("OPENROUTER_API_KEY_FILE",))
        names = "OPENROUTER_API_KEY, OPENROUTER_API_KEY_FILE"
        base_url = PROVIDERS[provider][1]

    if not key:
        raise SystemExit(
            f"no API key for provider {provider!r}; set one of {names} "
            f"(in the repo-root .env, or exported)"
        )
    return key, base_url


def _resolved_provider(model: str, provider: str = "") -> str:
    return provider or (
        "openai" if model.startswith(("gpt-", "o1", "o3", "o4")) else "openrouter"
    )


def _client(model: str, provider: str = ""):
    from openai import OpenAI

    provider = _resolved_provider(model, provider)
    key, base_url = _provider_config(provider)
    return OpenAI(api_key=key, base_url=base_url), provider


def _provider_backend(provider: str) -> str:
    """Auditable backend label without exposing the endpoint or credentials."""
    if provider == "openai" and os.environ.get("AZURE_OPENAI_BASE_URL", "").strip():
        return "azure-openai-compatible"
    return provider


def _endpoint_sha256(provider: str) -> str:
    """Stable endpoint identity without persisting the endpoint or a secret."""
    if provider == "openai":
        endpoint = (
            os.environ.get("AZURE_OPENAI_BASE_URL", "").strip()
            or os.environ.get("OPENAI_BASE_URL", "").strip()
            or "https://api.openai.com/v1"
        )
    else:
        endpoint = PROVIDERS.get(provider, ("", f"provider:{provider}"))[1]
    return hashlib.sha256(str(endpoint).encode("utf-8")).hexdigest()


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


_retries_seen = 0          # provider retries this process has done, ever


RESPONSES_API = True       # use the Responses API on the openai/Azure provider


def _create_with_retry(client, *, attempts: int = MAX_RETRIES + 1, create=None,
                       **kwargs):
    """One chat call, retrying the transient provider failures.

    A shared-pool 429 is the normal weather on an aggregated endpoint, and a
    single one used to kill a whole grid run mid-browse. Retries on rate limits,
    5xx and connection drops; anything else (a bad model id, a bad key) is a
    real error and is raised immediately.
    """
    import openai as openai_sdk

    # OpenAI's gpt-5.6-* models carry a non-none default reasoning_effort, and
    # /v1/chat/completions rejects function tools when one is set:
    #   "Function tools with reasoning_effort are not supported for gpt-5.6-terra
    #    ... use /v1/responses or set reasoning_effort to 'none'."
    # The CUA turn is the only call that sends tools, so without this the model
    # named throughout the runbook and the Shopping suite cannot drive the agent at
    # all. gpt-5.5 accepts the same argument, so this is safe across both.
    model_id = str(kwargs.get("model") or "")
    if kwargs.get("tools") and "reasoning_effort" not in kwargs and model_id.startswith("gpt-5"):
        kwargs["reasoning_effort"] = "none"

    retryable = (openai_sdk.RateLimitError, openai_sdk.APIConnectionError,
                 openai_sdk.InternalServerError)
    call = create or client.chat.completions.create
    for attempt in range(attempts):
        try:
            return call(**kwargs)
        except retryable as exc:
            if attempt == attempts - 1:
                raise
            global _retries_seen
            _retries_seen += 1
            delay = 5 * 2 ** attempt          # 5, 10, 20, 40s
            print(f"  [{type(exc).__name__}] retrying in {delay}s "
                  f"({attempt + 1}/{attempts - 1})", flush=True)
            time.sleep(delay)


# Prompt caching. Most providers cache a repeated prefix on their own -- OpenAI,
# Grok, Moonshot, DeepSeek, Z.AI and Gemini 2.5+ need nothing from us. Anthropic
# and Qwen only cache what an explicit breakpoint marks, and this loop is the
# worst case for that: every step resends the whole history, so the prefix that
# could be cached is nearly the entire bill.
CACHE_EXPLICIT_PREFIXES = ("anthropic/", "qwen/", "google/gemini-1", "google/gemini-2.0")
CACHE_TTL = "1h"                  # long enough to span one cell's browsing
CACHE_MAX_BREAKPOINTS = 4         # Anthropic's hard limit
# Models that answered "no" once: never marked again in this process.
_cache_refused: set[str] = set()
# Whether to mark breakpoints at all. Off makes a run cost what an uncached run
# costs, which is what a cost comparison needs; it cannot switch off the
# automatic caching OpenAI, Azure, Grok, Moonshot, DeepSeek and Z.AI do on their
# own, so an "off" run is only uncached for Anthropic and Qwen.
PROMPT_CACHE = True


def needs_explicit_cache(model: str) -> bool:
    return (PROMPT_CACHE and model.startswith(CACHE_EXPLICIT_PREFIXES)
            and model not in _cache_refused)


def cache_marked(messages: list[dict], model: str) -> list[dict]:
    """A copy of the messages with cache breakpoints, for providers needing them.

    The breakpoints are the system prompt plus the newest few cacheable turns:
    a provider caches the prefix up to a breakpoint, so keeping one near the end
    is what makes step N reuse the work of step N-1 instead of paying for the
    whole transcript again. The originals keep plain string content, so nothing
    accumulates markers across steps.
    """
    if not needs_explicit_cache(model):
        return messages
    marks = [0] if messages else []
    for index in range(len(messages) - 1, 0, -1):
        if len(marks) >= CACHE_MAX_BREAKPOINTS:
            break
        if messages[index].get("role") in ("user", "tool", "system"):
            marks.append(index)
    marked = list(messages)
    for index in marks:
        message = dict(marked[index])
        content = message.get("content")
        if not isinstance(content, str) or not content:
            continue          # nothing to attach a breakpoint to
        message["content"] = [{
            "type": "text", "text": content,
            "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
        }]
        marked[index] = message
    return marked


def _strip_cache_control(messages):
    """The same messages with every breakpoint removed, for a retry."""
    plain = []
    for message in messages or []:
        content = message.get("content")
        if isinstance(content, list):
            text = "".join(part.get("text", "") for part in content
                           if isinstance(part, dict))
            message = {**message, "content": text}
        plain.append(message)
    return plain


class Meter:
    """Every model call one cell made: role, tokens, dollars, wall time.

    The bill and the clock are results too -- a paper has to state what a
    setting cost and how long a task took -- so they are recorded beside the
    trajectory instead of being reconstructed from provider dashboards months
    later, when the prices have moved and the runs are indistinguishable.
    """

    ROLES = ("persona", "agent", "agent_summary", "rubric_judge")

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add(self, role: str, model: str, provider: str, resp, ms: float) -> dict:
        usage = getattr(resp, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        # OpenRouter returns what it actually charged when asked for usage, and
        # that beats a list price: it already accounts for the provider it
        # routed to, cache reads and any discount.
        reported = getattr(usage, "cost", None)
        # What the registry says these tokens are worth at list price.
        list_cost = model_registry.cost_of(model, prompt_tokens, completion_tokens)
        # Azure is costed like every other provider: whose card it lands on is
        # not something the report tracks, so there is one cost per call.
        if isinstance(reported, (int, float)):
            cost, source = float(reported), "provider"
        else:
            cost = list_cost
            source = "registry" if cost is not None else "unknown"
        details = getattr(usage, "prompt_tokens_details", None)
        completion_details = getattr(usage, "completion_tokens_details", None)
        call = {
            "role": role, "model": model, "provider": provider,
            "ms": round(ms), "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            # What the cache actually did on this call: read tokens, written
            # tokens and the discount the provider granted. Without these a
            # caching change cannot be shown to have worked.
            "cached_prompt_tokens": getattr(details, "cached_tokens", None),
            "cache_write_tokens": getattr(details, "cache_write_tokens", None),
            "cache_discount": getattr(usage, "cache_discount", None),
            # A reasoning model bills thinking as completion tokens, so the
            # split matters when comparing models on cost per useful answer.
            "reasoning_tokens": getattr(completion_details, "reasoning_tokens", None),
            "cost_usd": cost, "cost_source": source,
            "list_cost_usd": list_cost,
        }
        self.calls.append(call)
        return call

    def totals(self) -> dict:
        """Per-role and overall totals, with unpriced calls counted, not hidden."""
        by_role: dict[str, dict] = {}
        for call in self.calls:
            bucket = by_role.setdefault(call["role"], {
                "calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "ms": 0, "cost_usd": 0.0, "list_cost_usd": 0.0,
                "retries": 0, "unpriced_calls": 0})
            bucket["calls"] += 1
            bucket["retries"] += call.get("retries") or 0
            bucket["list_cost_usd"] = round(
                bucket["list_cost_usd"] + (call.get("list_cost_usd") or 0.0), 6)
            bucket["prompt_tokens"] += call["prompt_tokens"]
            bucket["completion_tokens"] += call["completion_tokens"]
            bucket["ms"] += call["ms"]
            if call["cost_usd"] is None:
                bucket["unpriced_calls"] += 1
            else:
                bucket["cost_usd"] = round(bucket["cost_usd"] + call["cost_usd"], 6)
        return {
            "calls": len(self.calls),
            "by_role": by_role,
            "prompt_tokens": sum(c["prompt_tokens"] for c in self.calls),
            "completion_tokens": sum(c["completion_tokens"] for c in self.calls),
            "model_ms": sum(c["ms"] for c in self.calls),
            # Provider retries (429s, 5xx, dropped connections). They cost no
            # tokens but they are most of the wall clock when a provider is
            # busy, so a latency number is unreadable without them.
            "retries": sum(c.get("retries") or 0 for c in self.calls),
            "cost_usd": round(sum(c["cost_usd"] or 0.0 for c in self.calls), 6),
            "list_cost_usd": round(
                sum(c.get("list_cost_usd") or 0.0 for c in self.calls), 6),
            "unpriced_calls": sum(c["cost_usd"] is None for c in self.calls),
        }


def dump_response(resp) -> dict:
    """A JSON-safe copy of a provider response, whatever SDK object it is."""
    for attempt in (lambda: resp.model_dump(exclude_none=True),
                    lambda: json.loads(resp.model_dump_json()),
                    lambda: json.loads(json.dumps(resp, default=lambda o: getattr(
                        o, "__dict__", None) or str(o)))):
        try:
            dumped = attempt()
        except Exception:
            continue
        if isinstance(dumped, dict):
            return dumped
    return {"repr": repr(resp)[:4000]}


def metered(client, meter: Meter | None, role: str, *, provider: str, **kwargs):
    """One chat call, timed and billed into the meter. Returns (resp, call)."""
    retries_before = _retries_seen
    if provider == "openai" and RESPONSES_API:
        # Chat completions on this deployment return a reasoning token count and
        # no reasoning; the Responses API returns a summary of it for the same
        # tokens. The shim keeps the caller in chat-completions terms.
        kwargs["create"] = lambda **call_kwargs: responses_shim.create(
            client, **call_kwargs)
    if provider == "openrouter":
        # Ask OpenRouter to report the charge for this call.
        body = dict(kwargs.get("extra_body") or {})
        body.setdefault("usage", {"include": True})
        kwargs["extra_body"] = body
    started = time.monotonic()
    try:
        resp = _create_with_retry(client, **kwargs)
    except Exception as exc:
        # An undocumented provider may refuse cache_control. Losing hours of
        # browsing to a caching optimisation is not a trade worth making, so the
        # turn is retried plain and this model is never marked again.
        if "cache_control" not in str(exc) or not kwargs.get("messages"):
            raise
        model_name = str(kwargs.get("model", ""))
        _cache_refused.add(model_name)
        print(f"  [{model_name} rejected cache_control: {exc}] "
              f"retrying without prompt caching", flush=True)
        kwargs["messages"] = _strip_cache_control(kwargs["messages"])
        resp = _create_with_retry(client, **kwargs)
    elapsed_ms = (time.monotonic() - started) * 1000
    call = None
    if meter is not None:
        call = meter.add(role, str(kwargs.get("model", "")), provider, resp, elapsed_ms)
        call["retries"] = _retries_seen - retries_before
    return resp, call


PERSONA_USER_RULES = prompt("persona_user")
MATCHED_PAIR_PERSONA_USER_RULES = prompt("persona_user_matched_pair")
# Not renamed with the directory: this string is written into every
# record and cache key, and changing it would invalidate what is saved.
OPENING_CACHE_SCHEMA = "odyssey.persona-opening.v1"


def _persona_rules(profile_doc: dict | None) -> str:
    return (
        MATCHED_PAIR_PERSONA_USER_RULES
        if isinstance(profile_doc, dict) and profile_doc.get("matched_pair")
        else PERSONA_USER_RULES
    )


def persona_opening_cache(
    task: dict,
    *,
    suite_id: str,
    persona: str,
    replicate_id: str,
    persona_path: Path | None,
    model: str,
    provider: str,
    temperature: float,
) -> dict | None:
    """Return a content-addressed cache spec for one simulated-user opening."""
    if persona_path is None:
        return None
    profile_doc = persona_lib.load_persona(persona_path)
    resolved_provider = _resolved_provider(model, provider)
    rules = _persona_rules(profile_doc)
    identity = {
        "schema_version": OPENING_CACHE_SCHEMA,
        "suite_id": suite_id,
        "task_id": task["task_id"],
        "task_sha256": task_router.canonical_sha256(task),
        "persona": persona,
        "persona_profile_sha256": hashlib.sha256(persona_path.read_bytes()).hexdigest(),
        "persona_model": model,
        "persona_provider": resolved_provider,
        "persona_backend": _provider_backend(resolved_provider),
        "persona_endpoint_sha256": _endpoint_sha256(resolved_provider),
        "temperature": temperature,
        "persona_prompt_sha256": hashlib.sha256(rules.encode("utf-8")).hexdigest(),
        "replicate_id": replicate_id,
    }
    cache_key = task_router.canonical_sha256(identity)
    path = (
        REPO
        / "artifacts"
        / "persona-openings"
        / suite_id
        / task["task_id"]
        / persona
        / f"{replicate_id}__{cache_key[:16]}.json"
    )
    return {"path": path, "cache_key": cache_key, "identity": identity}


class PersonaUser:
    """The person asking: a persona LLM holding the Odysseys task as its need.

    With no persona (the control arm) the opening message is the Odysseys task
    verbatim -- exactly the original benchmark -- and follow-up questions are
    answered by the same LLM without a profile.
    """

    def __init__(self, task: dict, persona_path: Path | None, model: str,
                 provider: str = "", temperature: float = 0.7,
                 opening_cache: dict | None = None, meter: "Meter | None" = None):
        self.client = None
        self.meter = meter
        self.provider = _resolved_provider(model, provider)
        self.model, self.temperature = model, temperature
        self.profile_snapshot = None
        if persona_path is None:
            rules = PERSONA_USER_RULES.format(goal=task["confirmed_task"])
            system = "You are a person.\n\n" + rules
        else:
            self.client, self.provider = _client(model, provider)
            profile_doc = persona_lib.load_persona(persona_path)
            evaluation_dimensions = profile_doc.get("evaluation_dimensions") or []
            if (not isinstance(evaluation_dimensions, list)
                    or len(evaluation_dimensions) != len(set(evaluation_dimensions))):
                raise ValueError(f"invalid evaluation_dimensions in {persona_path}")
            attributes = profile_doc.get("attributes") or {}
            missing = [key for key in evaluation_dimensions if key not in attributes]
            if missing:
                raise ValueError(
                    f"evaluation dimensions missing from {persona_path}: {missing}"
                )
            values = {
                key: (attributes[key].get("value")
                      if isinstance(attributes[key], dict) else attributes[key])
                for key in evaluation_dimensions
            }
            profile_narrative = "\n\n".join(
                persona_lib.build_dimension_narrative(profile_doc)
            )
            self.profile_snapshot = {
                "persona_id": profile_doc.get("persona_id"),
                "version": profile_doc.get("version"),
                "interaction_protocol": profile_doc.get(
                    "interaction_protocol", "natural_user.v1"
                ),
                "profile_sha256": hashlib.sha256(persona_path.read_bytes()).hexdigest(),
                "profile_narrative": profile_narrative,
                "evaluation_dimensions": list(evaluation_dimensions),
                "evaluation_values": values,
            }
            matched_pair = profile_doc.get("matched_pair")
            if matched_pair is not None:
                if not isinstance(matched_pair, dict):
                    raise ValueError(f"invalid matched_pair metadata in {persona_path}")
                applicable = matched_pair.get("applicable_task_ids")
                criteria = matched_pair.get("task_criteria")
                task_id = task["task_id"]
                if not isinstance(applicable, list) or task_id not in applicable:
                    raise ValueError(
                        f"persona {persona_path.stem!r} is not applicable to task {task_id}"
                    )
                if not isinstance(criteria, dict) or not isinstance(criteria.get(task_id), dict):
                    raise ValueError(
                        f"persona {persona_path.stem!r} has no task criterion for {task_id}"
                    )
                protocol_hash = str(matched_pair.get("protocol_sha256") or "")
                if not re.fullmatch(r"[0-9a-f]{64}", protocol_hash):
                    raise ValueError(f"invalid matched-pair protocol hash in {persona_path}")
                raw_protocol_path = matched_pair.get("protocol_path")
                if not isinstance(raw_protocol_path, str) or not raw_protocol_path.strip():
                    raise ValueError(f"missing matched-pair protocol path in {persona_path}")
                protocol_path = Path(raw_protocol_path).expanduser()
                if not protocol_path.is_absolute():
                    protocol_path = HERE / protocol_path
                if not protocol_path.is_file():
                    raise ValueError(
                        f"matched-pair protocol is missing for {persona_path}: {protocol_path}"
                    )
                actual_protocol_hash = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
                if actual_protocol_hash != protocol_hash:
                    raise ValueError(
                        f"matched-pair profile is stale for {persona_path}; regenerate it"
                    )
                criterion = criteria[task_id]
                arm = matched_pair.get("arm")
                if arm not in {"positive", "negative"}:
                    raise ValueError(f"invalid matched-pair arm in {persona_path}")
                changed_dimension = matched_pair.get("changed_dimension")
                if evaluation_dimensions != [changed_dimension]:
                    raise ValueError(
                        f"matched-pair evaluation dimension mismatch in {persona_path}"
                    )
                if values[changed_dimension] != matched_pair.get("target_value"):
                    raise ValueError(
                        f"matched-pair target value mismatch in {persona_path}"
                    )
                task_observables = criterion.get(f"{arm}_observables")
                if not isinstance(task_observables, list) or not task_observables:
                    raise ValueError(
                        f"matched-pair criterion has no {arm}_observables in {persona_path}"
                    )
                self.profile_snapshot["matched_pair"] = {
                    key: matched_pair.get(key)
                    for key in (
                        "schema_version",
                        "experiment_id",
                        "protocol_path",
                        "protocol_sha256",
                        "pair_id",
                        "axis_id",
                        "axis_label",
                        "arm",
                        "profile_name",
                        "counterpart_profile_name",
                        "changed_dimension",
                        "target_value",
                        "opposite_value",
                    )
                }
                self.profile_snapshot["matched_pair"]["adherence_rubric"] = {
                    "behavioral_definition": matched_pair.get("behavioral_definition"),
                    "generic_observables": matched_pair.get("generic_observables"),
                    "task_observables": task_observables,
                    "opposite_task_observables": criterion.get(
                        f"{'negative' if arm == 'positive' else 'positive'}_observables"
                    ),
                    "inherited_task_signals": criterion.get("inherited_task_signals"),
                    "contradictions": matched_pair.get("contradictions"),
                    "opposite_behavioral_definition": matched_pair.get(
                        "opposite_behavioral_definition"
                    ),
                    "opposite_generic_observables": matched_pair.get(
                        "opposite_generic_observables"
                    ),
                    "task_label": criterion.get("task_label"),
                    "rationale": criterion.get("rationale"),
                }
            interaction_protocol = profile_doc.get("interaction_protocol")
            if matched_pair is not None:
                if interaction_protocol != "matched_pair_full_coverage.v1":
                    raise ValueError(
                        f"matched-pair profile has an invalid interaction_protocol "
                        f"in {persona_path}"
                    )
                rules_template = MATCHED_PAIR_PERSONA_USER_RULES
            else:
                rules_template = PERSONA_USER_RULES
            rules = rules_template.format(goal=task["confirmed_task"])
            system = persona_lib.persona_system_prompt(persona_path, role="a person") + \
                "\n\n# Right now\n\n" + rules
        self.messages = [{"role": "system", "content": system}]
        if persona_path is None:
            self.opening = task["confirmed_task"]
            self.messages += [{"role": "user", "content": "What do you ask the assistant?"},
                              {"role": "assistant", "content": self.opening}]
        else:
            instruction = "Write the message you send the assistant. Only the message itself."
            self.opening = self._cached_opening(opening_cache)
            if self.opening is None:
                self.opening = self._say(instruction)
                self._store_opening(opening_cache, self.opening)
            else:
                # Preserve the exact chat history a generated opening would
                # have produced, so clarification replies remain comparable.
                self.messages += [
                    {"role": "user", "content": instruction},
                    {"role": "assistant", "content": self.opening},
                ]
            if not self.opening:
                raise RuntimeError("persona LLM produced no opening request")
        self.opening_cache = self._opening_cache_metadata(opening_cache)
        self.transcript = [{"role": "user", "text": self.opening}]

    @staticmethod
    def _cached_opening(spec: dict | None) -> str | None:
        if spec is None:
            return None
        path = spec["path"]
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid persona opening cache {path}: {exc}") from exc
        opening = payload.get("opening")
        if (
            payload.get("schema_version") != OPENING_CACHE_SCHEMA
            or payload.get("cache_key") != spec["cache_key"]
            or payload.get("identity") != spec["identity"]
            or not isinstance(opening, str)
            or not opening.strip()
            or payload.get("opening_sha256")
            != hashlib.sha256(opening.encode("utf-8")).hexdigest()
        ):
            raise ValueError(
                f"persona opening cache failed integrity checks: {path}; "
                "delete that one cache file and regenerate the opening"
            )
        spec["hit"] = True
        return opening.strip()

    @staticmethod
    def _store_opening(spec: dict | None, opening: str) -> None:
        if spec is None or not opening.strip():
            return
        path = spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": OPENING_CACHE_SCHEMA,
            "cache_key": spec["cache_key"],
            "identity": spec["identity"],
            "opening": opening.strip(),
            "opening_sha256": hashlib.sha256(opening.strip().encode("utf-8")).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, path)
        spec["hit"] = False

    def _opening_cache_metadata(self, spec: dict | None) -> dict | None:
        if spec is None:
            return None
        path = spec["path"]
        try:
            display_path = path.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            display_path = path.name
        return {
            "schema_version": OPENING_CACHE_SCHEMA,
            "cache_key": spec["cache_key"],
            "path": display_path,
            "cache_hit": bool(spec.get("hit")),
            "opening_sha256": hashlib.sha256(
                self.opening.encode("utf-8")
            ).hexdigest(),
        }

    def _say(self, prompt: str) -> str:
        # The control opening is deterministic and needs no API key.  Only
        # create its persona client if the CUA later asks a question.
        if self.client is None:
            self.client, self.provider = _client(self.model, self.provider)
        self.messages.append({"role": "user", "content": prompt})
        resp, _ = metered(self.client, self.meter, "persona",
                          provider=self.provider, model=self.model,
                          messages=cache_marked(self.messages, self.model),
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
        info = {"model": self.model, "provider": self.provider,
                "backend": _provider_backend(self.provider),
                "temperature": self.temperature}
        if self.opening_cache is not None:
            info["opening_cache"] = self.opening_cache
        if self.profile_snapshot is not None:
            info["persona_profile"] = self.profile_snapshot
        return info


def run_agent(task: dict, user: PersonaUser, model: str, *, max_steps: int,
              headless: bool, temperature: float,
              profile_dir: str | os.PathLike = DEFAULT_PROFILE,
              provider: str = "", meter: "Meter | None" = None,
              shots_dir: str | os.PathLike | None = None,
              nudge_proactive: bool = False) -> dict:
    client, provider = _client(model, provider)
    # The CUA carries no persona: it knows the user only through what they say.
    system = AGENT_RULES + (f"\n\n{PROACTIVE_NUDGE}" if nudge_proactive else "")
    real = task.get("real")
    if real:
        # As in REAL's own harness, the user is already on the site; without
        # this the agent wastes steps searching the open web for a sandbox.
        system += (f"\n\n# Where you are\n\nThe user's browser is already open on "
                   f"{real['site']} in tab 1 ({real['url']}). Do the task on that "
                   f"site; it is a self-contained replica, so do not look for the "
                   f"real one.")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user.opening}]
    questions = 0

    browser = Browser(headless=headless, profile_dir=profile_dir,
                      shots_dir=shots_dir)
    trajectory: list[dict] = []
    # One entry per model turn: what it thought, what it answered, what it
    # called, what it cost and how long it waited. The trajectory records what
    # the tools did; this records what the model did.
    turns: list[dict] = []
    answer, stop_reason, empty_turns, text_turns = "", "max_steps", 0, 0
    real_state, real_error = None, ""
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    try:
        if real:
            # Reset before the first step so the run starts from the task's
            # declared state, not from whatever the previous cell left behind.
            browser._real_reset(real["url"], f"{real['version']}.{real['id']}")
            browser.open_tab(real["url"])
        for step in range(max_steps):
            resp, call = metered(
                client, meter, "agent", provider=provider,
                model=model, messages=cache_marked(messages, model), tools=TOOLS,
                temperature=temperature)
            msg = resp.choices[0].message
            # The whole response, reasoning and tool calls included: a provider
            # that returns a reasoning trace puts it on the message, and the
            # dump keeps fields this code never names.
            turns.append({"step": step, "kind": "agent",
                          "response": dump_response(resp),
                          "call": call})
            messages.append(msg.model_dump(exclude_none=True))
            calls = msg.tool_calls or []
            if not calls and not (msg.content or "").strip():
                # Neither a tool call nor a word. That is an API hiccup, not a
                # result: scoring it would record a transient failure as this
                # persona's performance. Retry the turn; give up only if the
                # model stays mute.
                messages.pop()
                empty_turns += 1
                if empty_turns >= MAX_RETRIES:
                    stop_reason = "no_model_output"
                    break
                time.sleep(3)
                continue
            empty_turns = 0
            if calls:
                text_turns = 0            # it is working again
            if not calls:
                # Text with no tool call is usually a progress note -- "the page
                # is loading, I'll check the transcript next" -- not an answer.
                # Taking it as one closed the browser mid-task and handed the
                # judges an unfinished run, which then scored as the agent's
                # failure. Nudge instead, and only give up if it keeps talking.
                text_turns += 1
                if text_turns >= MAX_TEXT_TURNS:
                    answer, stop_reason = (msg.content or "").strip(), "no_tool_call"
                    break
                messages.append({"role": "user", "content":
                                 "That was not a tool call. If you are still "
                                 "working, continue with the tools. If you are "
                                 "done, call finish with your complete final "
                                 "answer -- plain text is not delivered."})
                continue
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
                # One frame per step, whatever the tool: a read_page that
                # returned nothing looks identical in a text log whether the
                # page was empty, still loading or a captcha wall.
                shot = browser.shot(f"{step:02d}-{name}", args.get("tab_id"))
                trajectory.append({
                    "step": step, "tool": name, "args": args, "screenshot": shot,
                    # result_preview is what the judge reads; result is the
                    # whole tool output the model was given, so a trajectory can
                    # be replayed and audited after the fact.
                    "result_preview": str(result)[:400],
                    "result": str(result)[:PAGE_CHARS + 500],
                    "tool_call_id": call.id})
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
                final, summary_call = metered(
                    client, meter, "agent_summary", provider=provider,
                    model=model, messages=cache_marked(messages, model),
                    temperature=temperature)
                turns.append({"step": len(turns), "kind": "agent_summary",
                              "response": dump_response(final),
                              "call": summary_call})
                answer = (final.choices[0].message.content or "").strip()
            except Exception as exc:
                answer, stop_reason = "", f"max_steps_no_summary ({type(exc).__name__})"
        open_tabs = browser.open_tabs()
        # One frame per tab left open: the rubrics score what stayed open, so
        # this is the evidence for those items.
        final_shots = [browser.shot(f"final-tab{tab['tab_id']}", tab["tab_id"])
                       for tab in open_tabs]
        if real:
            # The state is the only evidence a REAL task has: read it before the
            # browser closes, and record why if it cannot be read, because an
            # unread state and a failed task look identical downstream.
            try:
                real_state = browser._real_state(real["url"])
            except Exception as exc:
                real_error = f"{type(exc).__name__}: {exc}"
    finally:
        browser.close()

    finished_at = datetime.now(timezone.utc)
    return {"answer": answer, "stop_reason": stop_reason, "steps": len(trajectory),
            "max_steps": max_steps, "trajectory": trajectory, "turns": turns,
            "open_tabs": open_tabs, "final_screenshots": final_shots,
            "real_state": real_state, "real_state_error": real_error,
            "conversation": user.transcript, "user": user.info(),
            "timing": {"started_at": started_at.isoformat(),
                       "finished_at": finished_at.isoformat(),
                       "wall_seconds": round(time.monotonic() - started, 3),
                       "model_ms": sum((t["call"] or {}).get("ms", 0) for t in turns)},
            "arm": {"model": model, "provider": provider,
                    "backend": _provider_backend(provider), "temperature": temperature,
                    "proactive_nudge": nudge_proactive,
                    "prompt_cache": ("explicit_breakpoints"
                                     if needs_explicit_cache(model)
                                     else "provider_automatic_only"
                                     if PROMPT_CACHE else "off")}}


# --------------------------------------------------------------------------- #
# Judge
# --------------------------------------------------------------------------- #
JUDGE_PROMPT = prompt("rubric_judge")


def judge_run(task: dict, run: dict, *, judge_model: str, judge_provider: str,
              meter: "Meter | None" = None) -> dict:
    client, resolved_provider = _client(judge_model, judge_provider)
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
    for attempt in range(MAX_RETRIES):
        try:
            resp, _ = metered(client, meter, "rubric_judge",
                              provider=resolved_provider,
                              model=judge_model,
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
        return {"judge_model": judge_model, "judge_provider": resolved_provider,
                "judge_backend": _provider_backend(resolved_provider),
                "error": last_error or "empty judge response",
                "verdicts": {}, "met": None, "total": len(task["rubrics"]),
                "score": None, "trajectory_efficiency": None}
    return {"judge_model": judge_model, "judge_provider": resolved_provider,
            "judge_backend": _provider_backend(resolved_provider), "verdicts": verdicts,
            **score_verdicts(task, verdicts, run["steps"])}


REAL_BOOLEAN_PROMPT = prompt("real_boolean_check")


def real_jmespath(check: dict, state: dict) -> tuple[bool, str]:
    """(passed, what it found). Raises only if the query itself is malformed."""
    found = jmespath.search(check["query"], state)
    passed = found == check["expected_value"]
    return passed, (f"{check['query']} -> {json.dumps(found, ensure_ascii=False)[:200]} "
                    f"(wanted {json.dumps(check['expected_value'], ensure_ascii=False)})")


def real_llm_boolean(check: dict, task: dict, run: dict, *, judge_model: str,
                     judge_provider: str, meter: "Meter | None") -> tuple[bool, str]:
    """(passed, the judge's reason). Raises if the judge never answers usably."""
    client, resolved_provider = _client(judge_model, judge_provider)
    text = REAL_BOOLEAN_PROMPT.format(
        task=task["confirmed_task"], rubric=check["rubric"],
        answer=run.get("answer") or "(the agent produced no final answer)")
    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            resp, _ = metered(client, meter, "real_boolean_check",
                              provider=resolved_provider, model=judge_model,
                              messages=[{"role": "user", "content": text}],
                              max_completion_tokens=2000)
            parsed = extract_json(resp.choices[0].message.content or "")
        except (NameError, TypeError, AttributeError):
            raise                      # our bug, not the weather
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("answer"), bool):
            return (parsed["answer"] == check["expected_value"],
                    f"judge said {parsed['answer']}: {str(parsed.get('reason'))[:200]}")
        print(f"  [boolean check returned nothing usable] "
              f"attempt {attempt + 1}/{MAX_RETRIES}", flush=True)
        time.sleep(3)
    raise RuntimeError(last_error or "the judge never returned a usable boolean")


def judge_real(task: dict, run: dict, *, judge_model: str = "",
               judge_provider: str = "", meter: "Meter | None" = None) -> dict:
    """Score a REAL task with its own checks against the site's final state.

    Three kinds, and a task may carry several of each: a vendored agisdk script
    that prints SUCCESS, a jmespath query on the final state, and an llm_boolean
    question about the agent's own answer. The first two are deterministic and
    free; only the last calls a model, and only the tasks that declare one.

    The task passes only if every check passes. A check that cannot run is an
    error, never a failure -- a missing script and an unfinished task must not
    look alike.
    """
    real = task["real"]
    checks = real.get("checks") or []
    needs_model = any(c["type"] == "llm_boolean" for c in checks)
    if needs_model and judge_model:
        # Record where the call actually went, not the empty string a caller
        # that never named a provider passed in.
        try:
            judge_model, judge_provider = model_registry.resolve(judge_model,
                                                                 judge_provider)
        except Exception:
            pass                       # reported below by the call that fails
    base = {"judge_model": f"real-state-checker+{judge_model}" if needs_model
                           else "real-state-checker",
            "judge_provider": judge_provider or None if needs_model else None,
            "total": 1, "communicated": None, "score_communicated": None}
    if run.get("real_state") is None:
        return {**base, "verdicts": {}, "met": None, "score": None,
                "error": run.get("real_state_error") or
                "the sandbox's final state was never read"}
    missing = [s for s in real["eval_scripts"] if not (REAL_EVALS / s).is_file()]
    if missing:
        return {**base, "verdicts": {}, "met": None, "score": None,
                "error": f"checker(s) missing from {REAL_EVALS}: {missing}; "
                         f"run python src/prepare_real.py"}
    if needs_model and not judge_model:
        # Scoring it on the other checks alone would report a pass the task never
        # earned, so the cell is left unscored and says why.
        return {**base, "verdicts": {}, "met": None, "score": None,
                "error": f"{real['id']} has an llm_boolean check but no judge model "
                         f"was passed to judge_real()"}

    state_path = None
    outputs, passed, errors = {}, True, []
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as handle:
            json.dump(run["real_state"], handle)
            state_path = handle.name
        for script in real["eval_scripts"]:
            try:
                proc = subprocess.run(
                    [sys.executable, str(REAL_EVALS / script), state_path],
                    capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                errors.append(f"{script}: timed out after 60s")
                outputs[script] = "TIMEOUT"
                continue
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            outputs[script] = (out or err)[-500:]
            if proc.returncode != 0 and not out:
                errors.append(f"{script}: exit {proc.returncode}: {err[-200:]}")
                continue
            passed = passed and "SUCCESS" in out.upper()
    finally:
        if state_path:
            os.unlink(state_path)

    for i, check in enumerate(checks):
        label = f"{check['type']}[{i}]"
        try:
            if check["type"] == "jmespath":
                ok, detail = real_jmespath(check, run["real_state"])
            elif check["type"] == "llm_boolean":
                ok, detail = real_llm_boolean(
                    check, task, run, judge_model=judge_model,
                    judge_provider=judge_provider, meter=meter)
            else:
                raise RuntimeError(f"unknown check type {check['type']!r}")
        except (NameError, TypeError, AttributeError):
            raise
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
            outputs[label] = f"ERROR: {exc}"[:300]
            continue
        outputs[label] = ("PASS " if ok else "FAIL ") + detail
        passed = passed and ok

    if errors:
        # A checker that crashed says nothing about the agent, so the cell is
        # left unscored and a resume retries it.
        return {**base, "verdicts": {"R1": {"met": None, "reason": json.dumps(outputs)}},
                "met": None, "score": None, "error": "; ".join(errors)}
    return {**base,
            "verdicts": {"R1": {"met": passed, "communicated": None,
                                "reason": json.dumps(outputs)}},
            "met": int(passed), "score": float(passed),
            "trajectory_efficiency": round(float(passed) / max(run["steps"], 1), 4)}


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
def _is_scored(path: Path, *, suite_id: str | None = None,
               task_sha256: str | None = None,
               run_config_sha256: str | None = None,
               resume_config_sha256: str | None = None) -> bool:
    """True only for a result that actually carries a score.

    A run whose judge failed writes a result.json with score None; treating that
    as done would make the failure permanent on every resume.
    """
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    score = (rec.get("judgement") or {}).get("score")
    if (isinstance(score, bool) or not isinstance(score, (int, float))
            or not 0 <= float(score) <= 1):
        return False
    if task_sha256:
        stored_hash = rec.get("task_sha256")
        snapshot_hash = (
            task_router.canonical_sha256(rec["task_snapshot"])
            if isinstance(rec.get("task_snapshot"), dict) else None
        )
        if stored_hash and snapshot_hash and stored_hash != snapshot_hash:
            return False
        recorded_hash = snapshot_hash or stored_hash
        if recorded_hash != task_sha256:
            return False
    if suite_id:
        recorded_suite = (rec.get("suite_id") or rec.get("task_suite")
                          or (rec.get("suite_snapshot") or {}).get("id"))
        # A legacy result has no suite field.  A matching frozen task hash is
        # sufficient to identify it without guessing from its old directory.
        if recorded_suite is not None and recorded_suite != suite_id:
            return False
        if recorded_suite is None and not task_sha256:
            return False
    if run_config_sha256:
        stored_config_hash = rec.get("run_config_sha256")
        actual_config_hash = (
            task_router.canonical_sha256(rec["run_config"])
            if isinstance(rec.get("run_config"), dict) else None
        )
        if (stored_config_hash and actual_config_hash
                and stored_config_hash != actual_config_hash):
            return False
        if (actual_config_hash or stored_config_hash) != run_config_sha256:
            return False
    if resume_config_sha256:
        stored_resume_hash = rec.get("resume_config_sha256")
        actual_resume_hash = (
            task_router.canonical_sha256(rec["resume_config"])
            if isinstance(rec.get("resume_config"), dict) else None
        )
        if (stored_resume_hash and actual_resume_hash
                and stored_resume_hash != actual_resume_hash):
            return False
        if (actual_resume_hash or stored_resume_hash) != resume_config_sha256:
            return False
    return True


def resolve_tasks(spec: str | None, run_all: bool,
                  tasks: list[dict] | None = None) -> list[dict]:
    """Resolve ordinals or ID prefixes, retaining the old public helper."""
    suite = DEFAULT_TASK_SUITE
    if tasks is not None and tasks is not TASKS:
        suite = task_router.TaskSuite(
            suite_id="selected",
            title="Selected tasks",
            version="adhoc",
            default_personas=[],
            tasks=tasks,
            sources=[],
            task_sources={},
        )
    try:
        return suite.resolve(spec, run_all)
    except task_router.TaskRoutingError as exc:
        raise SystemExit(f"task routing error: {exc}") from exc


def resolve_persona_path(persona: str, suite_id: str) -> Path:
    """Resolve suite-scoped generated personas before legacy global profiles."""
    candidates = [
        HERE / "personas" / suite_id / "matched_pairs" / f"{persona}.yaml",
        HERE / "personas" / suite_id / f"{persona}.yaml",
        HERE / "personas" / f"{persona}.yaml",
    ]
    hits = [path for path in candidates if path.is_file()]
    if not hits:
        searched = ", ".join(str(path) for path in candidates)
        raise SystemExit(f"no persona {persona!r}; searched: {searched}")
    if len(hits) > 1:
        raise SystemExit(
            f"persona {persona!r} is ambiguous for suite {suite_id!r}: "
            + ", ".join(str(path) for path in hits)
        )
    return hits[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    route = ap.add_mutually_exclusive_group()
    route.add_argument("--suite", help="registered task suite (default: catalog default)")
    route.add_argument("--tasks-file", help="one unregistered JSON task file for an ad-hoc run")
    ap.add_argument("--list-suites", action="store_true",
                    help="validate and list registered task suites, then exit")
    ap.add_argument("--list-tasks", action="store_true",
                    help="validate and list tasks in the selected suite/file, then exit")
    ap.add_argument("--task", help="1-based ordinal, task_id prefix, or comma-separated list")
    ap.add_argument("--all", action="store_true", help="run every task in the selected suite")
    ap.add_argument("--persona", default="travel-senior",
                    help="the user asking: a suite-scoped matched-pair name, a name "
                         "under src/personas/ (omit .yaml), or 'none' for the "
                         "Odysseys task text verbatim")
    ap.add_argument("--replicate-id", default="default",
                    help="controlled repeat label; included in the run/cache identity")
    ap.add_argument("--pair-order", choices=("positive-negative", "negative-positive"),
                    help="auditable matched-pair execution order supplied by the planner")
    ap.add_argument("--pair-position", type=int, choices=(1, 2),
                    help="this arm's 1-based position within --pair-order")
    ap.add_argument("--setting", default="",
                    help="experiment setting label, e.g. s1 (group personas) or "
                         "s2 (one-dimension ablation). Results are stored under "
                         "it and it is recorded in every result, so the two "
                         "settings never share a directory or a report row")
    ap.add_argument("--model", default="gpt-5.6-terra",
                    help="the CUA doing the work: a key from src/models.json "
                         "(preferring Azure when that model is deployed there) or "
                         "a raw provider id")
    ap.add_argument("--provider", default="openai",
                    help="override routing for --model, e.g. openrouter for a "
                         "qwen id served somewhere other than DashScope")
    ap.add_argument("--persona-model", default="gpt-5.6-terra",
                    help="the LLM playing the persona user")
    ap.add_argument("--persona-provider", default="openai")
    # Azure serves gpt-5.6-terra; once AZURE_OPENAI_* is configured every
    # "openai" provider call goes there, and a real OpenAI id such as gpt-5.5
    # would 404 with DeploymentNotFound.
    ap.add_argument("--judge-model", default="gpt-5.6-terra")
    ap.add_argument("--judge-provider", default="",
                    help="default: openai for gpt-*/o* ids, openrouter otherwise")
    # 30 demonstrably truncates the medium tasks before the agent can finish.
    # 100, not 50: the REAL booking tasks spend a dozen steps just paging a
    # date picker back to the month the task names, and a cell that stops at the
    # budget tells us nothing about the agent. Runs that finish early cost the
    # same, and step counts are what we report.
    ap.add_argument("--max-steps", type=int, default=100)
    # gpt-5.6-terra accepts only its default temperature; 0.7 is rejected.
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--nudge-proactive", action="store_true",
                    help="tell the agent to ask the user when information is "
                         "missing, instead of leaving it to decide. An arm of "
                         "its own: the default prompt is neutral, so how often "
                         "a model asks unprompted stays measurable")
    ap.add_argument("--no-responses-api", action="store_true",
                    help="call Azure/OpenAI through chat completions instead of "
                         "the Responses API. The Responses API is the default "
                         "there because it returns a reasoning summary for the "
                         "same tokens; this switches back if a deployment "
                         "misbehaves")
    ap.add_argument("--no-screenshots", action="store_true",
                    help="skip the JPEG per page-changing step and per open tab. "
                         "Screenshots are what let a person tell a captcha wall "
                         "from an empty page when reading a trajectory; keeping "
                         "them also means Chrome must load images, which costs "
                         "memory, and roughly 1-3 MB of disk per cell")
    ap.add_argument("--no-prompt-cache", action="store_true",
                    help="do not mark cache breakpoints. Providers that cache "
                         "automatically (OpenAI/Azure, Grok, Moonshot, Z.AI) "
                         "still do; this only makes Anthropic and Qwen runs "
                         "uncached, for a cost comparison that has to be honest "
                         "about what was cached")
    ap.add_argument("--headless", action="store_true",
                    help="no browser window (recommended; required on a server without a display)")
    ap.add_argument("--profile", default="",
                    help="Chrome user-data dir; default is an isolated persistent "
                         "profile under artifacts/chrome-profiles/<suite>/<persona>")
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
    global PROMPT_CACHE, RESPONSES_API
    PROMPT_CACHE = not args.no_prompt_cache
    RESPONSES_API = not args.no_responses_api

    if args.list_suites:
        print("\n".join(task_router.format_suites(TASK_CATALOG)))
        return
    try:
        selected_suite = task_router.load_route(
            suite_id=args.suite,
            tasks_file=args.tasks_file,
            catalog=TASK_CATALOG,
        )
    except task_router.TaskRoutingError as exc:
        raise SystemExit(f"task routing error: {exc}") from exc
    if args.list_tasks:
        print("\n".join(task_router.format_tasks(selected_suite)))
        return

    if not task_router.PERSONA_ID_RE.fullmatch(args.persona):
        raise SystemExit(f"invalid path-unsafe persona id {args.persona!r}")
    if not task_router.PERSONA_ID_RE.fullmatch(args.replicate_id):
        raise SystemExit(f"invalid path-unsafe replicate id {args.replicate_id!r}")
    if (args.pair_order is None) != (args.pair_position is None):
        raise SystemExit("--pair-order and --pair-position must be supplied together")
    persona_path = (
        HERE / "personas" / "none.yaml"
        if args.persona == "none"
        else resolve_persona_path(args.persona, selected_suite.suite_id)
    )
    persona_document = (
        None if args.persona == "none" else persona_lib.load_persona(persona_path)
    )
    matched_pair_document = (
        persona_document.get("matched_pair")
        if isinstance(persona_document, dict) else None
    )
    if matched_pair_document is not None:
        if args.pair_order is None and not args.preview:
            raise SystemExit(
                "matched-pair execution requires --pair-order/--pair-position; "
                "use src/run_matched_pairs.py"
            )
        if args.pair_order is not None:
            ordered_arms = args.pair_order.split("-")
            expected_arm = matched_pair_document.get("arm")
            if ordered_arms[args.pair_position - 1] != expected_arm:
                raise SystemExit(
                    f"pair order/position selects {ordered_arms[args.pair_position - 1]!r} "
                    f"but persona arm is {expected_arm!r}"
                )
    elif args.pair_order is not None:
        raise SystemExit("--pair-order/--pair-position require a matched-pair persona")
    judge_provider = args.judge_provider      # "" -> inferred from the model id
    profile_dir = args.profile or str(
        REPO / "artifacts" / "chrome-profiles" / selected_suite.suite_id / args.persona
    )
    selected_tasks = resolve_tasks(args.task, args.all, selected_suite.tasks)

    if args.preview:
        for task in selected_tasks:
            opening_cache = persona_opening_cache(
                task,
                suite_id=selected_suite.suite_id,
                persona=args.persona,
                replicate_id=args.replicate_id,
                persona_path=None if args.persona == "none" else persona_path,
                model=args.persona_model,
                provider=args.persona_provider,
                temperature=args.temperature,
            )
            user = PersonaUser(task, None if args.persona == "none" else persona_path,
                               args.persona_model, args.persona_provider,
                               temperature=args.temperature,
                               opening_cache=opening_cache)
            print(f"\n=== {selected_suite.suite_id}/{task['task_id'][:12]} "
                  f"[{task['level']}] persona={args.persona} "
                  f"({len(user.opening.split())} words; Odysseys original "
                  f"{len(task['confirmed_task'].split())}) ===\n{user.opening}")
        return

    # A registry key becomes a concrete id plus the cheapest provider that
    # serves it; a raw id passes through untouched.
    args.model, args.provider = model_registry.resolve(args.model, args.provider)
    args.persona_model, args.persona_provider = model_registry.resolve(
        args.persona_model, args.persona_provider)
    args.judge_model, judge_provider = model_registry.resolve(
        args.judge_model, judge_provider)
    resolved_agent_provider = _resolved_provider(args.model, args.provider)
    resolved_persona_provider = _resolved_provider(
        args.persona_model, args.persona_provider
    )
    resolved_judge_provider = _resolved_provider(args.judge_model, judge_provider)
    profile_identity = hashlib.sha256(
        str(Path(profile_dir).expanduser().resolve()).encode("utf-8")
    ).hexdigest()
    base_run_config = {
        "setting": args.setting or None,
        "prompt_cache": not args.no_prompt_cache,
        "screenshots": not args.no_screenshots,
        "responses_api": not args.no_responses_api,
        "proactive_nudge": args.nudge_proactive,
        "persona": args.persona,
        "replicate_id": args.replicate_id,
        "pair_order": args.pair_order,
        "pair_position": args.pair_position,
        "persona_interaction_protocol": (
            "verbatim_control.v1"
            if persona_document is None
            else persona_document.get("interaction_protocol", "natural_user.v1")
        ),
        "persona_profile_sha256": (
            hashlib.sha256(persona_path.read_bytes()).hexdigest()
            if args.persona != "none" else None
        ),
        "agent": {
            "model": args.model,
            "provider": resolved_agent_provider,
            "backend": _provider_backend(resolved_agent_provider),
            "endpoint_sha256": _endpoint_sha256(resolved_agent_provider),
            "temperature": args.temperature,
            "max_steps": args.max_steps,
        },
        "persona_user": {
            "model": args.persona_model,
            "provider": resolved_persona_provider,
            "backend": _provider_backend(resolved_persona_provider),
            "endpoint_sha256": _endpoint_sha256(resolved_persona_provider),
            "temperature": args.temperature,
        },
        "judge": {
            "enabled": not args.no_judge,
            "model": args.judge_model,
            "provider": resolved_judge_provider,
            "backend": _provider_backend(resolved_judge_provider),
            "endpoint_sha256": _endpoint_sha256(resolved_judge_provider),
        },
        "browser": {
            "headless": args.headless,
            "profile_mode": "explicit" if args.profile else "isolated-per-suite-persona",
        },
        "prompt_sha256": {
            "agent": hashlib.sha256(AGENT_RULES.encode("utf-8")).hexdigest(),
            "persona_user": hashlib.sha256(
                (
                    MATCHED_PAIR_PERSONA_USER_RULES
                    if persona_document is not None
                    and persona_document.get("matched_pair")
                    else PERSONA_USER_RULES
                ).encode("utf-8")
            ).hexdigest(),
            "rubric_judge": hashlib.sha256(JUDGE_PROMPT.encode("utf-8")).hexdigest(),
        },
    }
    run_provenance = provenance()
    had_failures = False
    for task in selected_tasks:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # A model id like "qwen/qwen3.8-27b" would otherwise split the run
        # directory across an extra path level.
        safe_model = args.model.replace("/", "-")
        task_hash = task_router.canonical_sha256(task)
        opening_cache = persona_opening_cache(
            task,
            suite_id=selected_suite.suite_id,
            persona=args.persona,
            replicate_id=args.replicate_id,
            persona_path=None if args.persona == "none" else persona_path,
            model=args.persona_model,
            provider=args.persona_provider,
            temperature=args.temperature,
        )
        run_config = {
            **base_run_config,
            "persona_opening_cache_key": (
                opening_cache["cache_key"] if opening_cache is not None else None
            ),
        }
        run_config_hash = task_router.canonical_sha256(run_config)
        resume_config = {
            "run_config_sha256": run_config_hash,
            "profile_path_sha256": profile_identity,
        }
        resume_config_hash = task_router.canonical_sha256(resume_config)
        # v2 paths are namespaced by suite and use the full ID.  Also inspect
        # the old short-ID cell so --skip-existing remains useful after upgrade.
        results_root = Path(args.out) / args.setting if args.setting else Path(args.out)
        cell = results_root / selected_suite.suite_id / task["task_id"] / task_hash
        legacy_cell = Path(args.out) / task["task_id"][:12]
        candidate_dirs = list(cell.glob(f"{args.persona}__{safe_model}__*"))
        candidate_dirs += list(legacy_cell.glob(f"{args.persona}__{safe_model}__*"))
        if args.skip_existing and any(
            _is_scored(
                directory / "result.json",
                suite_id=selected_suite.suite_id,
                task_sha256=task_hash,
                run_config_sha256=run_config_hash,
                resume_config_sha256=resume_config_hash,
            )
            for directory in candidate_dirs
        ):
            print(f"skip {selected_suite.suite_id}/{task['task_id'][:12]} "
                  f"[{task['level']}] persona={args.persona} "
                  f"-- already has a result")
            continue
        out_dir = cell / (
            f"{args.persona}__{safe_model}__{resume_config_hash[:10]}__{stamp}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {selected_suite.suite_id}/{task['task_id'][:12]} "
              f"[{task['level']}] persona={args.persona} "
              f"model={args.model} ===")

        meter = Meter()
        cell_started = time.monotonic()
        try:
            user = PersonaUser(task, None if args.persona == "none" else persona_path,
                               args.persona_model, args.persona_provider,
                               temperature=args.temperature,
                               opening_cache=opening_cache, meter=meter)
            print(f"  user says: {user.opening[:300]!r}", flush=True)
            run = run_agent(task, user, args.model, max_steps=args.max_steps,
                            headless=args.headless, temperature=args.temperature,
                            profile_dir=profile_dir, provider=args.provider,
                            meter=meter,
                            shots_dir=None if args.no_screenshots
                            else out_dir / "shots",
                            nudge_proactive=args.nudge_proactive)
        except Exception as exc:  # a dead task must not take the grid with it
            had_failures = True
            print(f"FAILED: {type(exc).__name__}: {exc}")
            (out_dir / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n",
                                               encoding="utf-8")
            continue
        record = {
            "schema_version": task_router.RESULT_SCHEMA,
            "suite_id": selected_suite.suite_id,
            "suite_snapshot": selected_suite.task_snapshot(task),
            "task_id": task["task_id"],
            "task_sha256": task_hash,
            "level": task["level"],
            "task_snapshot": task,
            "run_config": run_config,
            "run_config_sha256": run_config_hash,
            "resume_config": resume_config,
            "resume_config_sha256": resume_config_hash,
            "setting": args.setting or None,
            "persona": args.persona,
            "replicate_id": args.replicate_id,
            "provenance": run_provenance,
            "run": run,
        }

        def seal_accounting() -> None:
            """Cost and clock for the whole cell, judge included.

            A paper has to state what a setting cost and how long it took; this
            is the only place that knows, because the persona, the agent and the
            judge all bill into one meter.
            """
            record["accounting"] = {
                "cell_wall_seconds": round(time.monotonic() - cell_started, 3),
                # per_call, not calls: totals() carries a "calls" count, and the
                # count silently overwrote this list when they shared a name.
                "per_call": meter.calls,
                **meter.totals(),
            }

        if run["stop_reason"] == "no_model_output":
            had_failures = True
            # Not a result. Leave it unscored so a resume retries the cell.
            record["judgement"] = {
                "error": "model returned no output",
                "verdicts": {},
                "met": None,
                "total": len(task["rubrics"]),
                "score": None,
            }
            seal_accounting()
            (out_dir / "result.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"UNSCORED: model returned no output -> {out_dir / 'result.json'}")
            continue
        if not args.no_judge:
            try:
                record["judgement"] = (
                    judge_real(task, run, judge_model=args.judge_model,
                               judge_provider=judge_provider, meter=meter)
                    if task.get("real")
                    else judge_run(task, run, judge_model=args.judge_model,
                                   judge_provider=judge_provider, meter=meter))
            except Exception as exc:  # never lose a completed browse to the judge
                record["judgement"] = {"error": f"{type(exc).__name__}: {exc}",
                                       "verdicts": {}, "met": None,
                                       "total": len(task["rubrics"]), "score": None}
            j = record["judgement"]
            if j.get("score") is None:
                had_failures = True
                print(f"UNJUDGED ({j.get('error')})  "
                      f"(steps {run['steps']}, stop={run['stop_reason']})")
            else:
                print(f"score {j['met']}/{j['total']} = {j['score']}  "
                      f"communicated {j['communicated']}/{j['total']} "
                      f"-> score on those {j['score_communicated']}  "
                      f"(steps {run['steps']}, asked {(len(run['conversation']) - 1) // 2}, "
                      f"stop={run['stop_reason']})")
        seal_accounting()
        # A REAL state dump is a quarter of a megabyte -- the evidence for the
        # score, but it would bury the record. It goes beside it, with its hash,
        # so result.json stays readable and the evidence stays verifiable.
        state = record["run"].get("real_state")
        if isinstance(state, dict):
            blob = json.dumps(state, ensure_ascii=False, indent=2)
            (out_dir / "real_state.json").write_text(blob, encoding="utf-8")
            record["run"]["real_state"] = {
                "file": "real_state.json",
                "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
                "bytes": len(blob.encode("utf-8")),
            }
        (out_dir / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        acct = record["accounting"]
        print(f"   cost ${acct['cost_usd']:.4f}  "
              f"tokens {acct['prompt_tokens']}/{acct['completion_tokens']}  "
              f"wall {acct['cell_wall_seconds']:.0f}s")
        print(f"-> {out_dir / 'result.json'}")
    if had_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
