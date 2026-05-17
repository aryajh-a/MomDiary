<!--
SYNC IMPACT REPORT
==================
Version change: (uninitialized template) → 1.0.0
Rationale: Initial ratification of the MomDiary constitution. MAJOR baseline
since no prior governed version existed.

Modified principles:
- [PRINCIPLE_1_NAME] → I. Code Quality & Maintainability
- [PRINCIPLE_2_NAME] → II. Testing Standards (NON-NEGOTIABLE)
- [PRINCIPLE_3_NAME] → III. Performance Requirements
- [PRINCIPLE_4_NAME] → IV. Modular Architecture
- [PRINCIPLE_5_NAME] → V. Microsoft Agent Framework First (NON-NEGOTIABLE)

Added sections:
- Technology & Dependency Constraints (replaces [SECTION_2_NAME])
- Development Workflow & Quality Gates (replaces [SECTION_3_NAME])

Removed sections:
- None

Templates requiring updates:
- ✅ .specify/templates/plan-template.md — Constitution Check gate text is
  generic; reviewers MUST map gates to principles I–V at /speckit.plan time.
  No structural edit required.
- ✅ .specify/templates/spec-template.md — No constitution-driven sections
  added or removed; no update required.
- ✅ .specify/templates/tasks-template.md — Existing phases already cover
  testing, modularity, and performance polish mandated here; no update
  required.
- ⚠ README.md / docs/quickstart.md — Not present; if added later, MUST
  reference this constitution and the Microsoft Agent Framework decision.

Follow-up TODOs:
- TODO(RATIFICATION_DATE): Confirm the original adoption date. Provisionally
  set to 2026-05-16; revise if an earlier adoption is documented.
-->

# MomDiary Constitution

## Core Principles

### I. Code Quality & Maintainability

All production code MUST be readable, self-consistent, and reviewable by a peer
unfamiliar with the change. Every merged change MUST satisfy:

- Conform to the project's configured linter and formatter; CI MUST fail on
  lint or format violations rather than producing warnings.
- Public APIs (functions, classes, agent contracts) MUST carry concise
  docstrings describing purpose, inputs, outputs, and failure modes.
- Cyclomatic complexity per function SHOULD stay ≤ 10; functions exceeding
  this MUST be refactored or accompanied by a written justification in the PR.
- No dead code, commented-out blocks, or `TODO` without an owner and tracking
  link.
- Naming MUST be intention-revealing; abbreviations are allowed only when
  they are domain-standard (e.g., `LLM`, `RAG`).

**Rationale**: MomDiary integrates agentic and user-facing logic where opaque
code multiplies debugging cost. Enforcing quality at merge time keeps the
surface area auditable as agents evolve.

### II. Testing Standards (NON-NEGOTIABLE)

Testing is a release gate, not a courtesy. The following rules are binding:

- Test-first for new behavior: tests MUST be authored and demonstrated
  failing before the implementing code is merged.
- Coverage floor: ≥ 80% line coverage and ≥ 70% branch coverage on changed
  packages; net coverage MUST NOT decrease in any PR.
- Required test tiers per feature: (a) unit tests for pure logic, (b)
  integration tests for any cross-module or cross-service interaction, and
  (c) contract tests for every agent tool, prompt schema, or external API
  surface.
- Agent behavior MUST be exercised by deterministic tests using mocked or
  recorded model responses; live-model calls in CI are prohibited except in
  an explicitly tagged, opt-in evaluation suite.
- Flaky tests MUST be quarantined within one business day and fixed or
  deleted within five; quarantined tests do not satisfy coverage gates.

**Rationale**: Non-deterministic agent outputs make regression detection
impossible without strict, deterministic test discipline. The coverage and
contract-test floors prevent silent drift in tool and prompt interfaces.

### III. Performance Requirements

Performance is a first-class functional requirement and MUST be measured, not
assumed:

- Interactive user actions MUST complete with p95 latency ≤ 2 seconds and
  p99 ≤ 5 seconds, excluding upstream model inference time, which MUST be
  reported separately.
- Agent invocations MUST stream partial output within 1 second of request
  acceptance when the underlying model supports streaming.
- Memory usage per long-lived process MUST remain bounded; any feature
  introducing unbounded caches, conversation history, or queues MUST
  document the bound and eviction policy.
- Every PR that touches a hot path (request handling, agent dispatch, prompt
  assembly, persistence) MUST include or update a benchmark; regressions
  > 10% on a tracked benchmark BLOCK merge until justified or fixed.
- Performance budgets MUST be encoded as automated checks where feasible
  (load tests, micro-benchmarks) rather than relying on manual observation.

**Rationale**: A diary-centric agent product loses users at the first hang.
Quantified budgets make performance a verifiable property rather than a
post-hoc concern.

### IV. Modular Architecture

Code MUST be organized into small, replaceable modules with explicit
contracts:

- Each module MUST have a single, stated responsibility and a documented
  public interface; cross-module access MUST go through that interface.
- Cyclic dependencies between modules are PROHIBITED; CI SHOULD enforce
  this via static analysis where available.
- Agent capabilities (tools, prompts, memory providers, model clients) MUST
  be pluggable: replacing one implementation MUST NOT require edits in
  unrelated modules.
