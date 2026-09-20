"""Wire protocol shared by the Persona user simulator and the CUA runner.

The computer-use model has three legal response shapes:

* ordinary action output (parsed by the underlying OSWorld agent),
* ``<ASK_USER>...</ASK_USER>``, or
* ``<FINAL_RESPONSE>...</FINAL_RESPONSE>``.

Control tags are deliberately parsed with a full match.  A response that mixes a
control tag with code/prose is an error rather than something from which the
runner tries to salvage an action.  That property is important: malformed
``ASK_USER`` output must never reach ``DesktopEnv.step`` as Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class ResponseProtocolError(ValueError):
    """Raised when a CUA response violates the control-tag protocol."""


class ResponseKind(str, Enum):
    ACTION = "action"
    ASK_USER = "ask_user"
    FINAL_RESPONSE = "final_response"


@dataclass(frozen=True)
class ParsedResponse:
    """A classified CUA response.

    ``text`` is the question/final answer for control responses and the original,
    byte-for-byte response for ordinary action output.
    """

    kind: ResponseKind
    text: str


@dataclass(frozen=True)
class Clarification:
    """One user-visible clarification exchange."""

    question: str
    answer: str


_ASK_USER_PATTERN = re.compile(
    r"\A\s*<ASK_USER>(?P<text>.*?)</ASK_USER>\s*\Z",
    re.DOTALL,
)
_FINAL_RESPONSE_PATTERN = re.compile(
    r"\A\s*<FINAL_RESPONSE>(?P<text>.*?)</FINAL_RESPONSE>\s*\Z",
    re.DOTALL,
)

# This intentionally also catches malformed variants such as ``<ASK_USER >``
# or a lone closing tag.  Exact, well-formed tags are accepted only by the two
# full-match expressions above.
_CONTROL_TAG_LIKE = re.compile(
    r"(?:<\s*/?\s*(?:ASK_USER|FINAL_RESPONSE)\b|"
    r"(?:ASK_USER|FINAL_RESPONSE)\s*>)",
    re.DOTALL | re.IGNORECASE,
)


def classify_response(response: str) -> ParsedResponse:
    """Classify one raw CUA response without executing or repairing it.

    Outer whitespace around a control block is allowed.  Its body must be
    non-empty and may not contain another control tag.  Any occurrence of a
    control-tag-like token that is not one complete block raises
    :class:`ResponseProtocolError`.
    """

    if not isinstance(response, str):
        raise ResponseProtocolError("CUA response must be a string")
    if not response.strip():
        raise ResponseProtocolError("CUA response must not be empty")

    ask_match = _ASK_USER_PATTERN.fullmatch(response)
    final_match = _FINAL_RESPONSE_PATTERN.fullmatch(response)

    if ask_match is not None:
        text = ask_match.group("text").strip()
        if not text:
            raise ResponseProtocolError("ASK_USER must not be empty")
        if _CONTROL_TAG_LIKE.search(text):
            raise ResponseProtocolError(
                "ASK_USER must contain exactly one control block"
            )
        return ParsedResponse(ResponseKind.ASK_USER, text)

    if final_match is not None:
        text = final_match.group("text").strip()
        if not text:
            raise ResponseProtocolError("FINAL_RESPONSE must not be empty")
        if _CONTROL_TAG_LIKE.search(text):
            raise ResponseProtocolError(
                "FINAL_RESPONSE must contain exactly one control block"
            )
        return ParsedResponse(ResponseKind.FINAL_RESPONSE, text)

    if _CONTROL_TAG_LIKE.search(response):
        raise ResponseProtocolError(
            "control tags must be the entire response and cannot be mixed with code or prose"
        )

    return ParsedResponse(ResponseKind.ACTION, response)


# A short alias is convenient for callers and keeps the protocol API obvious.
parse_response = classify_response


def extract_ask_user(response: str) -> str | None:
    """Return a valid ASK_USER question, or ``None`` for ordinary/final output.

    Malformed control output still raises instead of being silently ignored.
    """

    parsed = classify_response(response)
    return parsed.text if parsed.kind is ResponseKind.ASK_USER else None


def extract_final_response(response: str) -> str | None:
    """Return a valid final answer, or ``None`` for ordinary/ASK_USER output."""

    parsed = classify_response(response)
    return parsed.text if parsed.kind is ResponseKind.FINAL_RESPONSE else None


def _as_clarification(value: Any, index: int) -> Clarification:
    if isinstance(value, Clarification):
        clarification = value
    elif isinstance(value, Mapping):
        clarification = Clarification(
            question=str(value.get("question", "")),
            answer=str(value.get("answer", "")),
        )
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        clarification = Clarification(question=str(value[0]), answer=str(value[1]))
    else:
        raise TypeError(
            "clarification {} must be Clarification, a question/answer mapping, "
            "or a two-item sequence".format(index)
        )

    question = clarification.question.strip()
    answer = clarification.answer.strip()
    if not question:
        raise ValueError(f"clarification {index} has an empty question")
    if not answer:
        raise ValueError(f"clarification {index} has an empty answer")
    return Clarification(question=question, answer=answer)


def compose_cua_instruction(
    opening_request: str,
    clarifications: Sequence[
        Clarification | Mapping[str, Any] | tuple[str, str] | list[str]
    ] = (),
) -> str:
    """Build exactly what the CUA is allowed to know about the user's request.

    Only the opening request and completed question/answer exchanges are
    included.  In particular, this function has no parameter for the hidden
    Odysseys task, rubric, persona profile, or persona identifier.

    With no clarifications, the return value is the *same string object content*
    as ``opening_request``: it is not stripped, normalized, prefixed, or suffixed.
    This byte-for-byte property makes leakage tests straightforward.
    """

    if not isinstance(opening_request, str):
        raise TypeError("opening_request must be a string")
    if not opening_request.strip():
        raise ValueError("opening_request must not be empty")
    if not clarifications:
        return opening_request

    normalized = [
        _as_clarification(value, index)
        for index, value in enumerate(clarifications, start=1)
    ]
    lines = [opening_request, "", "Clarifications:"]
    for index, clarification in enumerate(normalized, start=1):
        lines.append(f"Q{index}: {clarification.question}")
        lines.append(f"A{index}: {clarification.answer}")
    return "\n".join(lines)


__all__ = [
    "Clarification",
    "ParsedResponse",
    "ResponseKind",
    "ResponseProtocolError",
    "classify_response",
    "compose_cua_instruction",
    "extract_ask_user",
    "extract_final_response",
    "parse_response",
]
