"""Build/verify offline evidence analysis; no model or browser calls."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

import evidence

HERE = Path(__file__).resolve().parents[1]
REVIEWS = ("evidence/easy_pair_review.json", "evidence/medium_pair_review.json")
SLUGS = dict(zip(evidence.LABELS, ("fathers-day-gifts", "all-black-outfit", "mens-outfit",
                                "shared-journaling", "christmas-gifts", "budget-outfit")))


def pointer(value, path):
    for part in path.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def behavior_trace(record):
    """Descriptive action evidence, not an automatic personalization score."""
    events = record["run"].get("trajectory", [])
    signals = {"search_or_filter": r"search|sort|filter|query|[?&]q=",
               "price_or_quality": r"price|cost|cheap|premium|material|leather|silk",
               "risk_or_privacy": r"return|seller|shipping|delivery|privacy|encrypt|permission"}
    candidates = {name: [] for name in signals}
    for index, event in enumerate(events):
        # Only actions/arguments here: a page mentioning a policy does not mean
        # the agent deliberately inspected that policy.
        text = event.get("tool", "") + " " + json.dumps(event.get("args", {}), ensure_ascii=False)
        for name, pattern in signals.items():
            if re.search(pattern, text, re.I):
                candidates[name].append({"source_pointer": f"/run/trajectory/{index}",
                                         "tool": event.get("tool"), "args": event.get("args")})
    return {"action_counts": dict(Counter(e.get("tool") for e in events)),
            "ask_user_count": sum(e.get("tool") == "ask_user" for e in events),
            "candidate_actions": candidates,
            "final_tabs": record["run"].get("open_tabs", []),
            "original_communicated": record["judgement"].get("communicated"),
            "original_score_communicated": record["judgement"].get("score_communicated")}


def build():
    evidence.verify()
    manifest = evidence.load(HERE / "redaction-manifest.json")
    sources = {item["file"]: item["review_copy_sha256"] for item in manifest["files"]}
    protocol = evidence.load(evidence.SUITE / "personas/persona_experiment.json")
    tasks = evidence.load(evidence.SUITE / "000-core.json")
    labels = {task["task_id"]: label for task, label in zip(tasks, evidence.LABELS)}
    axes = {axis["axis_id"]: axis for axis in protocol["axes"]}
    expected = {(task, axis["axis_id"]) for axis in protocol["axes"] for task in axis["tasks"]}
    pairs, seen, counts = [], set(), Counter()
    for name in REVIEWS:
        doc = evidence.load(HERE / name)
        assert doc["replicate_id"] == "r1"
        for review in doc["pairs"].values():
            key = (review["task_id"], review["axis_id"])
            assert key not in seen and key in expected
            seen.add(key)
            pair = {"task": labels[key[0]], "review": review, "arms": {}}
            records = {}
            for arm, item in review["arms"].items():
                assert arm in ("positive", "negative")
                source = HERE / item["source_file"]
                assert sources[item["source_file"]] == item["source_sha256"] == evidence.sha(source.read_bytes())
                record = records[arm] = evidence.load(source)
                assert record["task_id"] == key[0]
                assert record["persona"] == f"mp_{key[1]}_{arm}"
                for field in ("opening", "answer"):
                    if item.get(field + "_quote"):
                        assert item[field + "_quote"] in pointer(record, item[field + "_evidence_ref"])
                rubrics = item["rubric_reviews"]
                assert len(rubrics) == len(record["task_snapshot"]["rubrics"])
                assert {r["rubric_id"] for r in rubrics} == set(record["task_snapshot"]["rubrics"])
                for rubric in rubrics:
                    assert rubric["original_raw_verdict"] == record["judgement"]["verdicts"].get(rubric["rubric_id"])
                    assert rubric["category"] in {"supported", "not_met", "insufficient_evidence"}
                    counts[rubric["category"] if rubric["original_raw_verdict"] is not None else "unscored"] += 1
                    for ref in rubric["evidence_refs"]:
                        pointer(record, ref)
                pair["arms"][arm] = {
                    "pole": axes[key[1]][arm]["value"],
                    "raw_task_score": record["judgement"].get("score"),
                    "answer_present": bool(record["run"].get("answer", "").strip()),
                    "environment": record["environment"]["status"],
                    "behavior_trace": behavior_trace(record),
                    "judge_format_anomaly": any("met" not in v for v in record["judgement"]["verdicts"].values())}
            assert set(records) == {"positive", "negative"}
            pair["configuration_mismatches"] = [field for field in
                ("agent", "persona_user", "judge", "browser", "prompt_sha256", "environment_gate")
                if records["positive"]["run_config"].get(field) != records["negative"]["run_config"].get(field)]
            pair["complete_response_pair"] = all(a["answer_present"] and a["environment"] == "valid" for a in pair["arms"].values())
            signatures = {}
            for arm, record in records.items():
                signatures[arm] = {json.dumps({"tool": event.get("tool"), "args": event.get("args")}, sort_keys=True)
                    for event in record["run"].get("trajectory", []) if event.get("tool") not in {"finish", "ask_user"}}
            pair["browser_action_comparison"] = {
                "unique_action_signatures_positive": len(signatures["positive"]),
                "unique_action_signatures_negative": len(signatures["negative"]),
                "shared_exact_action_signatures": len(signatures["positive"] & signatures["negative"]),
                "interpretation": "Descriptive only: tool/argument differences can reflect page state, tab IDs, locale or randomness, not necessarily persona. Check candidate events and observations before attributing any strategy difference."}
            scores = [pair["arms"][a]["raw_task_score"] for a in ("positive", "negative")]
            pair["raw_delta_positive_minus_negative"] = round(scores[0] - scores[1], 3) if all(type(s) in (int, float) for s in scores) else None
            pair["basic_comparison_checks_pass"] = (pair["complete_response_pair"] and not pair["configuration_mismatches"]
                and not any(a["judge_format_anomaly"] for a in pair["arms"].values()))
            pairs.append(pair)
    assert seen == expected and len(pairs) == 15
    historical = [evidence.load(HERE / item["file"]) for item in manifest["files"]]
    scored = [r for r in historical if r["judgement"].get("score") is not None]
    assert len(scored) == 26
    assert all(r["judgement"]["communicated"] == r["judgement"]["total"] and
               r["judgement"]["score_communicated"] == r["judgement"]["score"] for r in scored)
    assert not any(e.get("tool") == "ask_user" for r in historical for e in r["run"].get("trajectory", []))
    return {"method": "Offline evidence review, not independent model judging or a new experiment",
            "summary": {"replicate_id": "r1", "pairs": len(pairs),
                "scored_records_all_requirements_communicated": len(scored), "ask_user_calls": 0,
                "complete_response_pairs": sum(p["complete_response_pair"] for p in pairs),
                "adaptation_findings": dict(Counter(p["review"]["status"] for p in pairs)),
                "rubric_review": dict(counts)}, "pairs": pairs,
            "review_file_sha256": {name: evidence.sha((HERE / name).read_bytes()) for name in REVIEWS}}


def markdown(bundle):
    lines = ["# Lifestyle r1: paired evidence analysis", "",
        "This is an offline evidence analysis of the saved first replicate only. No browser tasks were rerun.",
        "It excludes the abandoned Vertex post-hoc evaluations. Original task scores are unchanged.", "",
        "## Main findings", "",
        "- 15 planned pairs / 30 cells: 11 pairs have final answers on both sides. All 11 show some answer-level preference responsiveness in this review.",
        "- Two pairs are inconclusive because one arm has an empty answer; two budget-outfit pairs were blocked by preflight HTTP 403.",
        "- Responsiveness is not task success: an answer can adapt its framing while omitting required products or making unverified claims.",
        "- Of 130 historically scored rubric items, this review labels 24 supported, 32 not met and 74 insufficient evidence. Another 32 items were unscored due to environment failure. These are qualitative evidence labels, not replacement scores.",
        "- Saved page previews are truncated. One replicate, no no-persona control and uncontrolled website variation prevent causal or statistical claims.",
        "- Persona openings and final-answer excerpts are shown below. Formal persona-expression and P1–P5 numerical scores were not recorded; this analysis does not invent them or claim equivalence to a two-judge protocol.", "",
        "Positive/negative name the two persona poles, not good/bad users. Deltas are positive minus negative and do not measure personalization benefit.", "",
        "| Task | Axis | Positive pole / raw score | Negative pole / raw score | Raw delta | Answer comparison |",
        "|---|---|---|---|---:|---|"]
    for pair in bundle["pairs"]:
        a, b = pair["arms"]["positive"], pair["arms"]["negative"]
        lines.append(f'| {pair["task"]} | {pair["review"]["axis_id"]} | {a["pole"]} / {a["raw_task_score"]} | {b["pole"]} / {b["raw_task_score"]} | {pair["raw_delta_positive_minus_negative"]} | {pair["review"]["status"]} |')
    lines += ["", "Raw deltas retain historical anomalies, including empty-answer scores and one malformed judge key. They are descriptive only.", ""]
    lines += ["## What this round cannot test", "",
              "The original judge marked all requirements communicated in all 26 scored runs; their score_communicated therefore equals the raw task score. No saved run called ask_user. This is consistent with a protocol that explicitly requests full requirement/preference disclosure in the opening, not proof that clarification is unnecessary in general.", "",
              "Task pages now separate preference quotations, candidate browser actions, and final decisions. Action candidates are keyword-indexed for inspection, not semantic verdicts. Different URLs, event counts or results alone cannot establish a persona effect; website locale, stock and model randomness also differ.", ""]
    lines += ["## Task evidence pages", "",
              "Each page contains all persona pairs for one task, original rubrics, review reasons, final answers, tabs and saved action previews.", ""]
    for label, slug in SLUGS.items():
        lines.append(f'- [{label}](lifestyle-audit-evidence/{slug}.md)')
    lines += ["", "## Reproducibility", "", "```bash", "python docs/reports/lifestyle-r1-2026-09-24/verify_audit.py", "```", "",
              "The verifier checks original evidence hashes, exact pair coverage, source identity, quote matches, rubric coverage and unchanged historical verdicts. It does not prove the qualitative interpretations.", "",
              "Structured audit: [all pairs and rubric reviews](lifestyle-evaluation-audit.json). Original scores: [score results](lifestyle-score-results.md).", "",
              "```json", json.dumps(bundle["summary"], indent=2), "```", ""]
    return "\n".join(lines)


def block(value):
    """Fence saved text so embedded Markdown cannot masquerade as report prose."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    fence = "`" * max(4, max((len(part) for part in re.findall(r'`+', text)), default=0) + 1)
    return [fence + "text", text.rstrip(), fence, ""]


