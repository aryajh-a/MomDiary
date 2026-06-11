# Quickstart — Modular Agent Skills

Date: 2026-06-03 · Feature: `010-agent-skills-split`

This is the operator/contributor cheat sheet for the new skill-split agent.
For the full design see [plan.md](./plan.md), [data-model.md](./data-model.md),
and [contracts/skill-registry.md](./contracts/skill-registry.md).

---

## 1. Where things live

```text
backend/src/momdiary/agents/
├── diary_agent.py          # BASE_SYSTEM_PROMPT + build_agent(selected_skills=…)
├── maf_runner.py           # picks skills from router decision
├── skill_registry.py       # eager-load registry (REGISTRY singleton)
└── skills/
    ├── appointment/SKILL.md
    ├── feed/SKILL.md
    ├── poop/SKILL.md
    └── sleep/SKILL.md
```

---

## 2. Verify the registry loads (smoke check)

After pulling this branch:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -c "from momdiary.agents.skill_registry import REGISTRY; print(REGISTRY.names())"
# Expected: ('appointment', 'feed', 'poop', 'sleep')
```

If any skill file is missing or empty, this command MUST raise `RuntimeError`
with a clear message naming the offending file. Same error MUST appear if
you start uvicorn with a missing skill — the server must refuse to come up.

---

## 3. Run the targeted tests

```powershell
cd backend
pytest tests/unit/test_skill_separation.py tests/unit/test_maf_runner_prompt.py -v
```

Both files MUST pass after the feature lands. Coverage gates in
`pyproject.toml` remain at ≥80%; this feature only adds tests, so the
overall percentage may only go up.

---

## 4. Edit a single domain's behaviour (the maintainer scenario)

Want to teach the feed skill that "biberon" means a formula bottle?

1. Open `backend/src/momdiary/agents/skills/feed/SKILL.md`.
2. Add `biberon` to the formula synonyms section. Save.
3. Run `pytest tests/unit/test_skill_separation.py` — this verifies the
   change did not bleed into other domains.
4. Restart uvicorn. The new wording is now in feed-routed prompts only;
   sleep/poop/appointment prompts are byte-identical to before.

No other file needs to change for a pure rules update.

---

## 5. Add a fifth domain (out-of-scope here, but here is the recipe)

Should we ever add e.g. medication tracking:

1. Create `backend/src/momdiary/agents/skills/medication/__init__.py` and
   `SKILL.md`.
2. Extend the `SkillName` literal in `skill_registry.py`.
3. Add `medication` to the intent router's resource patterns.
4. Update the forbidden-token table in
   `tests/unit/test_skill_separation.py` and add tool wrappers in
   `maf_runner.py` per the existing pattern.

No change required to `select_skills_for` — it auto-picks up whatever the
registry exposes.

---

## 6. Manual prompt-size check (SC-001)

```powershell
cd backend
python -c "
from momdiary.agents.diary_agent import BASE_SYSTEM_PROMPT, build_agent
from momdiary.agents.skill_registry import REGISTRY
from unittest.mock import patch
# Skip MAF agent instantiation; just compose the prompt string.
from momdiary.agents.diary_agent import _assemble_prompt  # helper added by feature
single = _assemble_prompt(['feed'])
full = _assemble_prompt(list(REGISTRY.names()))
print('single len:', len(single), ' full len:', len(full))
print('ratio:', round(len(single) / len(full), 2))
"
```

Expected: routed single-domain prompt is ≤ 60% of the full prompt
(SC-001).

---

## 7. Rolling back

This feature touches only backend code and adds files. To revert:

```powershell
git revert <merge-commit>
```

No database migrations, no env-var changes, no frontend impact.
