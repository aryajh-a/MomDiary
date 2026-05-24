"""Unit tests for the pre-LLM intent router."""

from __future__ import annotations

import pytest

from momdiary.agents.intent_router import (
    ChainedIntentRouter,
    HintIntentRouter,
    NullIntentRouter,
    RegexIntentRouter,
    RouterDecision,
    SCOPE_THRESHOLD,
    allowed_tools_for,
    default_router,
)


# ---------------------------------------------------------------------------
# HintIntentRouter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hint_router_returns_resource_when_entry_type_supplied() -> None:
    r = HintIntentRouter()
    d = await r.classify("anything", entry_type_hint="feed")
    assert d.resource == "feed"
    assert d.confidence == 1.0
    assert d.source == "hint"
    assert d.should_scope_resource


@pytest.mark.asyncio
async def test_hint_router_ignores_unknown_entry_type() -> None:
    r = HintIntentRouter()
    d = await r.classify("anything", entry_type_hint="bogus")
    assert d.resource == "unknown"
    assert d.confidence == 0.0


@pytest.mark.asyncio
async def test_hint_router_returns_unknown_when_no_hint() -> None:
    r = HintIntentRouter()
    d = await r.classify("she ate 120 ml")
    assert d.resource == "unknown"
    assert not d.should_scope_resource


# ---------------------------------------------------------------------------
# RegexIntentRouter — single-resource phrasings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "msg,resource",
    [
        ("She had 120 ml of breast milk just now", "feed"),
        ("Bottle 4 oz formula at 2pm", "feed"),
        ("Nursing finished a few minutes ago", "feed"),
        ("She slept from 1 to 2:30", "sleep"),
        ("Just put her down for a nap", "sleep"),
        ("Diaper change, soft", "poop"),
        ("Pooped at 3pm", "poop"),
        ("Pediatrician appointment Tuesday at 9", "appointment"),
        ("Add appointment for vaccine next week", "appointment"),
    ],
)
@pytest.mark.asyncio
async def test_regex_router_classifies_clear_messages(msg: str, resource: str) -> None:
    r = RegexIntentRouter()
    d = await r.classify(msg)
    assert d.resource == resource, (msg, d)
    assert d.confidence >= SCOPE_THRESHOLD, (msg, d.confidence)
    assert d.should_scope_resource


@pytest.mark.asyncio
async def test_regex_router_defaults_to_log_action() -> None:
    r = RegexIntentRouter()
    d = await r.classify("she had 120 ml breast milk at 2pm")
    assert d.action == "log"


@pytest.mark.parametrize(
    "msg,action",
    [
        ("Delete the 2pm feed", "delete"),
        ("Remove that last poop entry", "delete"),
        ("Cancel her appointment tomorrow", "delete"),
        ("Update the feed to 150 ml", "update"),
        ("Actually it was 4 oz formula, change the feed", "update"),
        ("Fix the sleep end time to 3:15", "update"),
        ("What feeds did she have today?", "read"),
        ("How many naps so far?", "read"),
        ("Show me today's poops", "read"),
    ],
)
@pytest.mark.asyncio
async def test_regex_router_detects_action(msg: str, action: str) -> None:
    r = RegexIntentRouter()
    d = await r.classify(msg)
    assert d.action == action, (msg, d)


# ---------------------------------------------------------------------------
# RegexIntentRouter — ambiguous / empty messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regex_router_low_confidence_on_multi_resource() -> None:
    r = RegexIntentRouter()
    d = await r.classify("she ate 120 ml and pooped")
    # Both feed and poop hit once -> ambiguous -> below scope threshold.
    assert d.confidence < SCOPE_THRESHOLD
    assert not d.should_scope_resource


@pytest.mark.asyncio
async def test_regex_router_empty_message() -> None:
    r = RegexIntentRouter()
    d = await r.classify("")
    assert d.resource == "unknown"
    assert d.confidence == 0.0


@pytest.mark.asyncio
async def test_regex_router_unknown_message() -> None:
    r = RegexIntentRouter()
    d = await r.classify("hello there how are you")
    assert d.resource == "unknown"
    assert not d.should_scope_resource


