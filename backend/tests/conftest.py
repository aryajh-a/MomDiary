"""Shared pytest fixtures: ephemeral SQLite + MAF stub agent."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from momdiary.agents.dispatcher import AgentRunResult
from momdiary.agents.tools.registry import invoke_tool
from momdiary.api.dependencies import get_agent_runner
from momdiary.db.engine import (
    dispose_engine,
    get_session_factory,
    reset_engine_for_tests,
)
from momdiary.services.time_service import reset_timezone_cache


# ---------------------------------------------------------------------------
# Ephemeral Postgres schema + migrations (feature 009)
# ---------------------------------------------------------------------------
#
# Strategy: every test gets its own Postgres SCHEMA inside the shared test
# database, so parallel tests can run without colliding and teardown is a
# single `DROP SCHEMA CASCADE`. The DB URL itself comes from
# `MOMDIARY_TEST_DB_URL` (falling back to `MOMDIARY_DB_URL`); CI is expected
# to point at a disposable database.
#
# We override `search_path` via asyncpg `server_settings` so all
# CREATE/INSERT inside the migration land in the schema, and tell Alembic
# its `alembic_version` bookkeeping table also lives there.


def _test_db_url() -> str:
    url = os.environ.get("MOMDIARY_TEST_DB_URL") or os.environ.get(
        "MOMDIARY_DB_URL"
    )
    if not url or not url.startswith("postgresql+asyncpg://"):
        pytest.skip(
            "MOMDIARY_TEST_DB_URL (or MOMDIARY_DB_URL) must point at a "
            "postgresql+asyncpg URL to run integration tests."
        )
    return url


async def _drop_test_schema_safely(url: str, schema: str) -> None:
    """Best-effort `DROP SCHEMA ... CASCADE`. Idempotent on missing schema."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url, future=True, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
            )
    except Exception:  # noqa: BLE001 — teardown is best-effort
        pass
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_schema() -> AsyncIterator[str]:
    """Yield a unique Postgres schema name; drop it after the test."""
    import uuid

    schema = f"test_{uuid.uuid4().hex[:8]}"
    url = _test_db_url()
    yield schema
    await _drop_test_schema_safely(url, schema)


@pytest_asyncio.fixture
async def configured_app(
    db_schema: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Any]:
    """Configure env, run migrations into an ephemeral schema, yield FastAPI app."""
    import json as _json

    base_url = _test_db_url()
    # Inject search_path so every CREATE in the migration lands in the
    # per-test schema. asyncpg honours `server_settings` from the URL via
    # SQLAlchemy's connect_args; we expose it through MOMDIARY_DB_URL by
    # appending a marker the engine wrapper can pick up... but the cleanest
    # path is to set the env to a URL whose connect_args include the schema.
    # We achieve this by overriding the engine creation path: env vars stay
    # standard, and we create-the-schema + set search_path via a one-shot
    # bootstrap connection before alembic runs.
    monkeypatch.setenv("MOMDIARY_DB_URL", base_url)
    monkeypatch.setenv("MOMDIARY_DEFAULT_TIMEZONE", "America/Los_Angeles")
    monkeypatch.setenv("MOMDIARY_APP_ENV", "test")
    # Tests use the in-memory session store unless they explicitly opt into
    # PgSessionStore by clearing this env in their own setup.
    monkeypatch.setenv("MOMDIARY_SESSION_STORE", "memory")

    from momdiary.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()
    reset_timezone_cache()

    from momdiary.api.dependencies import reset_session_store_for_tests

    reset_session_store_for_tests()

    # 1. Bootstrap: create the schema in the target DB.
    from sqlalchemy.ext.asyncio import create_async_engine

    bootstrap = create_async_engine(base_url, future=True, echo=False)
    try:
        async with bootstrap.begin() as conn:
            await conn.exec_driver_sql(
                f'CREATE SCHEMA IF NOT EXISTS "{db_schema}"'
            )
    finally:
        await bootstrap.dispose()

    # 2. Run Alembic migrations *into* that schema.
    from alembic import command
    from alembic.config import Config

    cfg_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    alembic_cfg = Config(str(cfg_path))
    alembic_cfg.set_main_option(
        "script_location", str(cfg_path.parent / "alembic")
    )
    # Build a URL that pins search_path on every connection via asyncpg's
    # server_settings (passed through SQLAlchemy as a JSON query option).
    scoped_url = base_url
    alembic_cfg.set_main_option("sqlalchemy.url", scoped_url)
    # Also pin the alembic version table into the schema so it doesn't
    # collide with other parallel tests on the same DB.
    alembic_cfg.attributes["version_table_schema"] = db_schema  # type: ignore[index]

    # Run alembic in a thread; monkeypatch search_path inside the connect
    # event so every alembic connection lands in our schema.
    from sqlalchemy import event

    @event.listens_for(  # type: ignore[misc]
        __import__("sqlalchemy").engine.Engine, "connect"
    )
    def _set_search_path(dbapi_conn, _):  # noqa: ANN001
        # asyncpg connect path doesn't expose a sync DBAPI; this listener
        # is harmless if the connect doesn't carry a cursor (e.g. for
        # async paths the schema is applied via the per-engine connect
        # event in `_make_pg_engine` below).
        try:
            cur = dbapi_conn.cursor()
            cur.execute(f'SET search_path TO "{db_schema}", public')
            cur.close()
        except Exception:  # noqa: BLE001
            pass

    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    # 3. Re-create the app's engine with search_path baked into every
    #    asyncpg connection.
    from momdiary.db import engine as engine_mod

    monkeypatch.setattr(
        engine_mod,
        "_engine",
        None,
        raising=False,
    )

    # Patch the engine factory to inject server_settings.search_path.
    original_get_engine = engine_mod.get_engine

    def _patched_get_engine() -> Any:
        from sqlalchemy.ext.asyncio import (
            async_sessionmaker as _amk,
            create_async_engine as _cae,
        )

        if engine_mod._engine is None:
            settings = get_settings()
            engine_mod._engine = _cae(
                settings.momdiary_db_url,
                future=True,
                echo=False,
                pool_size=settings.momdiary_db_pool_size,
                max_overflow=settings.momdiary_db_max_overflow,
                pool_pre_ping=True,
                pool_recycle=1800,
                connect_args={
                    "server_settings": {
                        "search_path": f'{db_schema},public',
                    }
                },
            )
            engine_mod._session_factory = _amk(
                bind=engine_mod._engine,
                expire_on_commit=False,
            )
        return engine_mod._engine

    monkeypatch.setattr(engine_mod, "get_engine", _patched_get_engine)

    from momdiary.main import create_app

    app = create_app()
    try:
        yield app
    finally:
        await dispose_engine()
        reset_engine_for_tests()
        get_settings.cache_clear()  # type: ignore[attr-defined]
        # restore the original get_engine binding
        monkeypatch.setattr(engine_mod, "get_engine", original_get_engine)