def task_page(label, pairs):
    first = next(iter(pairs[0]["review"]["arms"].values()))
    task = evidence.load(HERE / first["source_file"])["task_snapshot"]
    lines = [f"# {label}: paired evidence and audit", "",
             "[Report index](../README.md) · [Scores](../lifestyle-score-results.md) · [Audit overview](../lifestyle-evaluation-audit.md)", "",
             "First replicate only. This is an offline evidence review, not a rerun or replacement score.",
             "Original answers below are audit subjects, not verified facts. Action previews are truncated saved observations, not full pages.", "",
             f'Task ID: `{pairs[0]["review"]["task_id"]}`', "", "## Original task", ""]
    lines += block(task["confirmed_task"])
    lines += ["## Original rubrics", ""] + block(task["rubrics"])
    for pair in pairs:
        review = pair["review"]
        lines += [f'## Pair: {review["axis_id"]}', "", review["adaptation_finding"], "",
                  f'Finding: `{review["status"]}`. Raw score delta (+ minus −): {pair["raw_delta_positive_minus_negative"]}.', "",
                  f'Basic response/configuration/judge-format checks pass: {pair["basic_comparison_checks_pass"]}. This is not factual verification.', ""]
        lines += ["Browser-action comparison (distinct tool + argument signatures, excluding finish/ask_user):", ""]
        lines += block(pair["browser_action_comparison"])
        for arm, item in review["arms"].items():
            record = evidence.load(HERE / item["source_file"])
            lines += [f'### {arm}: {pair["arms"][arm]["pole"]}', "",
                      f'[Source JSON](../{item["source_file"]}); SHA-256: `{item["source_sha256"]}`.', "",
                      f'Original score: {record["judgement"].get("score")}; environment: {record["environment"]["status"]}; final answer present: {pair["arms"][arm]["answer_present"]}.', "",
                      "Preference excerpt:", ""] + block(item.get("opening_quote") or "No saved opening.")
            for caveat in item.get("caveats", []):
                lines += ["Caveat: " + caveat, ""]
            lines += ["#### Browser behavior versus answer wording", "",
                      "The preference excerpt above documents user expression; the pair finding distinguishes reported selection or framing differences. The following action index supports checking browsing separately. Keyword matches are candidates, not proof of intent or success; inspect the referenced event and its observation below. Empty candidate lists do not prove absence of the behavior.", ""]
            lines += block(pair["arms"][arm]["behavior_trace"])
            lines += ["#### Rubric-by-rubric review", ""]
            for rubric in item["rubric_reviews"]:
                lines += [f'**{rubric["rubric_id"]}: {rubric["category"]}**', "", rubric["reason"], "",
                          "Source pointers: " + ", ".join(f'`{ref}`' for ref in rubric["evidence_refs"]) + ".", "",
                          "Original automatic verdict (unchanged):", ""] + block(rubric["original_raw_verdict"])
            lines += ["#### Original final answer", "", "Source: `/run/answer`.", ""]
            lines += block(record["run"].get("answer") or "No final answer.")
            lines += ["<details>", "<summary>Saved conversation, tabs, actions and environment checks</summary>", "",
                      "All saved events are included, indexed from zero. An action name alone does not establish success.", "",
                      "Conversation — `/run/conversation`:", ""] + block(record["run"].get("conversation", []))
            lines += ["Final tabs — `/run/open_tabs`:", ""] + block(record["run"].get("open_tabs", []))
            for index, event in enumerate(record["run"].get("trajectory", [])):
                lines += [f'Event {index} — `/run/trajectory/{index}`:', ""] + block(event)
            lines += ["Environment — `/environment`:", ""] + block(record["environment"])
            lines += ["</details>", ""]
    lines += ["## Missing measurements", "",
              "No original persona-expression or P1–P5 numerical evaluations were saved. Qualitative evidence review does not fill these numerical gaps.", ""]
    return "\n".join(lines)


def outputs(bundle):
    pages = {"lifestyle-evaluation-audit.md": markdown(bundle)}
    for label, slug in SLUGS.items():
        pages[f"lifestyle-audit-evidence/{slug}.md"] = task_page(label, [p for p in bundle["pairs"] if p["task"] == label])
    return pages


def verify():
    bundle = build()
    assert evidence.load(HERE / "lifestyle-evaluation-audit.json") == bundle
    pages = outputs(bundle)
    assert {p.name for p in (HERE / "lifestyle-audit-evidence").glob("*.md")} == {Path(p).name for p in pages if "/" in p}
    for name, text in pages.items():
        assert (HERE / name).read_text(encoding="utf-8") == text, name
    print("Verified 6 task pages, 15 pairs and 30 source records; no external calls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        bundle = build()
        evidence.write_json(HERE / "lifestyle-evaluation-audit.json", bundle)
        for name, text in outputs(bundle).items():
            path = HERE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        print(json.dumps(bundle["summary"], indent=2))
