"""Offline self-check: the whole pipeline with the LLM and the browser stubbed.

No API key, no network, no Chromium. Fails if task loading, persona injection,
the tool loop or the rubric scoring breaks.

    python scripts/test_pipeline.py
"""
from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import types
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

# This test lives in scripts/; the code it exercises lives in src/.
REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

import run as R  # noqa: E402

# Three tests below replace R.Browser with a stub and do not put it back, so
# anything that needs the real class must have taken a reference first.
REAL_BROWSER = R.Browser
import persona_experiment  # noqa: E402
import task_router  # noqa: E402


def test_tasks():
    # benchmark/v1_tasks.json is the source of truth for the full run: the
    # per-scenario suites held subsets of these same task ids and are retired.
    assert len(R.TASKS) >= 2, len(R.TASKS)
    assert R.TASK_CATALOG.default_suite_id == "odysseys"
    # Counted from the manifest, not written here: a hard-coded 37 fails the day
    # a task is added, which says nothing about whether the suites are correct.
    manifest = json.loads((REPO / "benchmark" / "v1_tasks.json")
                          .read_text(encoding="utf-8"))
    wanted = Counter(t["source"] for t in manifest["tasks"])
    assert len(R.TASKS) == wanted["Odysseys"], (len(R.TASKS), wanted["Odysseys"])
    assert len(R.TASK_CATALOG.get_suite("real").tasks) == wanted["REAL"]
    assert "Aurora, Illinois" in R.TASKS[0]["confirmed_task"]
    ids = [t["task_id"] for t in R.TASKS]
    assert len(set(ids)) == len(ids), "duplicate task_id in tasks.json"
    for t in R.TASKS:
        assert t["rubrics"] and t["confirmed_task"].strip() and t["level"]
    assert R.resolve_tasks("2", False)[0]["task_id"] == R.TASKS[1]["task_id"]
    assert len(R.resolve_tasks("1,3", False)) == 2
    assert R.resolve_tasks(R.TASKS[4]["task_id"][:8], False)[0] is R.TASKS[4]
    assert len(R.resolve_tasks(None, True)) == len(R.TASKS)


def test_task_router():
    catalog = task_router.TaskCatalog.load()
    shopping = catalog.get_suite("odysseys")
    assert [task["task_id"] for task in shopping.tasks] == [
        task["task_id"] for task in R.TASKS
    ]
    assert shopping.task_snapshot(shopping.tasks[0])["task_source"] == (
        "task_suites/odysseys/000-core.json"
    )
    assert len(shopping.sha256) == 64
    tampered = {
        "task_id": shopping.tasks[0]["task_id"],
        "task_snapshot": shopping.tasks[0],
        "task_sha256": "0" * 64,
    }
    try:
        R.task_for_record(tampered)
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered task snapshot was accepted")
    assert task_router.load_route(catalog=catalog) is shopping
    assert task_router.load_route(suite_id="real", catalog=catalog).suite_id == "real"
    assert shopping.resolve(shopping.tasks[0]["task_id"][:8])[0]["task_id"] == (
        shopping.tasks[0]["task_id"])

    for invalid in ("0", str(len(shopping.tasks) + 1), "1,1", "does-not-exist"):
        try:
            shopping.resolve(invalid)
        except task_router.TaskRoutingError:
            pass
        else:
            raise AssertionError(f"invalid selector {invalid!r} was accepted")

    first = copy.deepcopy(shopping.tasks[0])
    second = copy.deepcopy(shopping.tasks[1])
    first["task_id"], second["task_id"] = "same-prefix-a", "same-prefix-b"
    ambiguous = task_router.TaskSuite(
        "ambiguous", "Ambiguous", "1", ["none"], [first, second], [], {}
    )
    try:
        ambiguous.resolve("same-prefix")
    except task_router.TaskRoutingError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("ambiguous ID prefix was accepted")

    numeric = copy.deepcopy(second)
    numeric["task_id"] = "1"
    numeric_suite = task_router.TaskSuite(
        "numeric", "Numeric", "1", ["none"], [first, numeric], [], {}
    )
    assert numeric_suite.resolve("1")[0]["task_id"] == "1"

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        parts = root / "parts"
        parts.mkdir()
        a, b = copy.deepcopy(shopping.tasks[0]), copy.deepcopy(shopping.tasks[1])
        a["task_id"], b["task_id"] = "temporary-a", "temporary-b"
        (parts / "01.json").write_text(json.dumps([a]), encoding="utf-8")
        (parts / "02.json").write_text(json.dumps([b]), encoding="utf-8")
        manifest = root / "task_suites.json"
        manifest.write_text(json.dumps({
            "schema_version": task_router.MANIFEST_SCHEMA,
            "default_suite": "temporary",
            "suites": {
                "temporary": {
                    "title": "Temporary",
                    "version": "7",
                    "task_files": ["parts/*.json"],
                    "default_personas": ["none"],
                }
            },
        }), encoding="utf-8")
        temporary = task_router.TaskCatalog.load(
            manifest_path=manifest, legacy_tasks_path=root / "unused.json"
        ).default_suite
        assert [task["task_id"] for task in temporary.tasks] == [
            "temporary-a", "temporary-b"
        ]
        assert temporary.resolve("2")[0]["task_id"] == "temporary-b"

        legacy_path = root / "legacy.json"
        legacy_path.write_text(json.dumps([a]), encoding="utf-8")
        legacy = task_router.TaskCatalog.load(
            manifest_path=root / "missing-manifest.json",
            legacy_tasks_path=legacy_path,
        )
        assert legacy.default_suite_id == "legacy"
        assert legacy.default_suite.tasks[0]["task_id"] == "temporary-a"

        ad_hoc_path = root / "draft.json"
        ad_hoc_path.write_text(json.dumps({
            "suite_id": "draft-suite",
            "title": "Draft",
            "version": "3",
            "default_personas": ["none"],
            "tasks": [a],
        }), encoding="utf-8")
        ad_hoc = task_router.suite_from_file(ad_hoc_path)
        assert ad_hoc.suite_id == "draft-suite" and ad_hoc.tasks[0] == a

        plain_a, plain_b = root / "one.json", root / "renamed.json"
        plain_a.write_text(json.dumps([a]), encoding="utf-8")
        plain_b.write_text(json.dumps([a]), encoding="utf-8")
        assert task_router.suite_from_file(plain_a).suite_id == (
            task_router.suite_from_file(plain_b).suite_id
        )

        collision = root / "collision.json"
        collision.write_text(json.dumps({
            "suite_id": "odysseys", "tasks": [a]
        }), encoding="utf-8")
        try:
            task_router.load_route(tasks_file=collision, catalog=catalog)
        except task_router.TaskRoutingError as exc:
            assert "conflicts with a registered suite" in str(exc)
        else:
            raise AssertionError("ad-hoc suite shadowed a registered suite")

        unsafe = root / "unsafe.json"
        unsafe.write_text(json.dumps({
            "schema_version": task_router.MANIFEST_SCHEMA,
            "default_suite": "bad",
            "suites": {"bad": {"task_files": ["../outside.json"]}},
        }), encoding="utf-8")
        try:
            task_router.TaskCatalog.load(
                manifest_path=unsafe, legacy_tasks_path=root / "unused.json"
            )
        except task_router.TaskRoutingError as exc:
            assert "stay under" in str(exc)
        else:
            raise AssertionError("manifest path escape was accepted")

        malformed = root / "malformed.json"
        bad_task = copy.deepcopy(a)
        del bad_task["rubrics"]
        malformed.write_text(json.dumps([bad_task]), encoding="utf-8")
        try:
            task_router.suite_from_file(malformed)
        except task_router.TaskRoutingError as exc:
            assert "rubric" in str(exc)
        else:
            raise AssertionError("malformed task was accepted")

        unsafe_task = copy.deepcopy(a)
        unsafe_task["task_id"] = "../escape"
        malformed.write_text(json.dumps([unsafe_task]), encoding="utf-8")
        try:
            task_router.suite_from_file(malformed)
        except task_router.TaskRoutingError as exc:
            assert "path-safe" in str(exc)
        else:
            raise AssertionError("path-unsafe task id was accepted")

        bad_persona = root / "bad-persona.json"
        bad_persona.write_text(json.dumps({
            "suite_id": "draft-bad-persona",
            "default_personas": ["../escape"],
            "tasks": [a],
        }), encoding="utf-8")
        try:
            task_router.suite_from_file(bad_persona)
        except task_router.TaskRoutingError as exc:
            assert "path-safe persona" in str(exc)
        else:
            raise AssertionError("path-unsafe persona id was accepted")


