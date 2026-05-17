"""Target resolver for ambiguous update/delete requests (T058, FR-017)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.db.repositories.appointments import AppointmentsRepository
from momdiary.db.repositories.feeds import FeedsRepository
from momdiary.db.repositories.poops import PoopsRepository
from momdiary.db.repositories.sleeps import SleepsRepository
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

EntryType = str


@dataclass(slots=True, frozen=True)
class TargetCandidate:
    entry_type: EntryType
    entry_id: int
    summary: str


@dataclass(slots=True, frozen=True)
class ResolutionResult:
    """Either a single resolved target, or a list of candidates needing clarification."""

    target: TargetCandidate | None
    candidates: list[TargetCandidate]

    @property
    def is_resolved(self) -> bool:
        return self.target is not None


async def resolve(
    session: AsyncSession,
    *,
    hinted_id: int | None,
    hinted_type: EntryType | None,
    candidates: list[TargetCandidate] | None = None,
) -> ResolutionResult:
    """Resolve an update/delete target.

    Precedence:
      1. Explicit `(hinted_type, hinted_id)` — must exist and not be deleted.
      2. Single-element `candidates` list from the agent.
      3. Multi-element candidates → caller must ask for clarification.
    """
    if hinted_id is not None and hinted_type is not None:
        if await _exists(session, hinted_type, hinted_id):
            logger.info(
                "resolver.explicit_hit",
                entry_type=hinted_type,
                entry_id=hinted_id,
            )
            return ResolutionResult(
                target=TargetCandidate(hinted_type, hinted_id, ""), candidates=[]
            )
        logger.info(
            "resolver.explicit_miss",
            entry_type=hinted_type,
            entry_id=hinted_id,
        )
        return ResolutionResult(target=None, candidates=[])

    cs = list(candidates or [])
    if len(cs) == 1:
        logger.info(
            "resolver.single_candidate",
            entry_type=cs[0].entry_type,
            entry_id=cs[0].entry_id,
        )
        return ResolutionResult(target=cs[0], candidates=[])
    logger.info("resolver.multi_candidate", count=len(cs))
    return ResolutionResult(target=None, candidates=cs)


async def _exists(session: AsyncSession, entry_type: str, entry_id: int) -> bool:
    if entry_type == "feed":
        return await FeedsRepository(session).get_by_id(entry_id) is not None
    if entry_type == "sleep":
        return await SleepsRepository(session).get_by_id(entry_id) is not None
    if entry_type == "poop":
        return await PoopsRepository(session).get_by_id(entry_id) is not None
    if entry_type == "appointment":
        return (
            await AppointmentsRepository(session).get_by_id_with_notes(entry_id)
            is not None
        )
    return False
