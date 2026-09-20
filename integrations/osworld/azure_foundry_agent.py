"""Azure Foundry transport for OSWorld's screenshot-to-PyAutoGUI agent.

The inherited PromptAgent keeps OSWorld's prompts, trajectory handling, and
action parser. Only the model transport changes so GPT-5 reasoning deployments
receive the parameters supported by Azure Foundry's OpenAI v1 endpoint.
"""

from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from mm_agents.agent import PromptAgent


logger = logging.getLogger("desktopenv.agent")


_XY_FUNCTIONS = {
    "click",
    "doubleClick",
    "dragRel",
    "dragTo",
    "middleClick",
    "mouseDown",
    "mouseUp",
    "moveRel",
    "moveTo",
    "rightClick",
}

_FINAL_RESPONSE_PATTERN = re.compile(
    r"^\s*<FINAL_RESPONSE>\s*(.*?)\s*</FINAL_RESPONSE>\s*$",
    re.DOTALL,
)
_ASK_USER_PATTERN = re.compile(
    r"^\s*<ASK_USER>\s*(.*?)\s*</ASK_USER>\s*$",
    re.DOTALL,
)


def _extract_final_response(response: str) -> str | None:
    match = _FINAL_RESPONSE_PATTERN.fullmatch(response)
    return match.group(1).strip() if match else None


def _extract_ask_user(response: str) -> str | None:
    match = _ASK_USER_PATTERN.fullmatch(response)
    return match.group(1).strip() if match else None


def _scale_number(node: ast.expr, factor: float) -> ast.expr:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return ast.copy_location(ast.Constant(round(node.value * factor)), node)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
    ):
        value = -node.operand.value
        return ast.copy_location(ast.Constant(round(value * factor)), node)
    return node


class _CoordinateScaler(ast.NodeTransformer):
    def __init__(self, scale_x: float, scale_y: float) -> None:
        self.scale_x = scale_x
        self.scale_y = scale_y

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "pyautogui"
            and func.attr in _XY_FUNCTIONS
        ):
            return node

        if len(node.args) >= 2:
            node.args[0] = _scale_number(node.args[0], self.scale_x)
            node.args[1] = _scale_number(node.args[1], self.scale_y)
        for keyword in node.keywords:
            if keyword.arg == "x":
                keyword.value = _scale_number(keyword.value, self.scale_x)
            elif keyword.arg == "y":
                keyword.value = _scale_number(keyword.value, self.scale_y)
        return node


def _salvage_simple_action(code: str) -> str:
    """Drop accidental prose when the response otherwise contains simple actions."""
    kept = []
    for line in code.splitlines():
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("#")
            or stripped in {"import pyautogui", "import time"}
            or stripped.startswith("pyautogui.")
            or stripped.startswith("time.sleep(")
        ):
            kept.append(line)
    candidate = "\n".join(kept).strip()
    ast.parse(candidate)
    return candidate


def _scale_action(code: str, scale_x: float, scale_y: float) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        tree = ast.parse(_salvage_simple_action(code))
    tree = _CoordinateScaler(scale_x, scale_y).visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _load_api_key() -> str:
    direct = (
        os.environ.get("OSWORLD_OPENAI_API_KEY", "").strip()
        or os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    )
    if direct:
        return direct

    key_file = (
        os.environ.get("OSWORLD_OPENAI_API_KEY_FILE", "").strip()
        or os.environ.get("AZURE_OPENAI_API_KEY_FILE", "").strip()
    )
    if not key_file:
        raise RuntimeError(
            "Set OSWORLD_OPENAI_API_KEY[_FILE] or AZURE_OPENAI_API_KEY[_FILE]"
        )
    try:
        key = Path(key_file).expanduser().read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read AZURE_OPENAI_API_KEY_FILE: {exc}") from exc
    if not key:
        raise RuntimeError("AZURE_OPENAI_API_KEY_FILE is empty")
    return key