def test_report_task_routing():
    import report

    catalog = task_router.TaskCatalog.load()
    try:
        report._explicit_suite({"suite_id": "shopping", "task_suite": "other"})
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting result suite identities were accepted")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result_dir = root / "later" / "future-task" / "arm__model__20260101T000000Z"
        result_dir.mkdir(parents=True)
        future_task = copy.deepcopy(R.TASKS[0])
        future_task["task_id"] = "future-task"
        future_task["level"] = "hard"
        record = {
            "suite_id": "later",
            "task_id": "future-task",
            "task_snapshot": future_task,
            "persona": "none",
            "run": {"arm": {"model": "stub", "backend": "stub"}, "max_steps": 5},
            "judgement": {"score": 1.0, "score_communicated": 1.0},
        }
        (result_dir / "result.json").write_text(json.dumps(record), encoding="utf-8")
        best, order, levels = report.collect_results(
            root, catalog, list(catalog.suites.values()), all_suites=True
        )
        digest = task_router.canonical_sha256(future_task)
        task_key = ("later", "future-task", digest)
        result_key = (*task_key, "none/stub@stub#legacy")
        assert task_key in order
        assert levels[task_key] == "hard"
        assert result_key in best
        rendered = io.StringIO()
        with redirect_stdout(rendered):
            report.table(best, order, levels, "test scores", "score")
        assert "future-task" in rendered.getvalue()
        assert digest[:8] in rendered.getvalue()

        draft_file = root / "future-draft.json"
        draft_file.write_text(json.dumps([future_task]), encoding="utf-8")
        draft_route = task_router.suite_from_file(draft_file)
        custom_best, _, _ = report.collect_results(
            root, catalog, [draft_route], custom_selection=True
        )
        assert (draft_route.suite_id, "future-task", digest,
                "none/stub@stub#legacy") in custom_best

        # A newer judge failure must not replace the older valid score.
        unscored_dir = root / "later" / "future-task" / "arm__model__20270101T000000Z"
        unscored_dir.mkdir(parents=True)
        unscored = copy.deepcopy(record)
        unscored["judgement"] = {"score": None, "error": "judge failed"}
        (unscored_dir / "result.json").write_text(
            json.dumps(unscored), encoding="utf-8"
        )
        best, order, levels = report.collect_results(
            root, catalog, list(catalog.suites.values()), all_suites=True
        )
        assert best[result_key][1]["score"] == 1.0

        configured_dir = (
            root / "later" / "future-task" / "arm__model__20270102T000000Z"
        )
        configured_dir.mkdir(parents=True)
        configured = copy.deepcopy(record)
        configured["run_config"] = {"temperature": 1, "max_steps": 50}
        configured_hash = task_router.canonical_sha256(configured["run_config"])
        configured["run_config_sha256"] = configured_hash
        configured["judgement"] = {"score": 0.75, "score_communicated": 0.75}
        (configured_dir / "result.json").write_text(
            json.dumps(configured), encoding="utf-8"
        )
        best, order, levels = report.collect_results(
            root, catalog, list(catalog.suites.values()), all_suites=True
        )
        assert (*task_key, f"none/stub@stub#{configured_hash[:8]}") in best
        assert result_key in best

        # Task-bound opening/order fields do not fragment one arm across task
        # rows, but two browser profile identities for the same row are never
        # silently folded together.
        comparable_a = copy.deepcopy(configured)
        comparable_a["run_config"] = {
            **configured["run_config"],
            "persona_opening_cache_key": "a" * 64,
            "pair_order": "positive-negative",
            "pair_position": 1,
        }
        comparable_a["run_config_sha256"] = task_router.canonical_sha256(
            comparable_a["run_config"]
        )
        comparable_a["resume_config"] = {"profile_path_sha256": "1" * 64}
        comparable_a["resume_config_sha256"] = task_router.canonical_sha256(
            comparable_a["resume_config"]
        )
        profile_a_dir = root / "later" / "future-task" / "profile-a__20300101T000000Z"
        profile_a_dir.mkdir(parents=True)
        (profile_a_dir / "result.json").write_text(
            json.dumps(comparable_a), encoding="utf-8"
        )
        comparable_b = copy.deepcopy(comparable_a)
        comparable_b["resume_config"] = {"profile_path_sha256": "2" * 64}
        comparable_b["resume_config_sha256"] = task_router.canonical_sha256(
            comparable_b["resume_config"]
        )
        profile_b_dir = root / "later" / "future-task" / "profile-b__20300102T000000Z"
        profile_b_dir.mkdir(parents=True)
        (profile_b_dir / "result.json").write_text(
            json.dumps(comparable_b), encoding="utf-8"
        )
        best, _, _ = report.collect_results(
            root, catalog, list(catalog.suites.values()), all_suites=True
        )
        profile_keys = [
            key for key in best
            if key[:3] == task_key and "~profile-" in key[3]
        ]
        # The earlier fixture has the same comparison config but no recorded
        # browser resume identity ("legacy"), so all three identities must be
        # retained instead of selecting whichever result happened to be latest.
        assert len(profile_keys) == 3
        assert {
            key[3].rsplit("~profile-", 1)[-1] for key in profile_keys
        } == {
            "legacy",
            report.resume_config_version(comparable_a)[:8],
            report.resume_config_version(comparable_b)[:8],
        }

        # Reusing an ID after changing the task/rubric creates another version
        # row; it can never silently mix arms with the first version.
        changed_task = copy.deepcopy(future_task)
        changed_task["confirmed_task"] += " Changed."
        changed_digest = task_router.canonical_sha256(changed_task)
        changed_dir = root / "later" / "future-task" / "arm2__model__20280101T000000Z"
        changed_dir.mkdir(parents=True)
        changed = copy.deepcopy(record)
        changed["task_snapshot"] = changed_task
        changed["task_sha256"] = changed_digest
        changed["persona"] = "travel-senior"
        changed["judgement"] = {"score": 0.5, "score_communicated": None}
        (changed_dir / "result.json").write_text(json.dumps(changed), encoding="utf-8")
        best, order, levels = report.collect_results(
            root, catalog, list(catalog.suites.values()), all_suites=True
        )
        assert ("later", "future-task", digest) in order
        assert ("later", "future-task", changed_digest) in order
        assert ("later", "future-task", changed_digest,
                "travel-senior/stub@stub#legacy") in best
        assert report.mixed_revision_groups(best) == [("later", "future-task")]

        # Unknown pre-router records are kept under 'unrouted' for an all-suite
        # audit, never mislabeled as today's default Shopping suite.
        unknown_dir = root / "unknown" / "arm__model__20290101T000000Z"
        unknown_dir.mkdir(parents=True)
        unknown = copy.deepcopy(record)
        unknown.pop("suite_id")
        unknown["task_id"] = "unknown-task"
        unknown["task_snapshot"]["task_id"] = "unknown-task"
        unknown["judgement"] = {"score": 0.25, "score_communicated": 0.25}
        (unknown_dir / "result.json").write_text(json.dumps(unknown), encoding="utf-8")
        best, _, _ = report.collect_results(
            root, catalog, list(catalog.suites.values()), all_suites=True
        )
        assert any(key[:2] == ("unrouted", "unknown-task") for key in best)

        selected, _, _ = report.collect_results(
            root, catalog, [catalog.default_suite]
        )
        assert not selected


