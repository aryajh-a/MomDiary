"""Contract test: verify the OpenAPI surface matches the spec contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from momdiary.main import create_app

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-baby-tracker-backend"
    / "contracts"
    / "openapi.yaml"
)


@pytest.fixture(scope="module")
def contract_paths() -> set[str]:
    spec = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return set(spec["paths"].keys())


def test_app_exposes_all_contract_paths(contract_paths: set[str]) -> None:
    app = create_app()
    openapi = app.openapi()
    actual = set(openapi["paths"].keys())
    missing = contract_paths - actual
    assert not missing, f"App is missing contract paths: {sorted(missing)}"
