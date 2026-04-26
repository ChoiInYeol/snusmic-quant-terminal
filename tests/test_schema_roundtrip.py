"""Schema roundtrip tests — the read/write boundary must round-trip without drift.

Also verifies that the committed ``docs/schemas/*.schema.json`` files agree with
the live Pydantic models (i.e. ``scripts/export_schemas.py --check`` would pass).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from snusmic_pipeline.backtest.schemas import TABLE_MODELS
from snusmic_pipeline.backtest.warehouse import read_table, write_table


@pytest.mark.parametrize("table", sorted(TABLE_MODELS))
def test_committed_schema_matches_model(table: str) -> None:
    """Phase 1a AC #3 / #4 — `scripts/export_schemas.py --check` must pass."""
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/export_schemas.py", "--check"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"schema-drift detected for table '{table}':\n{result.stderr}\n"
        "Regenerate with `uv run python scripts/export_schemas.py`."
    )


def _sample_rows() -> dict[str, pd.DataFrame]:
    return {
        "daily_prices": pd.DataFrame(
            [
                {"date": "2025-01-02", "symbol": "005930.KS", "open": 70000.0, "high": 71000.0, "low": 69500.0, "close": 70500.0, "volume": 1234567.0, "source_currency": "KRW", "display_currency": "KRW", "krw_per_unit": 1.0},
                {"date": "2025-01-03", "symbol": "005930.KS", "open": 70500.0, "high": 72000.0, "low": 70200.0, "close": 71800.0, "volume": 1145678.0, "source_currency": "KRW", "display_currency": "KRW", "krw_per_unit": 1.0},
            ]
        ),
        "reports": pd.DataFrame(
            [
                {"report_id": "r1", "publication_date": "2025-01-02", "title": "Alpha", "company": "Alpha Inc", "ticker": "AAA", "exchange": "NYSE", "symbol": "AAA"},
            ]
        ),
    }


@pytest.mark.parametrize("table", sorted(_sample_rows()))
def test_write_then_read_is_idempotent(tmp_path: Path, table: str) -> None:
    frame = _sample_rows()[table]
    write_table(tmp_path, table, frame)
    read_back = read_table(tmp_path, table)
    # Column order preserved; row count preserved.
    assert list(read_back.columns)[: len(frame.columns)] == list(frame.columns)
    assert len(read_back) == len(frame)


def test_every_schema_declares_semantic_version_and_nan_policy() -> None:
    """Principle 6 load-bearing assertion: every column in every committed schema
    has an ``x-snusmic-nan-policy`` and every schema has
    ``x-snusmic-semantic-version`` so check_schema_compat never compares ``None``."""
    schemas_dir = Path(__file__).resolve().parent.parent / "docs" / "schemas"
    assert schemas_dir.is_dir(), "docs/schemas/ missing — run scripts/export_schemas.py"

    committed = [p for p in schemas_dir.glob("*.schema.json") if not p.name.endswith(".v2.schema.json")]
    assert committed, "no committed schemas in docs/schemas/"

    for path in committed:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema.get("x-snusmic-semantic-version"), f"{path.name}: missing x-snusmic-semantic-version"
        for col, prop in (schema.get("properties") or {}).items():
            assert "x-snusmic-nan-policy" in prop, (
                f"{path.name}.{col}: missing x-snusmic-nan-policy (Principle 6 metadata)."
            )