def test_grid_shell_contract():
    script = SRC / "run_grid.sh"
    syntax = subprocess.run(["/bin/bash", "-n", str(script)], capture_output=True)
    assert syntax.returncode == 0, syntax.stderr.decode()

    env = {**os.environ, "PYTHON_BIN": "/usr/bin/true",
           "PERSONAS": "none", "TASKS": "1,2"}
    default_route = subprocess.run(
        ["/bin/bash", str(script)],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    assert default_route.returncode == 0 and "GRID DONE" in default_route.stdout
    dry = subprocess.run(
        ["/bin/bash", str(script), "--suite", "odysseys"],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    assert dry.returncode == 0 and "GRID DONE" in dry.stdout, dry.stderr

    rejected = subprocess.run(
        ["/bin/bash", str(script), "--task", "1"],
        cwd=REPO, env=env, capture_output=True, text=True,
    )
    assert rejected.returncode == 2
    assert "use TASKS=" in rejected.stderr


def test_personas_differ():  # the profiles the persona LLM is given
    prompts = {name: R.persona_lib.persona_system_prompt(SRC / "personas" / f"{name}.yaml")
               for name in ("travel-expert", "travel-senior")}
    assert "75-84" in prompts["travel-senior"]
    assert "Frequent flyer" in prompts["travel-expert"]
    assert prompts["travel-expert"] != prompts["travel-senior"]
    # The profile carries no task: the need is added separately, per task.
    for p in prompts.values():
        assert "Aurora" not in p


def test_matched_persona_experiment():
    # Shopping is retired (v1 owns its task ids now) but its protocol, tasks and
    # generated personas are still on disk, so the matched-pair machinery stays
    # covered against real data rather than a fixture.
    suite = task_router.TaskCatalog.load_retired("shopping")
    assert suite.persona_experiment is not None
    catalog = persona_experiment.dimension_catalog()
    protocol = persona_experiment.validate_protocol(
        persona_experiment.load_json(suite.persona_experiment),
        catalog=catalog,
        task_ids=[task["task_id"] for task in suite.tasks],
        expected_suite_id=suite.suite_id,
    )
    profiles = persona_experiment.expected_profiles(
        protocol,
        catalog=catalog,
        suite_id=suite.suite_id,
        protocol_path=suite.persona_experiment,
    )
    assert len(protocol["axes"]) == 6
    assert len(profiles) == 12
    malformed = copy.deepcopy(protocol)
    del malformed["design"]["pairing_controls"]
    try:
        persona_experiment.validate_protocol(
            malformed,
            catalog=catalog,
            task_ids=[task["task_id"] for task in suite.tasks],
            expected_suite_id=suite.suite_id,
        )
    except persona_experiment.ExperimentDefinitionError as exc:
        assert "pairing_controls" in str(exc)
    else:
        raise AssertionError("protocol without pairing controls was accepted")
    persona_experiment.materialize_profiles(
        profiles,
        output_dir=SRC / "personas" / "shopping" / "matched_pairs",
        check=True,
    )

    cells = persona_experiment.build_cells(protocol, suite.tasks, replicate_id="r1")
    assert len(cells) == 36
    assert {cell["task_id"] for cell in cells} == {
        task["task_id"] for task in suite.tasks
    }
    for task in suite.tasks:
        assert sum(cell["task_id"] == task["task_id"] for cell in cells) == 6

    kobe_id = suite.tasks[0]["task_id"]
    kobe_cells = persona_experiment.build_cells(
        protocol, suite.tasks, selected_task_ids={kobe_id}
    )
    assert len(kobe_cells) == 6
    assert {cell["axis_id"] for cell in kobe_cells} == {
        "evidence_verification", "price_orientation", "purchase_risk"
    }
    r2_cells = persona_experiment.build_cells(
        protocol, suite.tasks, replicate_id="r2"
    )
    r1_order = {
        (cell["task_id"], cell["axis_id"]): cell["pair_order"] for cell in cells
    }
    r2_order = {
        (cell["task_id"], cell["axis_id"]): cell["pair_order"] for cell in r2_cells
    }
    assert all(
        r2_order[key] == "-".join(reversed(r1_order[key].split("-")))
        for key in r1_order
    )
    verifying = R.resolve_persona_path(
        "mp_evidence_verification_positive", suite.suite_id
    )
    rendered = R.persona_lib.persona_system_prompt(verifying)
    assert "Verifying" in rendered and "Trust level" in rendered


class _StubBrowser:
    """Records calls, returns canned page text; same surface run_agent uses."""

    def __init__(self, **_):
        self.calls = []

    def open_tab(self, url):
        self.calls.append(("open_tab", url))
        return f"tab 1 | Stub | {url}\n\nHigh 54F Low 39F"

    def open_tabs(self):
        return [{"tab_id": 1, "title": "Stub", "url": "https://example.com"}]

    def shot(self, label, tab_id=None):
        self.calls.append(("shot", label))
        return None                      # screenshots are off in offline tests

    def close(self):
        self.calls.append(("close", None))


def _tool_call(cid, name, args):
    return types.SimpleNamespace(
        id=cid, function=types.SimpleNamespace(name=name, arguments=json.dumps(args)))


class _StubUser:
    """Stands in for the persona LLM: a fixed opening, a canned reply."""

    def __init__(self, opening="I want to take the train to Aurora. Will it be cold?"):
        self.opening = opening
        self.transcript = [{"role": "user", "text": opening}]
        self.questions = []

    def reply(self, question):
        self.questions.append(question)
        answer = "The next three days, please."
        self.transcript += [{"role": "assistant", "text": question},
                            {"role": "user", "text": answer}]
        return answer

    def info(self):
        return {"model": "stub-user", "provider": "stub"}


class _StubClient:
    """Three turns: browse, ask the user, finish."""

    def __init__(self):
        self.turns = [
            _tool_call("c1", "open_tab", {"url": "https://www.google.com/search?q=x"}),
            _tool_call("c2", "ask_user", {"question": "How many days of forecast?"}),
            _tool_call("c3", "finish", {"summary": "High 54F, low 39F."}),
        ]
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))
        self.seen_system = None
        self.seen_first_user = None

    def _create(self, *, model, messages, tools, temperature):
        self.seen_system = messages[0]["content"]
        self.seen_first_user = messages[1]["content"]
        call = self.turns.pop(0)
        msg = types.SimpleNamespace(
            content=None, tool_calls=[call],
            model_dump=lambda exclude_none=True: {"role": "assistant", "tool_calls": []})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_agent_loop(monkeypatched):
    client, user = _StubClient(), _StubUser()
    R._client = lambda model, provider="": (client, "stub")
    R.Browser = _StubBrowser
    run = R.run_agent(R.TASKS[0], user, "stub-model",
                      max_steps=5, headless=True, temperature=0.0)
    assert run["stop_reason"] == "finish", run["stop_reason"]
    assert run["answer"] == "High 54F, low 39F."
    assert [t["tool"] for t in run["trajectory"]] == ["open_tab", "ask_user", "finish"]
    assert run["open_tabs"][0]["url"] == "https://example.com"
    # ask_user reached the persona and its reply went back to the agent
    assert user.questions == ["How many days of forecast?"]
    assert "three days" in run["trajectory"][1]["result_preview"]
    assert len(run["conversation"]) == 3
    # The CUA carries no persona and never sees the hidden Odysseys text --
    # only what the user said.
    assert "75-84" not in client.seen_system
    assert client.seen_first_user == user.opening
    assert R.TASKS[0]["confirmed_task"][:60] not in client.seen_system
    return run


