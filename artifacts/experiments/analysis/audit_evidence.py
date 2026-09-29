#!/usr/bin/env python3
"""Print the evidence behind each environment flag, for the manual KEEP/EXCLUDE audit.

For every cell with a block signal, shows the trajectory steps that carry it (tool, URL,
snippet) and every rubric verdict whose reason mentions a block, so the auditor can decide
whether the block stopped required or communicated evidence. It decides nothing itself.

    python3 work/audit_evidence.py BLOCK [BLOCK ...] [--model terra]
"""
import json, re, sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent / "repo"
SIG = re.compile(r"google\.[a-z.]+/sorry|\b403\b|(?i:access denied|captcha|cloudflare|verify you are human|are you a robot|just a moment|ERR_NAME_NOT_RESOLVED|ERR_CONNECTION|ERR_TIMED_OUT)")
REASON = re.compile(r"(?i)block|403|captcha|cloudflare|denied|unavailable|could not (?:load|access|open)|inaccessible|paywall|timed? ?out|robot|verification")
TASK_N = {t["task_id"][:12]: i for i, t in enumerate(json.loads((REPO / "odyssey/tasks.json").read_text()), 1)}
args = [a for a in sys.argv[1:] if not a.startswith("--")]
model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else ""
for b in args:
    b = REPO / b if not Path(b).is_absolute() else Path(b)
    for p in sorted((b / "results").glob("*/*/result.json")):
        if model and model not in p.parent.name:
            continue
        r = json.loads(p.read_text()); tr = r["run"]["trajectory"]
        hits = [t for t in tr if SIG.search(str(t.get("result_preview", "")) + json.dumps(t.get("args", {})))]
        vr = {k: v for k, v in r["judgement"]["verdicts"].items() if REASON.search(str(v.get("reason", "")))}
        if not hits and not vr:
            continue
        print(f"\n### {b.name.rsplit('-',1)[-1]} task {TASK_N[r['task_id'][:12]]} {r['persona']} "
              f"[{p.parent.name.split('__')[1]}] score={r['judgement']['score']}")
        for t in hits[:6]:
            m = SIG.search(str(t.get("result_preview", "")) + json.dumps(t.get("args", {})))
            url = re.search(r"https?://[^\s|\"']+", str(t.get("result_preview", "")) + json.dumps(t.get("args", {})))
            print(f"  step {t.get('step')} {t.get('tool')} [{m.group(0)}] {url.group(0)[:90] if url else ''}")
        for k, v in vr.items():
            print(f"  {k} met={v.get('met')} comm={v.get('communicated')}: {str(v.get('reason'))[:230]}")