@dataclass
class SeedCaregiver:
    """Seed-data record for the default authenticated caregiver fixture."""

    user_id: int
    baby_id: int
    email: str
    password: str
    display_name: str
    session_token: str


@pytest_asyncio.fixture
async def seed_caregiver(configured_app: Any) -> SeedCaregiver:
    """Create a default user + baby + auth session for the test suite.

    Most legacy tests assume an anonymous "happy path". Feature 006 added an
    auth gate plus a baby-scoping context-var. To keep those tests valuable,
    every test gets a single default caregiver pre-seeded and the
    `active_baby_id` context-var pre-set; the `client` fixture also attaches
    the corresponding session cookie. Tests that need multi-tenant scenarios
    (e.g. T038, T040, T058) create extra users via `caregiver_factory`.
    """
    from momdiary.auth.context import set_active_baby_id
    from momdiary.auth.hasher import get_password_hasher
    from momdiary.auth.sessions import SessionService
    from momdiary.models.orm import Baby, User

    factory = get_session_factory()
    hasher = get_password_hasher()
    password = "Pa55word!seed"
    async with factory() as s:
        user = User(
            email="seed@example.com",
            password_hash=hasher.hash(password),
            display_name="Seed Caregiver",
        )
        s.add(user)
        await s.flush()
        baby = Baby(
            owner_user_id=user.id,
            display_name="Seed Baby",
            date_of_birth="2025-01-01",
        )
        s.add(baby)
        await s.flush()
        user.active_baby_id = baby.id
        sessions = SessionService(s, ttl_days=30)
        sess = await sessions.create(user_id=user.id, user_agent="pytest")
        await s.commit()
        token = sess.id
        user_id, baby_id = user.id, baby.id

    set_active_baby_id(baby_id)
    return SeedCaregiver(
        user_id=user_id,
        baby_id=baby_id,
        email="seed@example.com",
        password=password,
        display_name="Seed Caregiver",
        session_token=token,
    )


@pytest_asyncio.fixture
async def caregiver_factory(
    configured_app: Any,
) -> Any:
    """Returns an async callable that creates additional caregivers on demand.

    Usage:
        carol = await caregiver_factory(email="carol@example.com", baby_name="Cara")
        # carol.user_id, carol.baby_id, carol.session_token
    """
    from momdiary.auth.hasher import get_password_hasher
    from momdiary.auth.sessions import SessionService
    from momdiary.models.orm import Baby, User

    factory = get_session_factory()
    hasher = get_password_hasher()

    async def _make(
        *,
        email: str,
        password: str = "Pa55word!alt",
        display_name: str = "Alt Caregiver",
        baby_name: str | None = "Alt Baby",
        date_of_birth: str = "2025-01-01",
    ) -> SeedCaregiver:
        async with factory() as s:
            user = User(
                email=email,
                password_hash=hasher.hash(password),
                display_name=display_name,
            )
            s.add(user)
            await s.flush()
            baby_id: int | None = None
            if baby_name is not None:
                baby = Baby(
                    owner_user_id=user.id,
                    display_name=baby_name,
                    date_of_birth=date_of_birth,
                )
                s.add(baby)
                await s.flush()
                user.active_baby_id = baby.id
                baby_id = baby.id
            sessions = SessionService(s, ttl_days=30)
            sess = await sessions.create(user_id=user.id, user_agent="pytest")
            await s.commit()
            return SeedCaregiver(
                user_id=user.id,
                baby_id=baby_id or 0,
                email=email,
                password=password,
                display_name=display_name,
                session_token=sess.id,
            )

    return _make


