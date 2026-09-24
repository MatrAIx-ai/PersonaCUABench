"""Offline protocol and runner integration checks; never calls a provider."""
import json
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import controlled_disclosure as disclosure
import run

TASK = json.loads((Path(__file__).parent / "task_suites/lifestyle/000-core.json").read_text(encoding="utf-8"))[0]


class DisclosureTests(unittest.TestCase):
    def user(self, arm="positive", condition="gap"):
        return disclosure.ControlledUser(TASK, f"mp_price_orientation_{arm}", condition)

    def test_openings_and_fixed_replies(self):
        a, b = self.user(), self.user("negative")
        self.assertEqual(a.opening, b.opening)
        self.assertTrue(a.opening.startswith(TASK["confirmed_task"]))
        for pref in disclosure.PREFERENCES.values():
            self.assertNotIn(pref, a.opening)
        self.assertIn(a.preference, self.user(condition="full").opening)
        self.assertEqual(a.reply("What shoe size?"), disclosure.FALLBACK)
        self.assertEqual(a.reply("Do you prioritize price or quality?"), a.preference)
        self.assertEqual(a.reply("What is your budget?"), a.preference)
        self.assertNotEqual(a.preference, b.reply("Any preferences?"))
        neutral = disclosure.ControlledUser(TASK, "none", "neutral")
        self.assertEqual(neutral.opening, b.opening)
        self.assertEqual(neutral.reply("Budget?"), disclosure.FALLBACK)

    def test_identity_and_scope(self):
        identities = {self.user(arm, condition).spec["sha256"] for arm in ("positive", "negative") for condition in ("full", "gap")}
        self.assertEqual(len(identities), 4)
        self.assertEqual(self.user().spec, self.user().spec)
        with self.assertRaises(ValueError):
            disclosure.ControlledUser({**TASK, "task_id": "other"}, "mp_price_orientation_positive", "gap")
        with self.assertRaises(ValueError):
            disclosure.ControlledUser(TASK, "none", "gap")

    def test_cli_preview_all_conditions_without_clients(self):
        for condition, persona in [(c, f"mp_price_orientation_{a}") for c in ("full", "gap")
                                   for a in ("positive", "negative")] + [("neutral", "none")]:
            argv = ["run.py", "--suite", "lifestyle", "--task", TASK["task_id"],
                    "--persona", persona, "--interaction-condition", condition,
                    "--replicate-id", "disclosure-pilot-r1", "--preview"]
            with patch.object(sys, "argv", argv), patch("sys.stdout", new_callable=io.StringIO) as output, \
                 patch.object(run, "_client", side_effect=AssertionError("No provider allowed")), \
                 patch.object(run, "Browser", side_effect=AssertionError("No browser allowed")):
                run.main()
            self.assertIn(disclosure.CUE, output.getvalue())

    def test_agent_only_sees_public_conversation_and_records_observations(self):
        user = self.user()
        captured = []
        def response(**kwargs):
            captured.append(json.loads(json.dumps(kwargs["messages"])))
            index = len(captured)
            name, args = (("read_page", {"tab_id": 1}) if index == 1 else
                          ("ask_user", {"question": "Price or quality?"}) if index == 2 else
                          ("finish", {"summary": "Done"}))
            call = NS(id=str(index), function=NS(name=name, arguments=json.dumps(args)))
            msg = NS(content=None, tool_calls=[call], model_dump=lambda **_: {"role": "assistant", "tool_calls": []})
            return NS(choices=[NS(message=msg)])
        browser = NS(read_page=lambda **_: "x" * 20000, open_tabs=lambda: [], close=lambda: None)
        with patch.object(run, "_client", return_value=(object(), "stub")), \
             patch.object(run, "_create_with_retry", side_effect=lambda _client, **kw: response(**kw)), \
             patch.object(run, "Browser", return_value=browser):
            result = run.run_agent(TASK, user, "stub", max_steps=4, headless=True, temperature=0)
        self.assertNotIn(user.preference, json.dumps(captured[0]))
        self.assertIn(user.preference, json.dumps(captured[2]))
        self.assertEqual(len(result["trajectory"][0]["result"]), 20000)
        self.assertEqual(len(result["trajectory"][0]["result_preview"]), 400)
        self.assertEqual(result["trajectory"][0]["agent_observation"], captured[1][-1]["content"])
        self.assertEqual(result["user"]["disclosures"][0]["user_turn_index"], 2)


if __name__ == "__main__":
    unittest.main()