class AzureFoundryPromptAgent(PromptAgent):
    """PromptAgent with a GPT-5-compatible Azure Foundry transport."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        allow_ask_user = bool(kwargs.pop("allow_ask_user", False))
        super().__init__(*args, **kwargs)

        base_url = (
            os.environ.get("OSWORLD_OPENAI_BASE_URL", "").strip()
            or _required_env("AZURE_OPENAI_BASE_URL")
        ).rstrip("/") + "/"
        timeout = float(os.environ.get("AZURE_OPENAI_TIMEOUT_SECONDS", "180"))
        max_retries = int(os.environ.get("AZURE_OPENAI_MAX_RETRIES", "5"))
        self.reasoning_effort = os.environ.get(
            "AZURE_OPENAI_REASONING_EFFORT", "low"
        ).strip()
        self.screen_width = int(os.environ.get("OSWORLD_SCREEN_WIDTH", "1920"))
        self.screen_height = int(os.environ.get("OSWORLD_SCREEN_HEIGHT", "1080"))
        self.vision_width = int(os.environ.get("AZURE_VISION_COORD_WIDTH", "1365"))
        self.vision_height = int(os.environ.get("AZURE_VISION_COORD_HEIGHT", "768"))
        self.allow_ask_user = allow_ask_user
        self.system_message += (
            f"\nUse the image coordinate grid {self.vision_width}x"
            f"{self.vision_height} when choosing PyAutoGUI coordinates. During task "
            "execution, return only executable Python inside the code block: no "
            "reflection or prose. When every requested action is complete, return the "
            "user-facing answer inside exactly one <FINAL_RESPONSE>...</FINAL_RESPONSE> "
            "block instead of Python or DONE. Include all requested findings and summary "
            "there. The runner records that answer and treats it as DONE. The runner "
            "will map action coordinates to the desktop resolution. Because only recent "
            "turns are retained, begin every Python code block with concise # TASK_MEMORY: "
            "comments carrying forward all verified names, prices, dates, URLs, and "
            "remaining requirements needed for the final answer. Copy and update those "
            "comments on every turn and never invent a fact."
        )
        if self.allow_ask_user:
            self.system_message += (
                " If a missing user preference is genuinely necessary, you may return "
                "exactly one concise question inside "
                "<ASK_USER>...</ASK_USER> instead of Python. Do not combine that tag "
                "with code or any other text. The runner will obtain the user's answer "
                "and give you the updated conversation on the next turn. Ask only when "
                "the answer could materially change the work; otherwise proceed."
            )
        self._azure_client = OpenAI(
            base_url=base_url,
            api_key=_load_api_key(),
            timeout=timeout,
            max_retries=max_retries,
        )

    def call_llm(self, payload: dict[str, Any]) -> str:
        request: dict[str, Any] = {
            "model": payload["model"],
            "messages": payload["messages"],
        }
        is_gpt_reasoning = str(payload["model"]).lower().startswith(
            ("gpt-5", "o1", "o3", "o4")
        )
        if is_gpt_reasoning:
            request["max_completion_tokens"] = self.max_tokens
        else:
            request["max_tokens"] = self.max_tokens
            request["temperature"] = self.temperature
            request["top_p"] = self.top_p
        if self.reasoning_effort and is_gpt_reasoning:
            request["reasoning_effort"] = self.reasoning_effort

        # GPT-5 reasoning models reject max_tokens, temperature, and top_p.
        logger.info(
            "Generating content with Azure Foundry model %s (reasoning=%s)",
            self.model,
            self.reasoning_effort or "deployment default",
        )
        response = self._azure_client.chat.completions.create(**request)
        if not response.choices:
            raise RuntimeError("Azure Foundry returned no completion choices")
        content = response.choices[0].message.content
        if not content:
            finish_reason = response.choices[0].finish_reason
            raise RuntimeError(
                f"Azure Foundry returned empty content (finish_reason={finish_reason})"
            )

        usage = response.usage
        if usage is not None:
            logger.info(
                "Azure token usage: prompt=%s completion=%s total=%s",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )
        return content

    def parse_actions(self, response: str, masks: Any = None) -> list[str]:
        ask_user = _extract_ask_user(response)
        if ask_user is not None:
            if not self.allow_ask_user:
                raise ValueError("ASK_USER is disabled for this run")
            if not ask_user:
                raise ValueError("ASK_USER must not be empty")
            actions: list[str] = []
            self.actions.append(actions)
            return actions

        final_response = _extract_final_response(response)
        if final_response is not None:
            if not final_response:
                raise ValueError("FINAL_RESPONSE must not be empty")
            actions = ["DONE"]
            self.actions.append(actions)
            return actions

        actions = super().parse_actions(response, masks)
        if not actions:
            return actions
        scale_x = self.screen_width / self.vision_width
        scale_y = self.screen_height / self.vision_height
        return [_scale_action(action, scale_x, scale_y) for action in actions]
