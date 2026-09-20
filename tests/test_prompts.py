from __future__ import annotations

import unittest

from personacuabench.core import ConfigurationError
from personacuabench.prompting import PROMPT_NAMES, load_prompt


class PromptAssetTests(unittest.TestCase):
    def test_every_registered_prompt_loads_without_metadata_comment(self) -> None:
        for name in PROMPT_NAMES:
            with self.subTest(name=name):
                prompt = load_prompt(name)
                self.assertTrue(prompt)
                self.assertFalse(prompt.startswith("<!--"))

    def test_prompt_placeholders_can_be_filled(self) -> None:
        values = {
            "max_questions": 2,
            "goal": "Find a product.",
            "persona": "A careful shopper.",
            "task": "Find a product.",
            "conversation": "PERSON: Please help.",
            "actions": "1. browse",
            "answer": "Done.",
            "tabs": "[]",
            "rubric": "R1: find it",
        }
        for name in PROMPT_NAMES:
            with self.subTest(name=name):
                rendered = load_prompt(name).format(**values)
                self.assertTrue(rendered.strip())

    def test_unknown_prompt_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_prompt("../tasks")


if __name__ == "__main__":
    unittest.main()