class _TextClient:
    """Plain-text chat stub for the persona LLM; records what it was sent."""

    def __init__(self, reply="Hi, how do I get to Aurora by train?"):
        self.reply, self.sent = reply, []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, *, model, messages, temperature=None, **kwargs):
        self.sent.append([dict(m) for m in messages])
        self.kwargs = dict(kwargs, temperature=temperature)
        msg = types.SimpleNamespace(content=self.reply, tool_calls=None)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_persona_user():
    task = R.TASKS[0]
    client = _TextClient()
    R._client = lambda model, provider="": (client, "stub")

    user = R.PersonaUser(task, SRC / "personas" / "travel-senior.yaml", "stub")
    system = client.sent[0][0]["content"]
    assert "75-84" in system                      # persona profile
    assert task["confirmed_task"] in system       # hidden need
    assert user.opening == client.reply           # said in its own words
    snapshot = user.info()["persona_profile"]
    assert snapshot["persona_id"] == "odyssey-travel-senior"
    assert snapshot["evaluation_dimensions"]
    assert set(snapshot["evaluation_dimensions"]) == set(snapshot["evaluation_values"])
    assert len(snapshot["profile_sha256"]) == 64
    assert "75-84" in snapshot["profile_narrative"]
    assert user.reply("Which days?") == client.reply
    assert [t["role"] for t in user.transcript] == ["user", "assistant", "user"]

    cache_r1 = R.persona_opening_cache(
        task,
        suite_id="shopping",
        persona="travel-senior",
        replicate_id="r1",
        persona_path=SRC / "personas" / "travel-senior.yaml",
        model="stub",
        provider="stub",
        temperature=0.7,
    )
    cache_r2 = R.persona_opening_cache(
        task,
        suite_id="shopping",
        persona="travel-senior",
        replicate_id="r2",
        persona_path=SRC / "personas" / "travel-senior.yaml",
        model="stub",
        provider="stub",
        temperature=0.7,
    )
    assert cache_r1["cache_key"] != cache_r2["cache_key"]

    with tempfile.TemporaryDirectory() as directory:
        cache_path = Path(directory) / "opening.json"
        cache_spec = {
            "path": cache_path,
            "cache_key": "c" * 64,
            "identity": {"replicate_id": "r1", "task_id": task["task_id"]},
        }
        cache_client = _TextClient(reply="A frozen opening")
        R._client = lambda model, provider="": (cache_client, "stub")
        first = R.PersonaUser(
            task,
            SRC / "personas" / "travel-senior.yaml",
            "stub",
            opening_cache=cache_spec,
        )
        assert first.opening == "A frozen opening" and cache_path.is_file()
        assert first.info()["opening_cache"]["cache_hit"] is False

        cache_client_2 = _TextClient(reply="A different sampled opening")
        R._client = lambda model, provider="": (cache_client_2, "stub")
        second = R.PersonaUser(
            task,
            SRC / "personas" / "travel-senior.yaml",
            "stub",
            opening_cache={
                "path": cache_path,
                "cache_key": "c" * 64,
                "identity": {"replicate_id": "r1", "task_id": task["task_id"]},
            },
        )
        assert second.opening == first.opening
        assert not cache_client_2.sent
        assert second.info()["opening_cache"]["cache_hit"] is True

    matched_path = R.resolve_persona_path(
        "mp_evidence_verification_positive", "shopping"
    )
    # A matched-pair profile is only applicable to its own suite's tasks, so
    # this half of the test uses a task from the retired shopping suite.
    shopping_task = task_router.TaskCatalog.load_retired("shopping").tasks[0]
    matched_client = _TextClient(reply="Please distinguish confirmed dates from rumors.")
    R._client = lambda model, provider="": (matched_client, "stub")
    matched_user = R.PersonaUser(shopping_task, matched_path, "stub")
    matched_system = matched_client.sent[0][0]["content"]
    assert "In your INITIAL message" in matched_system
    assert "complete requirement set" in matched_system
    matched = matched_user.info()["persona_profile"]["matched_pair"]
    assert matched["axis_id"] == "evidence_verification"
    assert matched["arm"] == "positive"
    assert matched["protocol_sha256"]
    assert matched["adherence_rubric"]["task_observables"]
    assert matched["adherence_rubric"]["opposite_task_observables"]
    try:
        R.PersonaUser(R.TASKS[1], matched_path, "stub")
    except ValueError as exc:
        assert "not applicable" in str(exc)
    else:
        raise AssertionError("matched persona ran on an undeclared task")

    # Control arm: no profile, and the opening is the Odysseys text verbatim
    # without an LLM call.
    client2 = _TextClient()
    R._client = lambda model, provider="": (client2, "stub")
    control = R.PersonaUser(task, None, "stub")
    assert control.opening == task["confirmed_task"]
    assert client2.sent == []


class _NeverFinishesClient(_StubClient):
    """Always browses, never calls finish -- the out-of-budget case."""

    def _create(self, *, model, messages, tools=None, temperature):
        self.seen_system = messages[0]["content"]
        if tools is None:  # the forced final-summary call carries no tools
            msg = types.SimpleNamespace(
                content="Partial: I found the BNSF line.", tool_calls=[],
                model_dump=lambda exclude_none=True: {"role": "assistant"})
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
        call = _tool_call("c", "open_tab", {"url": "https://example.com"})
        msg = types.SimpleNamespace(
            content=None, tool_calls=[call],
            model_dump=lambda exclude_none=True: {"role": "assistant", "tool_calls": []})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_budget_exhausted_still_answers():
    R._client = lambda model, provider="": (_NeverFinishesClient(), "stub")
    R.Browser = _StubBrowser
    run = R.run_agent(R.TASKS[0], _StubUser(), "stub-model",
                      max_steps=3, headless=True, temperature=0.0)
    assert run["stop_reason"] == "max_steps_summarised", run["stop_reason"]
    assert run["answer"] == "Partial: I found the BNSF line."
    assert run["steps"] == 3