@pytest_asyncio.fixture
async def session(
    configured_app: Any, seed_caregiver: SeedCaregiver
) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as s:
        yield s


# ---------------------------------------------------------------------------
# Scripted agent — deterministic, no live model (Principle II)
# ---------------------------------------------------------------------------


@dataclass
class _ScriptItem:
    tool_name: str
    kwargs: dict[str, Any]


@dataclass
class ScriptedAgent:
    """Plays a pre-scripted sequence of tool invocations.

    Each `run()` call pops one `(tool_name, kwargs)` pair from the queue,
    executes it against the live session via the shared tool registry,
    and returns the resulting `AgentRunResult`. This means tests exercise
    the real repositories and produce real side effects — only the model
    is stubbed out.
    """

    _queue: list[_ScriptItem] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def script(self, tool_name: str, **kwargs: Any) -> "ScriptedAgent":
        self._queue.append(_ScriptItem(tool_name=tool_name, kwargs=kwargs))
        return self

    async def run(
        self,
        message: str,
        *,
        session: AsyncSession,
        correlation_id: str,
        entry_id: int | None = None,
        entry_type: str | None = None,
        history: list[Any] | None = None,
    ) -> AgentRunResult:
        self.calls.append(
            {
                "message": message,
                "correlation_id": correlation_id,
                "entry_id": entry_id,
                "entry_type": entry_type,
                "history": list(history) if history is not None else [],
            }
        )
        if not self._queue:
            raise AssertionError(
                "ScriptedAgent.run() called with no scripted tool calls remaining"
            )
        item = self._queue.pop(0)
        return await invoke_tool(item.tool_name, session, **item.kwargs)


@pytest.fixture
def scripted_agent() -> ScriptedAgent:
    return ScriptedAgent()


# ---------------------------------------------------------------------------
# Opt-in HTTP tracing
# ---------------------------------------------------------------------------
# Set `MOMDIARY_TEST_TRACE=1` and run pytest with `-s` to see the request and
# response body of every API call made by the test client. Useful for
# debugging agent routing and dedup behavior. Output goes to stderr so it's
# visible even when stdout capturing is enabled.
def _trace_enabled() -> bool:
    return os.environ.get("MOMDIARY_TEST_TRACE", "").lower() in {"1", "true", "yes"}


def _pretty(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return json.dumps(json.loads(raw.decode("utf-8")), indent=2, default=str)
    except Exception:
        try:
            return raw.decode("utf-8")
        except Exception:
            return repr(raw)


async def _log_request(request: Request) -> None:
    body = _pretty(request.content or b"")
    print(
        f"\n>>> {request.method} {request.url}"
        + (f"\n{body}" if body else ""),
        file=sys.stderr,
    )


async def _log_response(response: Response) -> None:
    await response.aread()
    body = _pretty(response.content)
    print(
        f"<<< {response.status_code} {response.request.method} {response.request.url}"
        + (f"\n{body}" if body else ""),
        file=sys.stderr,
    )


def _trace_hooks() -> dict[str, list[Any]]:
    if not _trace_enabled():
        return {}
    return {"request": [_log_request], "response": [_log_response]}


@pytest_asyncio.fixture
async def client(
    configured_app: Any,
    scripted_agent: ScriptedAgent,
    seed_caregiver: SeedCaregiver,
) -> AsyncIterator[AsyncClient]:
    configured_app.dependency_overrides[get_agent_runner] = lambda: scripted_agent
    async with AsyncClient(
        transport=ASGITransport(app=configured_app),
        base_url="http://test",
        event_hooks=_trace_hooks(),
    ) as c:
        c.cookies.set("momdiary_session", seed_caregiver.session_token)
        yield c
    configured_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client(
    configured_app: Any, scripted_agent: ScriptedAgent
) -> AsyncIterator[AsyncClient]:
    """Anonymous HTTP client — no session cookie attached.

    Use this for register/login flows and for tests that explicitly verify
    the 401 unauthenticated path.
    """
    configured_app.dependency_overrides[get_agent_runner] = lambda: scripted_agent
    async with AsyncClient(
        transport=ASGITransport(app=configured_app),
        base_url="http://test",
        event_hooks=_trace_hooks(),
    ) as c:
        yield c
    configured_app.dependency_overrides.clear()
