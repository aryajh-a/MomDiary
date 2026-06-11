"""Policy helpers for the research agent (feature 011).

Pure functions only — no I/O, no MAF, no DB. The runner depends on these
to (a) normalize and trim the source list before persisting and (b) emit
the canned refusal copy that the contract test pins to verbatim strings
(``contracts/research-api.md``).

Keeping these concerns in a separate module keeps the runner small and
the unit tests fast.
"""

from __future__ import annotations

from typing import Literal, Mapping
from urllib.parse import urlparse


ResearchOutcome = Literal[
    "research_answer",
    "research_unavailable",
    "scope_refused",
    "safety_refused",
    "no_sources_found",
]


# Verbatim copy — pinned by `tests/contract/test_research_api.py`.
CANNED_MESSAGES: Mapping[str, str] = {
    "research_unavailable": (
        "Research is temporarily unavailable. Please try again in a moment."
    ),
    "no_sources_found": (
        "I couldn't find a reliable source for this. Try rephrasing, or "
        "consult your pediatrician."
    ),
    "scope_refused": (
        "I can only help with baby-care research questions. Please rephrase "
        "as a question about your baby's care."
    ),
    "safety_refused": (
        "I can't help with that request. If you have concerns about your "
        "baby's safety, please contact your pediatrician or an emergency "
        "line."
    ),
}


# Disclaimer suffix the model is instructed to append (research agent
# instructions in `research_agent.py`). The runner also appends it
# defensively if the model omits it, to keep SC-008 deterministic.
DISCLAIMER_SUFFIX = (
    "This is general information, not medical advice. "
    "Always consult your pediatrician for medical decisions about your baby."
)


def clamp_sources(
    raw: list[dict[str, str]] | list[Mapping[str, str]],
    *,
    min_n: int,
    max_n: int,
) -> list[dict[str, str]]:
    """Deduplicate by (host, path) and clamp to ``max_n``.

    Preserves the model's original order — the model is expected to put
    the most-relevant citation first. ``min_n`` is intentionally not
    enforced here (the runner decides whether to fall back to
    ``no_sources_found`` based on the post-clamp count) so this helper
    stays a pure normalizer.

    Each returned dict has exactly two keys: ``title`` and ``url``.
    """
    if max_n <= 0:
        return []
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for src in raw:
        url = str(src.get("url") or "").strip()
        if not url:
            continue
        try:
            parsed = urlparse(url)
        except Exception:  # noqa: BLE001 — malformed url, skip
            continue
        host = (parsed.hostname or "").lower()
        path = parsed.path or "/"
        key = (host, path)
        if key in seen:
            continue
        seen.add(key)
        title = str(src.get("title") or "").strip() or url
        out.append({"title": title, "url": url})
        if len(out) >= max_n:
            break
    return out


def ensure_disclaimer(text: str) -> str:
    """Append the not-medical-advice disclaimer if the model omitted it."""
    if not text:
        return DISCLAIMER_SUFFIX
    if DISCLAIMER_SUFFIX in text:
        return text
    stripped = text.rstrip()
    return f"{stripped}\n\n{DISCLAIMER_SUFFIX}"


__all__ = [
    "CANNED_MESSAGES",
    "DISCLAIMER_SUFFIX",
    "ResearchOutcome",
    "clamp_sources",
    "ensure_disclaimer",
]
