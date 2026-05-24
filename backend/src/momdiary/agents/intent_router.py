"""Pre-LLM intent router for `/v1/entries`.

Classifies each caregiver message into a `(resource, action)` pair so the
runner can scope the tool list (and prompt) the model sees. A narrower
tool surface dramatically improves tool-call accuracy and shrinks both
latency and cost.

Two routers are wired by default:

1. `HintIntentRouter` — if the request envelope already carries
   `entry_type`, treat that as authoritative (confidence 1.0). This is
   the typical "Edit this entry" path from the frontend.
2. `RegexIntentRouter` — keyword/regex match over the raw message. Cheap,
   deterministic, no LLM call. Returns low confidence when multiple
   resources match (multi-event messages) or none do.

The two are composed by `ChainedIntentRouter`; an LLM-backed fallback can
be added later as a third link without touching callers. Routing is
*advisory*: when confidence is below `SCOPE_THRESHOLD` the runner keeps
the full tool list and the prompt is untouched, so a misclassification
degrades to today's behavior, never below it.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Literal, Protocol

from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

Resource = Literal["feed", "sleep", "poop", "appointment", "unknown"]
Action = Literal["log", "update", "delete", "read", "note", "unknown"]

# Below this confidence the runner does NOT scope the tool list.
SCOPE_THRESHOLD = 0.75
# Below this confidence the runner does NOT scope by action (only by resource).
ACTION_SCOPE_THRESHOLD = 0.85


@dataclass(slots=True, frozen=True)
class RouterDecision:
    """A single classification result handed to the runner."""

    resource: Resource
    action: Action
    confidence: float  # 0.0 .. 1.0
    source: str  # "hint" | "regex" | "llm" | "default"
    reason: str = ""

    @property
    def should_scope_resource(self) -> bool:
        return self.confidence >= SCOPE_THRESHOLD and self.resource != "unknown"

    @property
    def should_scope_action(self) -> bool:
        return self.confidence >= ACTION_SCOPE_THRESHOLD and self.action != "unknown"


class IntentRouter(Protocol):
    """Minimal contract: classify a caregiver message."""

    async def classify(
        self,
        message: str,
        *,
        entry_type_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> RouterDecision: ...


# ---------------------------------------------------------------------------
# Keyword tables — tuned to maximise precision on real caregiver phrasings.
# Add words sparingly; every false positive narrows the tool list wrong.
# ---------------------------------------------------------------------------

_RESOURCE_PATTERNS: dict[Resource, re.Pattern[str]] = {
    "feed": re.compile(
        r"\b("
        r"feed|feeds|feeding|fed|"
        r"ate|eat|eating|"
        r"drink|drank|drunk|drinking|"
        r"breast|breastfed|breastfeeding|breastmilk|bm|"
        r"bottle|bottlefeed|bottlefed|"
        r"nurse|nursed|nursing|"
        r"formula|"
        r"milk|"
        r"solid|solids|puree|pur\u00e9e|food|"
        r"water|"
        r"oz|ounce|ounces|ml|millilit(?:re|er)s?|grams?"
        r")\b",
        re.IGNORECASE,
    ),
    "sleep": re.compile(
        r"\b("
        r"sleep|slept|sleeping|asleep|"
        r"nap|naps|napped|napping|"
        r"woke|wake|wakes|waking|woken|wakeup|"
        r"doze|dozed|dozing|"
        r"bedtime|"
        r"down\s+for"  # "put her down for a nap"
        r")\b",
        re.IGNORECASE,
    ),
    "poop": re.compile(
        r"\b("
        r"poops?|pooped|pooping|poo|"
        r"diapers?|nappy|nappies|"
        r"bm|bowel|"
        r"stools?|"
        r"soil|soiled|soiling|"
        r"dirty"
        r")\b",
        re.IGNORECASE,
    ),
    "appointment": re.compile(
        r"\b("
        r"appointment|appointments|appt|appts|"
        r"doctor|doc|ped|pediatrician|"
        r"vaccine|vaccin\w*|shot|shots|immunization|"
        r"checkup|check-?up|visit|clinic|"
        r"schedule|scheduled|scheduling|"
        r"follow-?up"
        r")\b",
        re.IGNORECASE,
    ),
}

_ACTION_PATTERNS: dict[Action, re.Pattern[str]] = {
    "delete": re.compile(
        r"\b("
        r"delete|deleted|"
        r"remove|removed|"
        r"cancel|cancelled|canceled|"
        r"undo|"
        r"scratch\s+that|never\s*mind|"
        r"by\s+mistake|wasn'?t|didn'?t\s+actually|"
        r"that\s+was\s+wrong"
        r")\b",
        re.IGNORECASE,
    ),
    "update": re.compile(
        r"\b("
        r"update|updated|updating|"
        r"change|changed|changing|"
        r"fix|fixed|"
        r"correct|corrected|correction|"
        r"edit|edited|"
        r"modify|modified|"
        r"actually\s+(was|it|she|he)|"
        r"should\s+be|"
        r"meant\s+(to|that)"
        r")\b",
        re.IGNORECASE,
    ),
    "read": re.compile(
        r"\b("
        r"what|when|how\s+(many|much|long)|"
        r"did\s+(she|he|they|baby)|"
        r"has\s+(she|he|they|baby)\s+(eaten|slept|pooped)|"
        r"list|show\s+me|tell\s+me|"
        r"total|sum|"
        r"last\s+(feed|sleep|nap|poop|appt|appointment)"
        r")\b",
        re.IGNORECASE,
    ),
    "note": re.compile(
        r"\b("
        r"note|notes|"
        r"comment|comments|"
        r"remark|"
        r"add\s+(a\s+)?(note|comment)"
        r")\b",
        re.IGNORECASE,
    ),
}


def _resource_hits(text: str) -> dict[Resource, int]:
    return {res: len(pat.findall(text)) for res, pat in _RESOURCE_PATTERNS.items()}


def _action_hits(text: str) -> dict[Action, int]:
    return {act: len(pat.findall(text)) for act, pat in _ACTION_PATTERNS.items()}


# ---------------------------------------------------------------------------
# Router implementations
# ---------------------------------------------------------------------------


class HintIntentRouter:
    """Use the request envelope's `entry_type` when supplied."""

    _VALID: frozenset[str] = frozenset({"feed", "sleep", "poop", "appointment"})

    async def classify(
        self,
        message: str,  # noqa: ARG002 - signature parity
        *,
        entry_type_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> RouterDecision:
        if entry_type_hint and entry_type_hint in self._VALID:
            decision = RouterDecision(
                resource=entry_type_hint,  # type: ignore[arg-type]
                action="unknown",  # caller already knows; don't constrain
                confidence=1.0,
                source="hint",
                reason=f"entry_type_hint={entry_type_hint}",
            )
            logger.info(
                "intent_router.hint.hit",
                correlation_id=correlation_id,
                resource=decision.resource,
                entry_type_hint=entry_type_hint,
            )
            return decision
        logger.debug(
            "intent_router.hint.miss",
            correlation_id=correlation_id,
            entry_type_hint=entry_type_hint,
            valid=entry_type_hint is None,
        )
        return RouterDecision(
            resource="unknown",
            action="unknown",
            confidence=0.0,
            source="hint",
            reason="no hint",
        )


class RegexIntentRouter:
    """Deterministic keyword router. No network, no model."""

    async def classify(
        self,
        message: str,
        *,
        entry_type_hint: str | None = None,  # noqa: ARG002
        correlation_id: str | None = None,
    ) -> RouterDecision:
        text = message or ""
        started = time.perf_counter()
        if not text.strip():
            logger.debug(
                "intent_router.regex.empty",
                correlation_id=correlation_id,
            )
            return RouterDecision(
                resource="unknown",
                action="unknown",
                confidence=0.0,
                source="regex",
                reason="empty message",
            )

        rhits = _resource_hits(text)
        ranked = sorted(rhits.items(), key=lambda kv: kv[1], reverse=True)
        top_res, top_n = ranked[0]
        _, second_n = ranked[1]
        logger.debug(
            "intent_router.regex.resource_hits",
            correlation_id=correlation_id,
            hits={k: v for k, v in rhits.items() if v > 0},
            top=top_res,
            top_n=top_n,
            second_n=second_n,
        )

        if top_n == 0:
            logger.info(
                "intent_router.regex.unknown",
                correlation_id=correlation_id,
                reason="no resource keywords",
            )
            return RouterDecision(
                resource="unknown",
                action="unknown",
                confidence=0.0,
                source="regex",
                reason="no resource keywords",
            )

        # Multi-resource messages ("ate and pooped") -> low confidence so the
        # runner keeps the full tool list and the model decides.
        if second_n > 0 and top_n - second_n <= 1:
            resource_conf = 0.4
            reason = f"ambiguous: {dict(ranked)}"
        else:
            # Single dominant resource. Confidence grows mildly with margin.
            resource_conf = min(0.95, 0.8 + 0.05 * (top_n - second_n))
            reason = f"matched {top_res}={top_n}"

        # Action detection.
        ahits = _action_hits(text)
        a_ranked = sorted(ahits.items(), key=lambda kv: kv[1], reverse=True)
        top_act, top_act_n = a_ranked[0]
        _, second_act_n = a_ranked[1]
        logger.debug(
            "intent_router.regex.action_hits",
            correlation_id=correlation_id,
            hits={k: v for k, v in ahits.items() if v > 0},
            top=top_act,
            top_n=top_act_n,
            second_n=second_act_n,
        )
        if top_act_n == 0:
            action: Action = "log"  # default for resource-only messages
            action_conf = 0.75
        elif second_act_n == 0:
            action = top_act
            action_conf = 0.9
        else:
            # Multiple action keywords (rare). Pick top but lower confidence.
            action = top_act
            action_conf = 0.65

        # Final confidence is the resource confidence; action confidence is
        # surfaced separately via `should_scope_action`.
        final_conf = (
            resource_conf if action_conf >= 0.65 else resource_conf * 0.9
        )
        decision = RouterDecision(
            resource=top_res,
            action=action,
            confidence=final_conf,
            source="regex",
            reason=reason,
        )
        elapsed_us = int((time.perf_counter() - started) * 1_000_000)
        logger.info(
            "intent_router.regex.decided",
            correlation_id=correlation_id,
            resource=decision.resource,
            action=decision.action,
            confidence=round(decision.confidence, 2),
            action_confidence=round(action_conf, 2),
            should_scope_resource=decision.should_scope_resource,
            should_scope_action=decision.should_scope_action,
            elapsed_us=elapsed_us,
            reason=reason,
        )
        return decision


class ChainedIntentRouter:
    """Try a list of routers in order, returning the first confident hit.

    "Confident" == `should_scope_resource`. If no router clears the bar,
    return the best-scoring decision so callers still get audit context.
    """

    def __init__(self, routers: list[IntentRouter]) -> None:
        if not routers:
            raise ValueError("ChainedIntentRouter requires at least one router")
        self._routers = routers

    async def classify(
        self,
        message: str,
        *,
        entry_type_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> RouterDecision:
        best: RouterDecision | None = None
        considered: list[str] = []
        for router in self._routers:
            router_name = type(router).__name__
            considered.append(router_name)
            decision = await router.classify(
                message,
                entry_type_hint=entry_type_hint,
                correlation_id=correlation_id,
            )
            if decision.should_scope_resource:
                logger.info(
                    "intent_router.chain.decided",
                    correlation_id=correlation_id,
                    winner=router_name,
                    considered=considered,
                    resource=decision.resource,
                    action=decision.action,
                    confidence=round(decision.confidence, 2),
                    source=decision.source,
                )
                return decision
            if best is None or decision.confidence > best.confidence:
                best = decision
        assert best is not None
        logger.info(
            "intent_router.chain.fallback",
            correlation_id=correlation_id,
            considered=considered,
            best_source=best.source,
            resource=best.resource,
            action=best.action,
            confidence=round(best.confidence, 2),
            reason=best.reason,
        )
        return best


def default_router() -> IntentRouter:
    """Production wiring: hint short-circuit, then regex."""
    return ChainedIntentRouter([HintIntentRouter(), RegexIntentRouter()])


class NullIntentRouter:
    """No-op router used when intent routing is disabled via config.

    Always returns a zero-confidence `unknown` decision, which causes
    `allowed_tools_for(...)` to return `None` and the runner to keep the
    full tool list (the same graceful-degradation path used when the
    regex+hint chain finds nothing).
    """

    async def classify(
        self,
        message: str,
        *,
        entry_type_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> RouterDecision:
        return RouterDecision(
            resource="unknown",
            action="unknown",
            confidence=0.0,
            source="disabled",
            reason="intent router disabled by config",
        )


# ---------------------------------------------------------------------------
# Tool-set scoping helpers — used by the runner.
# ---------------------------------------------------------------------------

# All write tools partitioned by resource (mirrors `tools/registry.py`).
RESOURCE_WRITE_TOOLS: dict[Resource, frozenset[str]] = {
    "feed": frozenset({"log_feed", "update_feed", "delete_feed"}),
    "sleep": frozenset({"log_sleep", "update_sleep", "delete_sleep"}),
    "poop": frozenset({"log_poop", "update_poop", "delete_poop"}),
    "appointment": frozenset(
        {
            "log_appointment",
            "update_appointment",
            "delete_appointment",
            "add_appointment_note",
        }
    ),
    "unknown": frozenset(),
}

RESOURCE_READ_TOOLS: dict[Resource, frozenset[str]] = {
    "feed": frozenset({"list_feeds"}),
    "sleep": frozenset({"list_sleeps"}),
    "poop": frozenset({"list_poops"}),
    "appointment": frozenset({"list_appointments"}),
    "unknown": frozenset(),
}


def allowed_tools_for(decision: RouterDecision) -> frozenset[str] | None:
    """Compute the allowed tool-name set for a routing decision.

    Returns `None` when no scoping should be applied (caller keeps the
    full tool list, today's behavior). Otherwise returns a closed set
    including the matching read tool and `ask_for_clarification` so the
    model can always bail out or look up context.
    """
    if not decision.should_scope_resource:
        logger.debug(
            "intent_router.scope.skipped",
            resource=decision.resource,
            confidence=round(decision.confidence, 2),
            reason="below_threshold_or_unknown",
        )
        return None

    writes = RESOURCE_WRITE_TOOLS[decision.resource]
    reads = RESOURCE_READ_TOOLS[decision.resource]
    narrowed_by_action = False

    if decision.should_scope_action:
        narrowed_by_action = True
        if decision.action == "log":
            writes = frozenset(t for t in writes if t.startswith("log_"))
        elif decision.action == "update":
            writes = frozenset(
                t
                for t in writes
                if t.startswith("update_") or t == "add_appointment_note"
            )
        elif decision.action == "delete":
            writes = frozenset(t for t in writes if t.startswith("delete_"))
        elif decision.action == "note":
            writes = frozenset(
                t for t in writes if t == "add_appointment_note"
            ) or writes  # fall back to full if message wasn't actually note-on-appt
        elif decision.action == "read":
            writes = frozenset()

    allowed = writes | reads
    logger.debug(
        "intent_router.scope.computed",
        resource=decision.resource,
        action=decision.action,
        narrowed_by_action=narrowed_by_action,
        allowed=sorted(allowed),
        allowed_count=len(allowed),
    )
    # `ask_for_clarification` is a pseudo-tool registered separately by the
    # runner; it is always available regardless of scoping.
    return allowed