- Shared utilities MUST live in a clearly named common module; copy-paste
  reuse across more than two call sites MUST be refactored into shared code.
- Module boundaries MUST be reflected in the test layout: unit tests live
  with their module; integration tests live at the seam they validate.

**Rationale**: Agentic systems evolve by swapping models, tools, and prompts.
Modular boundaries turn those swaps into local edits instead of cross-cutting
rewrites.

### V. Microsoft Agent Framework First (NON-NEGOTIABLE)

All AI agent functionality in MomDiary MUST be built on the Microsoft
agentic framework (Microsoft Agent Framework). The following rules are
binding:

- New agents, tools, orchestrations, and agent-to-agent workflows MUST use
  Microsoft Agent Framework primitives; alternative agent frameworks MUST
  NOT be introduced without a constitutional amendment.
- Prerelease (preview, beta, RC, or nightly) versions of the Microsoft
  Agent Framework and its companion libraries ARE the approved baseline.
  Projects MUST track the latest prerelease cadence appropriate to the
  targeted capability; pinning to a stable release that lags required
  features requires a documented exception in `plan.md` complexity
  tracking.
- Build/CI configuration MUST permit prerelease resolution (e.g., enable
  prerelease feeds, allow `--prerelease` / preview package versions) for
  Microsoft Agent Framework packages only.
- Compiler and tooling warnings originating from Microsoft Agent Framework
  packages (including experimental/preview API warnings such as
  `SKEXPnnnn`, `MEAIxxx`, or equivalent prerelease diagnostics) MUST be
  suppressed at the narrowest possible scope (project file `NoWarn`, or
  per-call `#pragma`) and documented in a single
  `AGENT_FRAMEWORK_WARNINGS.md` (or equivalent section in the project
  file) listing each suppressed code and why.
- Suppression of warnings from non-Microsoft-Agent-Framework libraries is
  PROHIBITED under this principle; those MUST be fixed or escalated
  normally.
- Each release MUST record the exact prerelease versions consumed so that
  builds remain reproducible despite the moving target.

**Rationale**: MomDiary is intentionally a forward-leaning agent product.
Standardizing on Microsoft Agent Framework — including its prereleases —
gives the team early access to required capabilities, while bounded warning
suppression prevents preview-API noise from drowning out real defects.

## Technology & Dependency Constraints

- Approved agent stack: Microsoft Agent Framework (prerelease channel) plus
  Microsoft-supported model clients and connectors. Any additional AI/ML
  dependency MUST be justified in `plan.md` and reviewed against Principles
  IV and V.
- Dependency hygiene: all third-party packages MUST be pinned to explicit
  versions (including prereleases for Microsoft Agent Framework);
  transitive upgrades MUST be reviewed in PRs, not auto-merged.
- Secrets, model keys, and connection strings MUST be supplied via
  environment variables or a secret manager; they MUST NOT be committed,
  logged, or embedded in prompts.
- Observability: every agent invocation MUST emit a structured log record
  containing correlation ID, agent name, model identifier, latency, token
  usage (where available), and outcome (success / tool error / model
  error).
- Reproducibility: builds MUST be deterministic given a committed lockfile
  and the recorded prerelease versions from Principle V.

## Development Workflow & Quality Gates

- Branching: feature work MUST occur on `###-feature-name` branches created
  via the speckit workflow; direct commits to the default branch are
  prohibited.
- Required gates before merge:
  1. Lint, format, and static analysis pass.
  2. Unit, integration, and contract test suites pass with coverage floors
     from Principle II satisfied.
  3. Performance checks from Principle III pass or, on regression, include
     a reviewed justification.
  4. Constitution Check in `plan.md` is filled in and any violations are
     entered in Complexity Tracking with rationale.
- Code review: at least one reviewer other than the author MUST approve;
  reviewers are responsible for verifying compliance with Principles I–V.
- Agent-behavior changes (new tool, prompt edit, model swap) MUST include
  updated contract tests and an entry in the change log of the affected
  agent module.
- Documentation: any new public capability MUST be reflected in the
  feature's `quickstart.md` (when present) and in the agent's module
  README.

## Governance

- Authority: This constitution supersedes ad-hoc conventions and prior
  informal practices for MomDiary. Conflicts MUST be resolved in favor of
  the constitution.
- Amendments: Proposed amendments MUST be raised as a PR editing this file,
  include a Sync Impact Report at the top, follow the semantic-versioning
  policy below, and be approved by at least one maintainer.
- Versioning policy:
  - MAJOR: backward-incompatible removal or redefinition of a principle or
    governance rule.
  - MINOR: addition of a new principle/section or materially expanded rule.
  - PATCH: clarifications, wording, typo fixes, non-semantic refinements.
- Compliance review: maintainers MUST audit the repository against this
  constitution at least once per release cycle and file follow-ups for any
  drift.
- Runtime guidance: day-to-day agent and feature execution guidance lives
  in feature-specific `plan.md`, `quickstart.md`, and module READMEs;
  those documents MUST cite this constitution when introducing
  constraints.

**Version**: 1.0.0 | **Ratified**: 2026-05-16 | **Last Amended**: 2026-05-16
