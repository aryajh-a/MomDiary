"""Microsoft Agent Framework agent factory (Principle V).

The agent is built around an Azure OpenAI chat client backed by Azure AI
Foundry's `gpt-4.1` deployment. Tools are registered by the dispatcher /
phase-specific wiring code; this module only owns model client + system
prompt + base ChatAgent construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from azure.identity import DefaultAzureCredential

from momdiary.config import get_settings
from momdiary.observability.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - import guard for environments without MAF installed
    from agent_framework_azure_ai import AzureOpenAIChatClient  # type: ignore[import-not-found,import-untyped]
    from agent_framework import Agent  # type: ignore[import-not-found,import-untyped]
except Exception:  # noqa: BLE001
    AzureOpenAIChatClient = None  # type: ignore[assignment,misc]
    Agent = None  # type: ignore[assignment,misc]


SYSTEM_PROMPT = """\
You are MomDiary, an assistant that records baby-care events for a single
caregiver. You MUST obey these rules:

1. Choose exactly ONE tool per message; never fabricate fields.
2. If any required field is missing or ambiguous (time, quantity, type),
   call `ask_for_clarification` instead of guessing.
3. For updates or deletes (FR-017): if the request envelope provides
   `entry_id` and `entry_type`, treat them as authoritative and call the
   matching `update_*` or `delete_*` tool. Otherwise infer the target from
   the user's description; if multiple candidates match, call
   `ask_for_clarification` with the candidate list.
4. Never operate on soft-deleted entries (FR-018). Treat them as
   non-existent for target resolution and for further deletes.
5. Quantities expressed in ounces are converted to millilitres by the
   normalization layer; pass the user's verbatim unit to the tool.
6. Return concise confirmation text — one sentence — in the tool result.
7. Appointment note text is append-only via `add_appointment_note`;
   never overwrite existing notes.
"""


@dataclass
class AgentBundle:
    """Wrapper exposing the constructed agent and its registered tool list."""

    agent: Any
    tools: list[Any] = field(default_factory=list)


def _build_chat_client() -> Any:
    """Construct an AzureOpenAIChatClient using DefaultAzureCredential.

    Per Principle IV, the backend authenticates to Azure OpenAI / Foundry
    exclusively via Microsoft Entra ID. No API-key code path is supported.
    """
    if AzureOpenAIChatClient is None:
        raise RuntimeError(
            "agent-framework-azure-ai is not installed. "
            "Run `pip install --pre agent-framework agent-framework-azure-ai`."
        )
    settings = get_settings()
    credential = DefaultAzureCredential()
    logger.info(
        "diary_agent.chat_client.building",
        endpoint=settings.azure_openai_endpoint,
        deployment=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
    )
    return AzureOpenAIChatClient(
        endpoint=settings.azure_openai_endpoint,
        deployment_name=settings.azure_openai_deployment,
        api_version=settings.azure_openai_api_version,
        credential=credential,
    )


def default_tool_list() -> list[Any]:
    """The full set of MomDiary MAF tools registered on the agent.

    Mirrors `agents.tools.registry.TOOL_REGISTRY` plus the pseudo
    `ask_for_clarification` tool implemented inside the registry's
    `invoke_tool` dispatcher (T033 + T067).
    """
    from momdiary.agents.tools.registry import TOOL_REGISTRY

    return list(TOOL_REGISTRY.values())


def build_agent(tools: list[Any] | None = None) -> AgentBundle:
    """Build an Agent with the given tool list (defaults to the full set)."""
    if Agent is None:
        raise RuntimeError(
            "agent-framework is not installed. "
            "Run `pip install --pre agent-framework==1.0.0rc6 agent-framework-azure-ai==1.0.0rc6`."
        )
    client = _build_chat_client()
    tool_list = list(tools) if tools is not None else default_tool_list()
    agent = Agent(
        client,
        SYSTEM_PROMPT,
        tools=tool_list,
    )
    return AgentBundle(agent=agent, tools=tool_list)
