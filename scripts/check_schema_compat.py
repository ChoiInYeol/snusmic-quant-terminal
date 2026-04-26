#!/usr/bin/env python3
"""Principle-6 CI gate.

Compares every ``docs/schemas/{table}.schema.json`` in the current working tree
against the same file at ``--base-ref`` (default ``origin/main``) and fails when:

  (a) a top-level ``properties`` key is **deleted** without a sibling
      ``docs/schemas/{table}.v2.schema.json`` committed in the PR, OR
  (b) a column's ``x-snusmic-semantic-version`` or ``x-snusmic-nan-policy``
      value **changes** without a sibling ``.v2.schema.json``.

Additive changes — new columns or new tables — pass silently.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "docs" / "schemas"
DECISIONS_DIR = REPO_ROOT / "docs" / "decisions"
PHASE_2_OBJECTIVE_DOC = DECISIONS_DIR / "phase-2-objective.md"


def load_current(table: str) -> dict | None:
    path = SCHEMAS_DIR / f"{table}.schema.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_base(base_ref: str, table: str) -> dict | None:
    rel = f"docs/schemas/{table}.schema.json"
    try:
        out = subprocess.run(
            ["git", "show", f"{base_ref}:{rel}"],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    if not out.stdout.strip():
        return None
    return json.loads(out.stdout)


def list_tables(base_ref: str) -> list[str]:
    """Enumerate table names across working tree + base ref."""
    names: set[str] = set()
    for path in SCHEMAS_DIR.glob("*.schema.json"):
        if path.name.endswith(".v2.schema.json"):
            continue
        names.add(path.stem.removesuffix(".schema"))
    try:
        out = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", base_ref, "--", "docs/schemas/"],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return sorted(names)
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".schema.json") or line.endswith(".v2.schema.json"):
            continue
        names.add(Path(line).stem.removesuffix(".schema"))
    return sorted(names)


def has_v2_sidecar(table: str) -> bool:
    return (SCHEMAS_DIR / f"{table}.v2.schema.json").exists()


def read_primary_objective() -> str | None:
    """Read ``docs/decisions/phase-2-objective.md`` for the locked
    ``primary_objective``. Missing file / missing key returns ``None`` (not
    a failure; Phase 1a projects pre-decision-file state)."""
    if not PHASE_2_OBJECTIVE_DOC.exists():
        return None
    text = PHASE_2_OBJECTIVE_DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("primary_objective:"):
            value = stripped.split(":", 1)[1].strip().strip("'\"")
            return value or None
    return None


def check_phase_2_objective_contract(current: dict | None) -> list[str]:
    """If the decision file pins ``primary_objective``, require the
    ``strategy_runs`` schema to carry ``{obj}_in_sample`` / ``{obj}_oos``
    columns. This enforces the Phase 2 column-naming contract at CI time."""
    violations: list[str] = []
    objective = read_primary_objective()
    if objective is None or current is None:
        return violations
    props = (current or {}).get("properties") or {}
    expected = [f"{objective}_in_sample", f"{objective}_oos"]
    for col in expected:
        if col not in props:
            violations.append(
                f"strategy_runs: docs/decisions/phase-2-objective.md pins "
                f"primary_objective={objective!r}, but column {col!r} is absent "
                f"from docs/schemas/strategy_runs.schema.json."
            )
    return violations


def diff_one(table: str, base: dict, current: dict) -> list[str]:
    """Return a list of Principle-6 violations for one table."""
    violations: list[str] = []
    base_props = (base or {}).get("properties") or {}
    cur_props = (current or {}).get("properties") or {}

    # (a) Deletion check.
    deleted_cols = sorted(set(base_props) - set(cur_props))
    if deleted_cols and not has_v2_sidecar(table):
        violations.append(
            f"{table}: column(s) {deleted_cols} deleted without a "
            f"docs/schemas/{table}.v2.schema.json sidecar (Principle 6 (a))."
        )

    # Model-level semantic_version change.
    base_ver = base.get("x-snusmic-semantic-version")
    cur_ver = current.get("x-snusmic-semantic-version")
    if base_ver is not None and cur_ver is not None and base_ver != cur_ver and not has_v2_sidecar(table):
        violations.append(
            f"{table}: x-snusmic-semantic-version changed {base_ver!r} → {cur_ver!r} "
            f"without a docs/schemas/{table}.v2.schema.json sidecar (Principle 6 (b))."
        )

    # (b) Column-level nan_policy / semantic metadata drift.
    for col in sorted(set(base_props) & set(cur_props)):
        base_col = base_props[col] or {}
        cur_col = cur_props[col] or {}
        base_nan = base_col.get("x-snusmic-nan-policy")
        cur_nan = cur_col.get("x-snusmic-nan-policy")
        if base_nan != cur_nan and not has_v2_sidecar(table):
            violations.append(
                f"{table}.{col}: x-snusmic-nan-policy changed {base_nan!r} → {cur_nan!r} "
                f"without a docs/schemas/{table}.v2.schema.json sidecar (Principle 6 (b))."
            )
        base_semver_col = base_col.get("x-snusmic-semantic-version")
        cur_semver_col = cur_col.get("x-snusmic-semantic-version")
        if (
            base_semver_col is not None
            and cur_semver_col is not None
            and base_semver_col != cur_semver_col
            and not has_v2_sidecar(table)
        ):
            violations.append(
                f"{table}.{col}: x-snusmic-semantic-version changed "
                f"{base_semver_col!r} → {cur_semver_col!r} without a .v2 sidecar (Principle 6 (b))."
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git ref to compare schemas against (default: origin/main).",
    )
    args = parser.parse_args(argv)

    all_violations: list[str] = []
    tables = list_tables(args.base_ref)
    for table in tables:
        base = load_base(args.base_ref, table)
        current = load_current(table)
        if base is None:
            # New table — additive, pass.
            if table == "strategy_runs":
                all_violations.extend(check_phase_2_objective_contract(current))
            continue
        if current is None:
            # Table removed entirely. Require .v2 sidecar.
            if not has_v2_sidecar(table):
                all_violations.append(
                    f"{table}: entire schema removed without a "
                    f"docs/schemas/{table}.v2.schema.json sidecar (Principle 6 (a))."
                )
            continue
        all_violations.extend(diff_one(table, base, current))
        if table == "strategy_runs":
            all_violations.extend(check_phase_2_objective_contract(current))

    if all_violations:
        print("Principle-6 schema-compat violations:", file=sys.stderr)
        for v in all_violations:
            print(f"  - {v}", file=sys.stderr)
        print(
            "\nIf this change is intentional, commit a sibling .v2.schema.json file "
            "per plan Principle 6.",
            file=sys.stderr,
        )
        return 1

    print(f"schema-compat check: {len(tables)} tables, no Principle-6 violations against {args.base_ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
