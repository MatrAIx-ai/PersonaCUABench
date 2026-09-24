"""Fail-closed access checks for live-site benchmark runs.

A valid rubric score requires evidence that the task's required pages were
reachable in the same browser setup.  Missing checks are *unverified*, never
silently equivalent to a passing preflight.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse


HERE = Path(__file__).resolve().parent
CHECKS_FILE = HERE / "environment_checks.json"
BLOCK_SIGNAL = re.compile(
    r"Access Denied|HTTP (?:403|429)|GE401001|Oops!! Something went wrong|"
    r"captcha|verify you are human|chrome-error://chromewebdata/",
    re.IGNORECASE,
)


def plan_for_task(suite_id: str, task_id: str, path: Path = CHECKS_FILE) -> dict:
    """Load explicit, versioned canaries; absence prevents a scored run."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data["suites"][suite_id][task_id]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "unconfigured", "reason": f"no access checks: {exc}",
                "checks": [], "plan_sha256": None}
    if not isinstance(raw, list) or not raw:
        return {"status": "unconfigured", "reason": "access checks must be non-empty",
                "checks": [], "plan_sha256": None}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each access check must be an object")
        url = item.get("url")
        terms = item.get("must_contain")
        if (not isinstance(url, str) or urlparse(url).scheme != "https"
                or not urlparse(url).hostname or not isinstance(terms, list)
                or not terms or any(not isinstance(t, str) or not t.strip() for t in terms)):
            raise ValueError(f"invalid access check: {item!r}")
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"status": "configured", "reason": None,
            "checks": raw, "plan_sha256": digest}


def preflight(browser, plan: dict) -> dict:
    """Probe required page *content*, not merely HTTP 200 or a homepage."""
    if plan["status"] != "configured":
        return {"status": "unconfigured", "reason": plan["reason"],
                "plan_sha256": plan["plan_sha256"], "required_check_count": 0,
                "checks": []}
    checks = []
    for item in plan["checks"]:
        probe = browser.probe_url(item["url"])
        text = str(probe.get("text") or "")
        missing = [term for term in item["must_contain"]
                   if term.casefold() not in text.casefold()]
        status = probe.get("http_status")
        passed = (not probe.get("error") and isinstance(status, int)
                  and 200 <= status < 400 and not missing
                  and not BLOCK_SIGNAL.search(text[:2000]))
        checks.append({"url": item["url"], "actual_url": probe.get("url"),
                       "http_status": status, "title": probe.get("title"),
                       "http_errors": probe.get("http_errors") or [],
                       "passed": bool(passed), "missing": missing,
                       "error": probe.get("error"), "body_sample": text[:200]})
        if not passed:
            break
    return {"status": "valid" if len(checks) == len(plan["checks"])
            and all(check["passed"] for check in checks) else "blocked",
            "reason": None if all(check["passed"] for check in checks)
            and len(checks) == len(plan["checks"]) else "required page unavailable",
            "plan_sha256": plan["plan_sha256"],
            "required_check_count": len(plan["checks"]), "checks": checks}


def run_block_signals(run: dict) -> list[dict]:
    """Conservatively quarantine runs that hit an explicit site block."""
    signals = []
    for step in run.get("trajectory", []):
        preview = str(step.get("result_preview") or "")
        match = BLOCK_SIGNAL.search(preview)
        if match:
            signals.append({"step": step.get("step"), "tool": step.get("tool"),
                            "signal": match.group(0)})
    return signals


def score_is_valid(record: dict) -> bool:
    """Legacy scores without an access preflight are not comparable evidence."""
    environment = record.get("environment")
    if not isinstance(environment, dict):
        return False
    checks = environment.get("checks")
    return (environment.get("status") == "valid"
            and isinstance(environment.get("plan_sha256"), str)
            and bool(environment["plan_sha256"])
            and isinstance(checks, list) and bool(checks)
            and environment.get("required_check_count") == len(checks)
            and all(isinstance(check, dict) and check.get("passed") is True
                    for check in checks))