class _MuteClient(_StubClient):
    """Returns neither content nor tool calls -- the API-hiccup case."""

    def __init__(self):
        super().__init__()
        self.calls = 0

    def _create(self, *, model, messages, tools=None, temperature):
        self.calls += 1
        msg = types.SimpleNamespace(
            content=None, tool_calls=[],
            model_dump=lambda exclude_none=True: {"role": "assistant"})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_mute_model_is_not_scored_as_zero():
    client = _MuteClient()
    R._client = lambda model, provider="": (client, "stub")
    R.Browser = _StubBrowser
    real_sleep, R.time.sleep = R.time.sleep, lambda *_: None
    try:
        run = R.run_agent(R.TASKS[0], _StubUser(), "stub",
                          max_steps=10, headless=True, temperature=0.0)
    finally:
        R.time.sleep = real_sleep
    # Three retries, then give up -- and never a forced summary, which is what
    # used to turn a mute API into a confident 0.0.
    assert run["stop_reason"] == "no_model_output", run["stop_reason"]
    assert client.calls == 3, client.calls
    assert run["answer"] == "" and run["steps"] == 0


def test_judge_failure_keeps_the_run(run):
    """An unusable judge response must not throw away the browse it grades."""
    client = _TextClient(reply="")          # the judge answers with nothing
    R._client = lambda model, provider="": (client, "stub")
    # monotonic as well as sleep: every model call is timed for the cost report.
    R.time = types.SimpleNamespace(sleep=lambda *_: None, monotonic=time.monotonic)

    j = R.judge_run(R.TASKS[0], run, judge_model="stub", judge_provider="stub")
    assert j["score"] is None and j["met"] is None and j["error"]
    assert len(client.sent) == 3            # retried, then gave up
    R.time = __import__("time")


def test_extract_json():
    assert R.extract_json('{"R1": {"met": true}}') == {"R1": {"met": True}}
    assert R.extract_json('```json\n{"R1": {"met": false}}\n```') == {"R1": {"met": False}}
    assert R.extract_json("Here you go: {\"a\": 1} -- done") == {"a": 1}
    assert R.extract_json("") is None
    assert R.extract_json("no json here") is None
    assert R.extract_json("[1, 2]") is None


