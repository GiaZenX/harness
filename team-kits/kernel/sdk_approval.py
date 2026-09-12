"""Minting an approval from the Claude Agent SDK's `canUseTool` callback (FR-0083).

WHAT THIS IS FOR. `AskUserQuestion` does not exist in the CLI's headless mode -- measured, 30 tools
in the init line and none of them it, and `--tools "Read,AskUserQuestion"` yields `['Read']`. The
documented way to run the harness without a terminal is the Claude Agent SDK, where the same tool
raises the ordinary `canUseTool` permission callback and the embedding program answers with
`{behavior: "allow", updatedInput: {questions, answers}}`. This module is the one door from that
callback into the kernel's approval store.

WHAT IT DOES NOT DO, and the sentence belongs here rather than in a release note: it does not make
an unattended run trustworthy. Until it existed, "a token exists" meant "a human answered", because
`AskUserQuestion` can show a question to nobody but a human. Through this door it means "the
embedding PROGRAM decided". The SDK does not solve the trust question, it moves it -- out of the
provider and into whatever code calls this function -- so the record has to keep saying which of
the two happened. That is `approvals.MINTED_VIA_FIELD`, stamped by `approvals.mint` from the route
it recognises here, and it is what `approval_card` reads back out.

THE PREMISE THIS BUILDS ON IS THE CORRECTED ONE. `docs/POST_V2_WISHLIST.md` section 10 used to end
"da `gate_approval` nur aus einer echten Antwort auf eine echte `AskUserQuestion` prägt, ist die
Freigabekette headless unerreichbar". That premise was refuted on 2026-08-30 (chain and
counter-measurement at `H80`): the hook mints from any stdin payload shaped like an answer, and
what stops that inside a kit is `gate_write_scope`, not `gate_approval`. So headless is reachable,
and building a door with a NAMED provenance is better than leaving the reachable path unnamed.

WHAT A PROGRAM MAY NOT MINT HERE is decided by the kernel and not by this module:
`approvals._assert_the_route_may_decide_this` refuses every kind in `approvals.IRREVERSIBLE_KINDS`.
The remaining half of the same property -- merging or pushing work whose approval a program gave
itself -- is a gate question and `gate_git` asks it.
"""
from __future__ import annotations

from . import approvals
from .state import ProjectState


def answer_from_can_use_tool(tool_input: dict, question_text: str) -> str:
    """The answer string an SDK `updatedInput` carries for `question_text`, or "".

    The SDK hands back the tool's own input shape, so the answers live where the provider would
    have put them (`{"answers": {<question text>: <answer>}}`, spike S2b). Read here rather than by
    the caller, so an embedding program does not have to know the platform's blob layout to use
    this door -- and so there is one reader of it in the kernel.
    """
    answers = (tool_input or {}).get("answers")
    if not isinstance(answers, dict):
        return ""
    return str(answers.get(question_text) or "")


def mint_from_can_use_tool(state: ProjectState, request_id: str, answer: str) -> dict:
    """Mint the approval for `request_id` from a program's answer, and return the APR.

    A THIN DOOR ON PURPOSE. Every content check stays where it is -- `approvals.mint` still
    demands the verbatim approval label with this request's mint code, still refuses an expired
    request, an out-of-band edit of the item and a replay. What this function adds is exactly one
    thing: it is the file `approvals._assert_minting_caller` recognises as the programmatic route,
    so the resulting APR carries `PROGRAMMATIC_MINT` instead of `INTERACTIVE_MINT`. Nothing here
    passes a provenance; the kernel reads it off the running frame.

    THE CALLER'S HALF, which this module cannot check: the embedding program is the judge now, and
    whether the human it claims to represent ever saw the question is outside the kernel's reach --
    exactly as the hook route cannot prove a human read the question it relayed. What the record
    keeps is WHICH of the two answered, and that is what an auditor can still use afterwards.
    """
    return approvals.mint(state, request_id, answer)


def card(apr: dict, state=None) -> str:
    """The same card the approval hook prints, for a program that wants to log what it just did.

    Bound to `approvals.approval_card` rather than re-composed here, for the reason the composer
    exists: the difference between the two routes is precisely what the card has to make visible,
    so two spellings of it would be the one drift that matters.

    `state` is optional for the same reason it is there: a LIST-bound approval carries no `item`,
    and its list lives in the consumed request -- pass the state and the card counts the entries,
    leave it out and it says what it can.
    """
    return approvals.approval_card(apr, state)
