#!/usr/bin/env python3
"""Export Pydantic-v2 table models to committed JSON Schemas.

For every model in the warehouse-table and JSON-artifact schema registries, emit
``docs/schemas/{name}.schema.json`` with Phase-1a column-level metadata:

* ``x-snusmic-semantic-version`` — model-level ``semantic_version`` (default "1.0").
* ``properties.{col}.x-snusmic-nan-policy`` — per-column ``nan_policy``
  derived from the model's ``column_nan_policy`` ClassVar.

Principle 6 compliance: a change to either ``semantic_version`` or any
``nan_policy`` value WITHOUT shipping a ``.v2.schema.json`` sidecar is rejected
by :mod:`scripts.check_schema_compat`.

Usage:
    uv run python scripts/export_schemas.py          # regenerate
    uv run python scripts/export_schemas.py --check  # non-zero exit on diff
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from snusmic_pipeline.sim.schemas import TABLE_MODELS

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "docs" / "schemas"


def build_schema(name: str, model: type[BaseModel]) -> dict:
    """Render the JSON Schema for ``model`` enriched with Phase-1a metadata."""
    schema = model.model_json_schema()
    schema["x-snusmic-table"] = name
    schema["x-snusmic-semantic-version"] = getattr(model, "semantic_version", "1.0")

    nan_policy = getattr(model, "column_nan_policy", {}) or {}
    properties = schema.get("properties", {})
    for col, policy in nan_policy.items():
        if col in properties:
            properties[col]["x-snusmic-nan-policy"] = policy
    # Columns without an explicit nan_policy get the default so every committed
    # schema is self-describing (schema-compat check does not need to diff
    # "present vs. absent" vs. "drop vs. forward_fill_then_flag").
    for col, prop in properties.items():
        prop.setdefault("x-snusmic-nan-policy", nan_policy.get(col, "drop"))
    return schema


def emit_all() -> dict[str, str]:
    """Return a ``{path: serialized_json}`` mapping for every schema model."""
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, str] = {}
    for name, model in sorted(TABLE_MODELS.items()):
        schema = build_schema(name, model)
        target = SCHEMAS_DIR / f"{name}.schema.json"
        payloads[str(target)] = json.dumps(schema, indent=2, sort_keys=False) + "\n"
    return payloads


def write_all(payloads: dict[str, str]) -> list[Path]:
    written: list[Path] = []
    for path_str, body in payloads.items():
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written


def check_all(payloads: dict[str, str]) -> list[tuple[Path, str]]:
    """Return ``[(path, diff_reason), …]`` for any committed schema that drifts
    from the regenerated payload."""
    drifts: list[tuple[Path, str]] = []
    for path_str, body in payloads.items():
        path = Path(path_str)
        if not path.exists():
            drifts.append((path, "missing from repo — run `uv run python scripts/export_schemas.py`"))
            continue
        committed = path.read_text(encoding="utf-8")
        if committed != body:
            drifts.append((path, "differs from model-derived output"))
    return drifts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail (exit 1) if committed schemas differ from model-derived output.",
    )
    args = parser.parse_args(argv)

    payloads = emit_all()

    if args.check:
        drifts = check_all(payloads)
        if drifts:
            print("schema drift detected:", file=sys.stderr)
            for path, reason in drifts:
                print(f"  {path}: {reason}", file=sys.stderr)
            print(
                "\nRegenerate with `uv run python scripts/export_schemas.py`"
                " and commit the updated docs/schemas/*.json.",
                file=sys.stderr,
            )
            return 1
        print(f"schema drift check: {len(payloads)} schemas up to date")
        return 0

    written = write_all(payloads)
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