def test_azure_key_file_config():
    """Azure aliases may point at a file, so the key stays out of .env."""
    import os
    import tempfile

    names = (
        "OPENAI_API_KEY", "OPENAI_API_KEY_FILE", "OPENAI_BASE_URL",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_KEY_FILE",
        "AZURE_OPENAI_BASE_URL",
    )
    before = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ.pop(name, None)
        with tempfile.TemporaryDirectory() as d:
            key_file = Path(d) / "azure.key"
            key_file.write_text("test-secret\n", encoding="utf-8")
            # Stale direct OpenAI settings must not be mixed with Azure.
            os.environ["OPENAI_API_KEY"] = "wrong-secret"
            os.environ["OPENAI_BASE_URL"] = "https://wrong.example/v1"
            os.environ["AZURE_OPENAI_API_KEY_FILE"] = str(key_file)
            os.environ["AZURE_OPENAI_BASE_URL"] = "https://example.test/openai/v1"
            key, base_url = R._provider_config("openai")
            assert key == "test-secret"
            assert base_url == "https://example.test/openai/v1"
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_persona_fidelity_contract():
    import copy
    import persona_fidelity_judge as fidelity

    snapshot = {
        "persona_id": "odyssey-travel-young",
        "version": "2.0",
        "profile_sha256": "a" * 64,
        "evaluation_dimensions": ["tech_savviness", "economic_motivation"],
        "evaluation_values": {
            "tech_savviness": "Digital native",
            "economic_motivation": "Cost-sensitive",
        },
    }
    record = {
        "task_id": R.TASKS[0]["task_id"],
        "task_snapshot": {
            **R.TASKS[0],
            "confirmed_task": "FROZEN KOBE TASK",
        },
        "persona": "travel-young",
        "run": {
            "answer": "stub",
            "user": {"model": "stub", "provider": "stub", "persona_profile": snapshot},
            "conversation": [
                {"role": "user", "text": "Please keep it quick and show me cheaper Kobe shoes."},
                {"role": "assistant", "text": "Do you care about size?"},
                {"role": "user", "text": "Men's 10, and I want a page I can check myself."},
            ],
        },
    }
    rendered = fidelity.build_prompt(record)
    assert '"expected_value": "Cost-sensitive"' in rendered
    assert "PERSON TURN 1: Please keep it quick" in rendered
    assert "Do you care about size?" not in rendered
    assert "FROZEN KOBE TASK" in rendered
    task, integrity = R.task_for_record(record)
    assert task["confirmed_task"] == "FROZEN KOBE TASK"
    assert integrity == "frozen_snapshot"

    matched_snapshot = copy.deepcopy(snapshot)
    matched_snapshot["evaluation_dimensions"] = ["economic_motivation"]
    matched_snapshot["evaluation_values"] = {
        "economic_motivation": "Cost-sensitive"
    }
    matched_snapshot["matched_pair"] = {
        "axis_id": "price_orientation",
        "axis_label": "Price orientation",
        "arm": "positive",
        "opposite_value": "Premium-seeking",
        "adherence_rubric": {
            "behavioral_definition": "Prioritizes total cost.",
            "generic_observables": ["Asks to avoid a premium."],
            "task_observables": ["Asks for the cheapest qualifying option."],
            "inherited_task_signals": ["Reports a visible price."],
            "contradictions": ["Explicitly prefers a premium option."],
            "opposite_behavioral_definition": "Pays more for quality.",
            "opposite_generic_observables": ["Accepts a premium."],
            "opposite_task_observables": ["Chooses a higher-priced option for fit."],
        },
    }
    target = fidelity.requested_targets(matched_snapshot)[0]
    assert target["task_observables"] == [
        "Asks for the cheapest qualifying option."
    ]
    assert target["opposite_task_observables"] == [
        "Chooses a higher-priced option for fit."
    ]
    matched_record = copy.deepcopy(record)
    matched_record["run"]["user"]["persona_profile"] = matched_snapshot
    matched_record["judgement"] = {
        "communicated": len(R.TASKS[0]["rubrics"]) - 1,
        "total": len(R.TASKS[0]["rubrics"]),
        "verdicts": {
            rubric_id: {"communicated": index > 0}
            for index, rubric_id in enumerate(R.TASKS[0]["rubrics"])
        },
    }
    coverage = fidelity.communication_guardrail(matched_record)
    assert coverage["applicable"] and coverage["passed"] is False
    matched_prompt = fidelity.build_prompt(matched_record)
    assert "must receive score 0" in matched_prompt
    assert "cannot count as persona expression" in matched_prompt
    guarded = fidelity.apply_communication_guardrail(
        {
            "targets": [{"score": 2, "expressed": True, "note": "clear"}],
            "expressed_target_count": 1,
            "fidelity_issues": [],
        },
        coverage,
    )
    assert guarded["targets"][0]["score"] == 0
    assert guarded["targets"][0]["score_before_coverage_guardrail"] == 2
    assert guarded["expressed_target_count"] == 0

    parsed = {
        "targets": [
            {"attribute": "tech_savviness", "score": 1, "expressed": False,
             "contradicted": False, "confidence": 0.7,
             "evidence": "quick", "note": "weak"},
            {"attribute": "economic_motivation", "score": 2, "expressed": True,
             "contradicted": False, "confidence": 0.9,
             "evidence": "cheaper", "note": "clear"},
        ],
        "fidelity_issues": [],
        "judge_confidence": 0.8,
    }
    normalized = fidelity.normalize_verdict(
        parsed, model="stub-judge", provider="stub", snapshot=snapshot
    )
    assert normalized["expressed_target_count"] == 1
    assert normalized["total_target_count"] == 2
    assert normalized["contradicted_target_count"] == 0
    assert normalized["judge"] == {
        "model": "stub-judge", "provider": "stub", "backend": "stub"
    }
    assert normalized["profile_integrity"] == "frozen_snapshot"
    assert all(item["criterion_source"] == "declared_profile_dimension"
               for item in normalized["targets"])

    invalid_cases = []
    boolean_score = copy.deepcopy(parsed)
    boolean_score["targets"][0]["score"] = True
    invalid_cases.append(boolean_score)
    mismatch = copy.deepcopy(parsed)
    mismatch["targets"][0]["expressed"] = True
    invalid_cases.append(mismatch)
    bad_confidence = copy.deepcopy(parsed)
    bad_confidence["targets"][0]["confidence"] = 1.1
    invalid_cases.append(bad_confidence)
    boolean_confidence = copy.deepcopy(parsed)
    boolean_confidence["targets"][0]["confidence"] = True
    invalid_cases.append(boolean_confidence)
    no_evidence = copy.deepcopy(parsed)
    no_evidence["targets"][1]["evidence"] = ""
    invalid_cases.append(no_evidence)
    bad_issue = copy.deepcopy(parsed)
    bad_issue["fidelity_issues"] = [123]
    invalid_cases.append(bad_issue)
    duplicate = copy.deepcopy(parsed)
    duplicate["targets"].append(copy.deepcopy(duplicate["targets"][0]))
    invalid_cases.append(duplicate)
    missing = copy.deepcopy(parsed)
    missing["targets"].pop()
    invalid_cases.append(missing)
    for invalid in invalid_cases:
        try:
            fidelity.normalize_verdict(
                invalid, model="stub-judge", provider="stub", snapshot=snapshot
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid fidelity verdict must be rejected")


def test_experience_uses_frozen_profile():
    import experience_judge

    record = {
        "task_id": R.TASKS[0]["task_id"],
        "task_snapshot": {
            **R.TASKS[0],
            "confirmed_task": "FROZEN EXPERIENCE TASK",
        },
        "persona": "travel-young",
        "run": {
            "answer": "stub",
            "trajectory": [],
            "open_tabs": [],
            "conversation": [{"role": "user", "text": "A short request."}],
            "user": {"persona_profile": {"profile_narrative": "FROZEN PROFILE"}},
        },
    }
    rendered = experience_judge.build_prompt(record)
    assert "FROZEN PROFILE" in rendered
    assert "FROZEN EXPERIENCE TASK" in rendered
    complete = {
        "a": {dimension: {"score": 4} for dimension in experience_judge.DIMENSIONS},
        "b": {dimension: {"score": 4} for dimension in experience_judge.DIMENSIONS},
    }
    assert experience_judge.experience_complete(complete)
    complete["a"]["error"] = "transient"
    assert not experience_judge.experience_complete(complete)


def test_skip_existing_ignores_unscored(tmp: Path = Path("/tmp")):
    with tempfile.TemporaryDirectory() as d:
        scored, unscored = Path(d) / "a.json", Path(d) / "b.json"
        scored.write_text(json.dumps({"judgement": {"score": 0.5}}))
        unscored.write_text(json.dumps({"judgement": {"score": None, "error": "x"}}))
        assert R._is_scored(scored)
        assert not R._is_scored(unscored)
        assert not R._is_scored(Path(d) / "missing.json")

        snapshot = copy.deepcopy(R.TASKS[0])
        digest = task_router.canonical_sha256(snapshot)
        run_config = {"temperature": 1, "max_steps": 50}
        run_config_digest = task_router.canonical_sha256(run_config)
        resume_config = {"run_config_sha256": run_config_digest,
                         "profile_path_sha256": "p" * 64}
        resume_config_digest = task_router.canonical_sha256(resume_config)
        routed = Path(d) / "routed.json"
        routed.write_text(json.dumps({
            "suite_id": "shopping",
            "task_sha256": digest,
            "task_snapshot": snapshot,
            "run_config": run_config,
            "run_config_sha256": run_config_digest,
            "resume_config": resume_config,
            "resume_config_sha256": resume_config_digest,
            "judgement": {"score": 0.5},
        }), encoding="utf-8")
        assert R._is_scored(
            routed, suite_id="shopping", task_sha256=digest,
            run_config_sha256=run_config_digest,
            resume_config_sha256=resume_config_digest,
        )
        assert not R._is_scored(routed, suite_id="main-original", task_sha256=digest)
        assert not R._is_scored(routed, suite_id="shopping", task_sha256="0" * 64)
        assert not R._is_scored(
            routed, suite_id="shopping", task_sha256=digest,
            run_config_sha256="b" * 64,
        )
        assert not R._is_scored(
            routed, suite_id="shopping", task_sha256=digest,
            run_config_sha256=run_config_digest, resume_config_sha256="d" * 64,
        )

        tampered = json.loads(routed.read_text(encoding="utf-8"))
        tampered["run_config"]["temperature"] = 0
        routed.write_text(json.dumps(tampered), encoding="utf-8")
        assert not R._is_scored(
            routed, suite_id="shopping", task_sha256=digest,
            run_config_sha256=run_config_digest,
            resume_config_sha256=resume_config_digest,
        )

        tampered = json.loads(routed.read_text(encoding="utf-8"))
        tampered["run_config"] = run_config
        tampered["task_snapshot"]["confirmed_task"] += " tampered"
        routed.write_text(json.dumps(tampered), encoding="utf-8")
        assert not R._is_scored(
            routed, suite_id="shopping", task_sha256=digest,
            run_config_sha256=run_config_digest,
            resume_config_sha256=resume_config_digest,
        )


def test_grid_tasks_selector():
    """TASKS takes an index or an id, and an empty grid must not report DONE.

    The per-task persona assignment emits task_ids, so TASKS="1 2 3" -- the
    documented form -- silently matched nothing and run_grid printed GRID DONE
    and exited 0 without running a cell.
    """
    env = {**os.environ, "DRY_RUN": "1", "JOBS": "3", "TASK_SUITE": "odysseys",
           "PYTHON_BIN": sys.executable}
    first = R.TASKS[0]["task_id"]

    def cells(tasks):
        out = subprocess.run(
            ["bash", str(SRC / "run_grid.sh"), "--setting", "s1",
             "--model", "gpt-6-sol"],
            cwd=REPO, env={**env, "TASKS": tasks},
            capture_output=True, text=True, timeout=180)
        return out, sum(1 for l in out.stdout.splitlines() if l.startswith("DRY:"))

    # One task is one control plus its family's four personas.
    _, by_index = cells("1")
    assert by_index == 5, by_index
    _, by_id = cells(first)
    assert by_id == 5, by_id
    _, by_prefix = cells(first[:8])
    assert by_prefix == 5, by_prefix
    # A bare index must not also prefix-match every id starting with that digit.
    _, two = cells("1 2")
    assert two == 10, two

    # Matching nothing is an error, not a silent success.
    out, none = cells("no-such-task")
    assert none == 0, none
    assert out.returncode != 0, "an empty grid reported success"
    assert "matched nothing" in out.stderr, out.stderr[:200]


def test_embedded_python_runs_on_older_pythons():
    """run_grid.sh embeds Python; it must parse on the Pythons people have.

    A collaborator's server died on a double-quoted f-string whose replacement
    field also used double quotes around a dict key. PEP 701 allows that only
    from 3.12; it ran here because this machine is 3.12, and it broke the grid
    for everyone else before a single cell was enumerated. ast.parse cannot
    catch it, because it uses the grammar of whatever Python runs the test, so
    the shape is matched directly -- including in this file, which is why the
    offending form is described here rather than written out.
    """
    import re

    nested = re.compile(r'f"[^"\n]*\{[^}\n]*"[^"\n]*"[^}\n]*\}')
    offenders = []
    for path in list(SRC.rglob("*.py")) + list(SRC.rglob("*.sh")) \
            + list((REPO / "scripts").rglob("*.py")) \
            + list((REPO / "scripts").rglob("*.sh")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if nested.search(line):
                offenders.append(f"{path.name}:{i}")
    assert not offenders, (
        f"f-strings with nested same-type quotes need Python 3.12: {offenders}")

    # And the heredoc itself must be valid Python at all.
    script = (SRC / "run_grid.sh").read_text(encoding="utf-8")
    for body in re.findall(r"<<'PY[A-Z]*'\n(.*?)\nPY[A-Z]*\n", script, re.S):
        compile(body, "run_grid.sh:embedded", "exec")


def test_cli_defaults_do_not_override_routing():
    """--provider must default to empty, or the registry is overruled.

    It defaulted to "openai". resolve() treats a non-empty provider as an
    explicit override and honours it even when no such route exists, handing
    back the OpenRouter *id* aimed at the Azure endpoint. That mis-routed 11 of
    13 registry models; the two it spared, gpt-6-astra and terra, are the only
    two that had ever been run, so nothing caught it.
    """
    parser = R.build_parser() if hasattr(R, "build_parser") else None
    if parser is None:                      # parser is built inline in main()
        import re
        src = (SRC / "run.py").read_text(encoding="utf-8")
        for flag in ("--provider", "--persona-provider"):
            m = re.search(rf'add_argument\("{re.escape(flag)}",\s*default=("[^"]*")',
                          src)
            assert m, f"{flag} has no literal default any more; check by hand"
            assert m.group(1) == '""', f"{flag} defaults to {m.group(1)}, not empty"

    # An empty provider must behave exactly as passing none at all, whether or
    # not this machine has the credentials -- the gate runs without any.
    def outcome(key, provider):
        try:
            return R.model_registry.resolve(key, provider)
        except SystemExit as exc:
            return f"unrouted: {exc}"

    for key in R.model_registry.MODELS:
        assert outcome(key, "") == outcome(key, None or ""), key
        # "openai" as a default would have been an override: prove it differs,
        # so this test fails loudly if the default is ever put back.
        if key not in ("gpt-6-astra", "terra"):
            assert outcome(key, "openai") != outcome(key, ""), (
                f"{key}: forcing the openai provider must not look identical")


def test_typing_failure_says_why():
    """A failed type_text must tell the model what to do differently.

    It used to return Playwright's call log after waiting out the context's
    whole 40s timeout, so a wrong selector cost a minute and taught nothing;
    a read-only field (a date picker's input) looked the same as a missing one.
    """
    class Locator:
        def __init__(self, n, readonly=None, editable=True):
            self._n, self._ro, self._ed = n, readonly, editable

        def count(self):
            return self._n

        def nth(self, _index):
            return self

        @property
        def first(self):
            return self

        def get_attribute(self, name):
            return self._ro if name == "readonly" else None

        def is_editable(self):
            return self._ed

    class Page:
        def __init__(self, locator, fields=0):
            self._locator, self._fields = locator, fields

        def locator(self, selector):
            # The f<n> path counts the page's fields through this same call.
            return Locator(self._fields) if ">> visible=true" in selector \
                else self._locator

    why = REAL_BROWSER._why_typing_failed
    boom = RuntimeError("Timeout 8000ms exceeded.\nCall log:\n  - waiting for ...")

    absent = why(None, Page(Locator(0)), "input#nope", boom)
    assert "nothing on the page matches" in absent, absent
    assert "Call log" not in absent, "the call log is not something a model can act on"

    readonly = why(None, Page(Locator(1, readonly="")), "input[readonly]", boom)
    assert "read-only" in readonly and "Click it" in readonly, readonly

    # Editable but not typable (a React widget) reads the same way.
    guarded = why(None, Page(Locator(1, editable=False)), "#d", boom)
    assert "read-only" in guarded, guarded

    many = why(None, Page(Locator(3)), "input", boom)
    assert "matches 3 elements" in many and "nth=0" in many, many

    # Anything else: the exception's own first line, never the call log.
    other = why(None, Page(Locator(1)), "#x", boom)
    assert other == "Timeout 8000ms exceeded.", other
    assert REAL_BROWSER.TYPE_TIMEOUT_MS <= 10000, "a wrong selector must not cost 40s"

    # An f<n> handle out of range names the range it could have used, rather
    # than sending the model to look for another handle that is not there.
    gone = why(None, Page(Locator(0), fields=9), "f99", boom)
    assert "f1 to f9" in gone, gone
    # A handle is not a CSS selector: it must never fall through to the
    # "nothing on the page matches" branch, which would be a lie.
    assert "nothing on the page matches" not in gone, gone


def test_agent_sees_persona_prompt():
    """The persona-profile ablation adds the profile and nothing else.

    The main arm's prompt must be untouched by the feature existing, or every
    finished main-arm cell would stop matching its own identity.
    """
    task = {"real": {"site": "Zilloft", "url": "http://localhost/zilloft"}}
    plain = R.agent_system_prompt(task)
    profile = "### Identity\n- Age bracket: 75-84\n- Note: {not a placeholder}"
    seen = R.agent_system_prompt(task, persona_profile=profile)
    assert plain.startswith(R.AGENT_RULES) and "# The person you are working for" not in plain
    assert "# The person you are working for" in seen and profile in seen
    # The profile sits before "Where you are", and removing it gives back the
    # main arm's prompt exactly: the arm differs by the profile alone.
    assert seen.index(profile) < seen.index("# Where you are")
    section = "\n\n" + R.AGENT_PERSONA_PROFILE.replace("{profile}", profile)
    assert seen.replace(section, "", 1) == plain
    # Neutral on purpose: it says who the person is, not how to adapt.
    lowered = R.AGENT_PERSONA_PROFILE.lower()
    for steer in ("tailor", "adapt", "should ask", "ask the user"):
        assert steer not in lowered, f"profile prompt steers the agent: {steer!r}"


class _ScriptedClient(_StubClient):
    """Plays a given list of tool calls, one per turn."""

    def __init__(self, turns):
        super().__init__()
        self.turns = list(turns)


def test_force_clarify():
    """The forced-clarification arm: the prompt asks, the loop holds the floor."""
    plain = R.agent_system_prompt({})
    forced = R.agent_system_prompt({}, force_clarify=True)
    # A replacement, not an addition: the main arm's asking rule is not in it.
    assert plain == R.AGENT_RULES and forced == R.FORCE_CLARIFY
    assert "do\nnot ask about what you can reasonably decide yourself" in plain
    assert "reasonably decide yourself" not in forced
    assert "{" not in forced and f"at most {R.MAX_QUESTIONS}\nquestions" in forced
    assert "do your utmost to remove every ambiguity" in forced
    # Apart from the paragraph on asking, the two prompts are the same text, so
    # an edit to agent.md that is not carried over fails here.
    def paragraphs(text):
        return [p for p in text.split("\n\n") if not p.startswith("Users differ:")]
    assert paragraphs(plain) == paragraphs(forced)
    R.Browser = _StubBrowser

    def play(turns, **kw):
        R._client = lambda model, provider="": (_ScriptedClient(turns), "stub")
        return R.run_agent(R.TASKS[0], _StubUser(), "stub-model",
                           max_steps=8, headless=True, temperature=0.0, **kw)

    ask = _tool_call("q", "ask_user", {"question": "Which days?"})
    done = _tool_call("f", "finish", {"summary": "done"})
    # A finish before any question is sent back; after asking, it finishes.
    run = play([done, ask, done], force_clarify=True)
    assert [t["tool"] for t in run["trajectory"]] == ["finish", "ask_user", "finish"]
    assert run["trajectory"][0]["result_preview"] == R.CLARIFY_REFUSAL_MESSAGE
    assert run["stop_reason"] == "finish" and run["answer"] == "done"
    assert run["arm"]["force_clarify"] and run["arm"]["clarify_refusals"] == 1
    # A model that never asks is refused only CLARIFY_REFUSALS times, then ends.
    run = play([done] * (R.CLARIFY_REFUSALS + 1), force_clarify=True)
    assert run["stop_reason"] == "finish"
    assert run["arm"]["clarify_refusals"] == R.CLARIFY_REFUSALS
    # Off, a first-step finish is taken as before: the main arm is unchanged.
    run = play([done])
    assert run["steps"] == 1 and run["stop_reason"] == "finish"
    assert not run["arm"]["force_clarify"] and run["arm"]["clarify_refusals"] == 0


def test_judge(run):
    """Three fields from two judges, and the four outcomes they encode.

    met is objective and comes from the rubric judge. raised and engaged are
    subjective and come from the intent judge. One boolean could not hold both
    of the latter: "did it though nobody asked" and "was asked and never tried"
    both used to read as communicated=false.
    """
    task = R.TASKS[0]
    rids = list(task["rubrics"])
    assert len(rids) >= 4, "this test needs at least four rubric items"
    # One item per outcome, so every branch of INTENT_OUTCOMES is exercised:
    #   0 raised+engaged (met)   1 raised+engaged (not met)
    #   2 raised, not engaged    3 engaged, never raised
    plan = {rids[0]: (True, True, True), rids[1]: (True, True, False),
            rids[2]: (True, False, False), rids[3]: (False, True, True)}
    fake = {rid: {"met": plan.get(rid, (False, False, False))[2],
                  "raised": plan.get(rid, (False, False, False))[0],
                  "engaged": plan.get(rid, (False, False, False))[1],
                  "reason": "stub"}
            for rid in rids}
    client = _TextClient(reply=json.dumps(fake))
    R._client = lambda model, provider="": (client, "stub")

    j = R.judge_run(task, run, judge_model="stub-judge", judge_provider="stub")
    # reasoning-model call shape: no temperature, max_completion_tokens
    assert client.kwargs["temperature"] is None
    assert client.kwargs["max_completion_tokens"] == 8000
    # met counts items 0 and 3; total is every rubric item.
    assert j["met"] == 2 and j["total"] == len(rids)
    assert j["score"] == round(2 / len(rids), 3)
    assert j["trajectory_efficiency"] == round(2 / len(rids) / run["steps"], 4)
    # communicated still means "this person raised it": items 0, 1, 2. One of
    # those three was met, so the fair score is 1/3 -- item 3 was met but never
    # asked for, and must not inflate it.
    assert j["communicated"] == 3, j["communicated"]
    assert j["score_communicated"] == round(1 / 3, 3), j["score_communicated"]

    out = j["intent_outcomes"]
    assert out["understood"] == 2, out          # items 0 and 1
    assert out["not_understood"] == 1, out      # item 2: asked, never engaged
    assert out["exceeded"] == 1, out            # item 3: done, never asked
    assert out["out_of_scope"] == len(rids) - 4, out
    assert j["intent_graded"] == len(rids)
    # Of what this person asked for, the agent took up 2 of 3.
    assert j["engagement"] == round(2 / 3, 3), j["engagement"]

    # Each field keeps its own reason, so a disagreement stays readable.
    v = j["verdicts"][rids[0]]
    assert set(v) >= {"met", "met_reason", "raised", "raised_reason",
                      "engaged", "engaged_reason"}

    # raised is cached per conversation, so every model that saw the same words
    # is measured against the same line. Without this the answer moves: four
    # models on a byte-identical request gave raised counts of 0, 1, 4 and 0.
    import tempfile as _tf
    saved_cache = R.RAISED_CACHE
    with _tf.TemporaryDirectory() as tmp:
        R.RAISED_CACHE = Path(tmp) / "raised"
        try:
            calls = []
            saved_ask2 = R._ask_judge

            def counting(client, meter, role, **kw):
                calls.append(role)
                return json.loads(json.dumps(fake)), ""

            R._ask_judge = counting
            try:
                first = R.judge_run(task, run, judge_model="stub", judge_provider="stub")
                second = R.judge_run(task, run, judge_model="stub", judge_provider="stub")
            finally:
                R._ask_judge = saved_ask2
        finally:
            R.RAISED_CACHE = saved_cache
    assert first["raised_cache"]["hit"] is False, first["raised_cache"]
    assert second["raised_cache"]["hit"] is True, second["raised_cache"]
    # The second run must not have asked the raised judge again.
    assert calls.count("raised_judge") == 1, calls
    assert calls.count("rubric_judge") == 2 and calls.count("engagement_judge") == 2, calls
    # And the cached answer must be the same answer.
    assert ({r: v["raised"] for r, v in first["verdicts"].items()}
            == {r: v["raised"] for r, v in second["verdicts"].items()})

    # If the intent judge fails, the objective half must still stand.
    R._client = lambda model, provider="": (_TextClient(reply=json.dumps(fake)), "stub")
    saved_ask = R._ask_judge
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        return (json.loads(json.dumps(fake)), "") if calls["n"] == 1 else (None, "boom")

    R._ask_judge = flaky
    try:
        degraded = R.judge_run(task, run, judge_model="stub", judge_provider="stub")
    finally:
        R._ask_judge = saved_ask
    assert degraded["score"] == round(2 / len(rids), 3), degraded
    assert degraded["intent_outcomes"] is None
    assert degraded["score_communicated"] is None
    assert "boom" in degraded["intent_judge_error"]


if __name__ == "__main__":
    test_tasks()
    test_task_router()
    test_report_task_routing()
    test_grid_shell_contract()
    test_personas_differ()
    test_matched_persona_experiment()
    run = test_agent_loop(None)
    test_persona_user()
    test_budget_exhausted_still_answers()
    test_mute_model_is_not_scored_as_zero()
    test_judge_failure_keeps_the_run(run)
    test_extract_json()
    test_azure_key_file_config()
    test_persona_fidelity_contract()
    test_experience_uses_frozen_profile()
    test_skip_existing_ignores_unscored()
    test_grid_tasks_selector()
    test_embedded_python_runs_on_older_pythons()
    test_cli_defaults_do_not_override_routing()
    test_typing_failure_says_why()
    test_agent_sees_persona_prompt()
    test_force_clarify()
    test_judge(run)
    print("odyssey pipeline self-check OK")
