"""Deterministic preference-disclosure pilot; no model calls or opening cache.

Only Father's Day / price orientation is supported. Original hard requirements
remain public; the withheld variable is a soft price-vs-quality preference.
"""
import hashlib
import json
import re
from pathlib import Path

TASK_ID = "1211fbaa646424ab75869c0379431d5d049d2c9b"
VERSION = "price-disclosure.v1"
CUE = "For the final recommendation, I'm unsure how to weigh price against build quality."
PREFERENCES = {
    "positive": "When more than one option meets the original requirements, prioritize the lower-cost qualifying choice. Do not relax any original requirement.",
    "negative": "When more than one option meets the original requirements, I accept a higher price for evidenced better materials or durability. Do not relax any original requirement.",
}
QUESTION = re.compile(r"\b(budget|cost|price|spend|cheap|cheaper|afford\w*|premium|quality|durab\w*|material\w*|priorit\w*|prefer\w*|trade.?off\w*)\b", re.I)
FALLBACK = "I have no additional constraint on that; please follow my original request and state any necessary assumption."


def validate(task, persona, condition):
    if task["task_id"] != TASK_ID or condition not in {"full", "gap", "neutral"}:
        raise ValueError("disclosure pilot supports Father's Day only: full/gap/neutral")
    expected = {"none"} if condition == "neutral" else {f"mp_price_orientation_{arm}" for arm in PREFERENCES}
    if persona not in expected:
        raise ValueError("full/gap require a price-orientation persona; neutral requires none")


def identity(task, persona, condition):
    validate(task, persona, condition)
    spec = {"version": VERSION, "task_id": TASK_ID, "condition": condition,
            "persona": persona, "cue": CUE, "preferences": PREFERENCES,
            "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "question_pattern": QUESTION.pattern, "fallback": FALLBACK}
    spec["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    return spec


class ControlledUser:
    def __init__(self, task, persona, condition):
        self.spec = identity(task, persona, condition)
        self.condition = condition
        self.arm = persona.rsplit("_", 1)[-1] if persona != "none" else None
        self.preference = PREFERENCES.get(self.arm)
        self.opening = task["confirmed_task"] + "\n\n" + CUE
        if condition == "full":
            self.opening += "\n" + self.preference
        self.transcript = [{"role": "user", "text": self.opening}]
        self.disclosures = []

    def reply(self, question):
        matched = bool(QUESTION.search(question))
        answer = self.preference if matched and self.preference else FALLBACK
        self.disclosures.append({"question": question, "matched_trigger": matched,
                                 "preference_disclosed": bool(matched and self.preference),
                                 "user_turn_index": len(self.transcript) + 1})
        self.transcript.extend([{"role": "assistant", "text": question},
                                {"role": "user", "text": answer}])
        return answer

    def info(self):
        return {"model": None, "provider": "scripted", "interaction": self.spec,
                "disclosures": self.disclosures,
                "persona_profile": {"evaluation_dimensions": ["economic_motivation"] if self.arm else [],
                    "evaluation_values": {"economic_motivation": "Cost-sensitive" if self.arm == "positive" else "Premium-seeking"} if self.arm else {},
                    "profile_narrative": self.preference or "No additional price orientation."}}
