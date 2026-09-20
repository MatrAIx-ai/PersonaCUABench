"""Offline unit tests for the Azure OSWorld adapter.

The adapter normally inherits OSWorld's ``PromptAgent``.  These tests load the
adapter from its source file with a minimal stand-in so unittest discovery does
not depend on an OSWorld checkout being importable.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = REPO_ROOT / "integrations" / "osworld" / "azure_foundry_agent.py"


class _StubPromptAgent:
    """Only the superclass behavior exercised by ``parse_actions`` is needed."""

    def parse_actions(self, response: str, masks: object = None) -> list[str]:
        del masks
        return [response]


def _load_adapter() -> types.ModuleType:
    mm_agents = types.ModuleType("mm_agents")
    mm_agents.__path__ = []
    agent_module = types.ModuleType("mm_agents.agent")
    agent_module.PromptAgent = _StubPromptAgent
    mm_agents.agent = agent_module

    module_name = "_personacuabench_azure_foundry_adapter_test"
    spec = importlib.util.spec_from_file_location(module_name, ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load adapter from {ADAPTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(
        sys.modules,
        {
            "mm_agents": mm_agents,
            "mm_agents.agent": agent_module,
            module_name: module,
        },
    ):
        spec.loader.exec_module(module)
    return module


adapter = _load_adapter()


def _bare_agent(*, allow_ask_user: bool = False):
    agent = object.__new__(adapter.AzureFoundryPromptAgent)
    agent.actions = []
    agent.screen_width = 1920
    agent.screen_height = 1080
    agent.vision_width = 1365
    agent.vision_height = 768
    agent.allow_ask_user = allow_ask_user
    return agent


class CoordinateScalingTests(unittest.TestCase):
    def test_scales_positional_and_keyword_coordinates(self) -> None:
        scale_x = 1920 / 1365
        scale_y = 1080 / 768

        positional = adapter._scale_action(
            "import pyautogui\npyautogui.click(1068, 590)", scale_x, scale_y
        )
        keyword = adapter._scale_action(
            "pyautogui.dragTo(x=683, y=384, duration=1)", scale_x, scale_y
        )

        self.assertIn("pyautogui.click(1502, 830)", positional)
        self.assertIn("x=961", keyword)
        self.assertIn("y=540", keyword)

    def test_parse_actions_scales_superclass_output(self) -> None:
        agent = _bare_agent()

        actions = agent.parse_actions("pyautogui.click(683, 384)")

        self.assertEqual(actions, ["pyautogui.click(961, 540)"])

    def test_salvages_simple_action_from_accidental_prose(self) -> None:
        agent = _bare_agent()

        actions = agent.parse_actions(
            "Click it once.\nimport pyautogui\npyautogui.click(683, 384)"
        )

        self.assertEqual(
            actions,
            ["import pyautogui\npyautogui.click(961, 540)"],
        )
        self.assertNotIn("Click it once", actions[0])


class TaggedResponseTests(unittest.TestCase):
    def test_final_response_becomes_done_and_is_recorded(self) -> None:
        agent = _bare_agent()
        response = (
            "<FINAL_RESPONSE>Found the requested products and left the tabs "
            "open.</FINAL_RESPONSE>"
        )

        self.assertEqual(
            adapter._extract_final_response(response),
            "Found the requested products and left the tabs open.",
        )
        self.assertEqual(agent.parse_actions(response), ["DONE"])
        self.assertEqual(agent.actions, [["DONE"]])

    def test_final_response_must_be_nonempty_and_standalone(self) -> None:
        agent = _bare_agent()

        with self.assertRaisesRegex(ValueError, "must not be empty"):
            agent.parse_actions("<FINAL_RESPONSE>   </FINAL_RESPONSE>")
        self.assertIsNone(
            adapter._extract_final_response(
                "prefix <FINAL_RESPONSE>done</FINAL_RESPONSE>"
            )
        )

    def test_ask_user_is_allowed_and_recorded(self) -> None:
        agent = _bare_agent(allow_ask_user=True)
        response = "<ASK_USER>Do you have a budget ceiling?</ASK_USER>"

        self.assertEqual(
            adapter._extract_ask_user(response),
            "Do you have a budget ceiling?",
        )
        self.assertEqual(agent.parse_actions(response), [])
        self.assertEqual(agent.actions, [[]])

    def test_ask_user_is_rejected_when_disabled_or_malformed(self) -> None:
        agent = _bare_agent(allow_ask_user=False)

        with self.assertRaisesRegex(ValueError, "ASK_USER is disabled"):
            agent.parse_actions("<ASK_USER>Which size?</ASK_USER>")
        self.assertIsNone(
            adapter._extract_ask_user(
                "please ask <ASK_USER>Which size?</ASK_USER>"
            )
        )


if __name__ == "__main__":
    unittest.main()