# ---------------------------------------------------------------------------
# ChainedIntentRouter — hint short-circuits before regex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chained_router_prefers_hint_over_regex() -> None:
    chain = ChainedIntentRouter([HintIntentRouter(), RegexIntentRouter()])
    # Message screams "feed" but the hint says "sleep" -> hint wins.
    d = await chain.classify("she had 120 ml formula", entry_type_hint="sleep")
    assert d.resource == "sleep"
    assert d.source == "hint"


@pytest.mark.asyncio
async def test_chained_router_falls_back_to_regex_when_no_hint() -> None:
    chain = default_router()
    d = await chain.classify("she had 120 ml formula")
    assert d.resource == "feed"
    assert d.source == "regex"


@pytest.mark.asyncio
async def test_chained_router_returns_best_when_none_confident() -> None:
    chain = default_router()
    d = await chain.classify("hello there")
    # Both routers return unknown; best (highest-confidence) wins, which is
    # fine — caller checks `should_scope_resource` before scoping.
    assert d.resource == "unknown"
    assert not d.should_scope_resource


# ---------------------------------------------------------------------------
# allowed_tools_for — tool-set scoping
# ---------------------------------------------------------------------------


def _decision(resource: str, action: str, confidence: float) -> RouterDecision:
    return RouterDecision(
        resource=resource,  # type: ignore[arg-type]
        action=action,  # type: ignore[arg-type]
        confidence=confidence,
        source="test",
    )


def test_allowed_tools_none_when_below_threshold() -> None:
    assert allowed_tools_for(_decision("feed", "log", 0.5)) is None


def test_allowed_tools_unknown_resource_is_none() -> None:
    assert allowed_tools_for(_decision("unknown", "log", 0.99)) is None


def test_allowed_tools_resource_only_scoping() -> None:
    # High resource confidence, low action confidence -> all CRUD for feed,
    # plus list_feeds; no other resources.
    allowed = allowed_tools_for(_decision("feed", "unknown", 0.8))
    assert allowed is not None
    assert allowed == frozenset(
        {"log_feed", "update_feed", "delete_feed", "list_feeds"}
    )


def test_allowed_tools_log_action_drops_update_and_delete() -> None:
    allowed = allowed_tools_for(_decision("sleep", "log", 0.95))
    assert allowed == frozenset({"log_sleep", "list_sleeps"})


def test_allowed_tools_update_action_keeps_appointment_note() -> None:
    allowed = allowed_tools_for(_decision("appointment", "update", 0.95))
    assert allowed is not None
    assert "update_appointment" in allowed
    assert "add_appointment_note" in allowed
    assert "log_appointment" not in allowed
    assert "delete_appointment" not in allowed


def test_allowed_tools_delete_action_keeps_only_delete() -> None:
    allowed = allowed_tools_for(_decision("poop", "delete", 0.95))
    assert allowed == frozenset({"delete_poop", "list_poops"})


def test_allowed_tools_read_action_drops_all_writes() -> None:
    allowed = allowed_tools_for(_decision("feed", "read", 0.95))
    assert allowed == frozenset({"list_feeds"})


def test_allowed_tools_hint_resource_only_keeps_all_actions() -> None:
    # Hint router returns action="unknown" with confidence 1.0 -> we should
    # scope by resource but NOT by action.
    allowed = allowed_tools_for(
        RouterDecision(
            resource="feed",
            action="unknown",
            confidence=1.0,
            source="hint",
        )
    )
    assert allowed == frozenset(
        {"log_feed", "update_feed", "delete_feed", "list_feeds"}
    )


# ---------------------------------------------------------------------------
# NullIntentRouter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_router_returns_zero_confidence_unknown() -> None:
    r = NullIntentRouter()
    d = await r.classify(
        "Delete the 2pm feed", entry_type_hint="feed", correlation_id="cid-1"
    )
    assert d.resource == "unknown"
    assert d.action == "unknown"
    assert d.confidence == 0.0
    assert d.source == "disabled"
    # Critical contract: low-confidence => no tool scoping (full toolset).
    assert allowed_tools_for(d) is None
