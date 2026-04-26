#!/usr/bin/env python3
"""Verify and optionally repair the production Vercel alias.

The safe default is read-only: compare the configured alias with the latest
READY production deployment for the project and print the exact repair action if
the alias is stale. The script only mutates Vercel when both --repair and --yes
are passed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.vercel.com"
DEFAULT_ALIAS = "snusmic-quant-terminal.vercel.app"
DEFAULT_PROJECT = "snusmic-quant-terminal"
REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_JSON = REPO_ROOT / ".vercel" / "project.json"


class VercelError(RuntimeError):
    """Raised when Vercel returns an error response."""


def load_linked_project_id() -> str | None:
    if not PROJECT_JSON.exists():
        return None
    try:
        data = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VercelError(f"{PROJECT_JSON} is not valid JSON: {exc}") from exc
    value = data.get("projectId")
    return str(value) if value else None


def with_team_query(path: str, team: str | None) -> str:
    if not team:
        return path
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}{urllib.parse.urlencode({'teamId': team})}"


def api_request(
    token: str,
    path: str,
    *,
    team: str | None = None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> Any:
    url = f"{API_BASE}{with_team_query(path, team)}"
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "snusmic-vercel-alias-guard/1.0",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise VercelError(f"Vercel API {method} {path} failed with HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise VercelError(f"Vercel API {method} {path} failed: {exc.reason}") from exc
    return json.loads(raw) if raw else None


def get_alias(token: str, alias: str, project: str, team: str | None) -> dict[str, Any] | None:
    quoted_alias = urllib.parse.quote(alias, safe="")
    quoted_project = urllib.parse.quote(project, safe="")
    path = f"/v4/aliases/{quoted_alias}?projectId={quoted_project}"
    try:
        data = api_request(token, path, team=team)
    except VercelError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise
    if isinstance(data, list):
        return data[0] if data else None
    return data if isinstance(data, dict) else None


def latest_ready_production(token: str, project: str, team: str | None) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            "projectId": project,
            "target": "production",
            "state": "READY",
            "limit": "1",
        }
    )
    data = api_request(token, f"/v6/deployments?{params}", team=team)
    deployments = data.get("deployments", []) if isinstance(data, dict) else []
    return deployments[0] if deployments else None


def assign_alias(token: str, deployment_id: str, alias: str, team: str | None) -> Any:
    quoted_id = urllib.parse.quote(deployment_id, safe="")
    return api_request(
        token,
        f"/v2/deployments/{quoted_id}/aliases",
        team=team,
        method="POST",
        body={"alias": alias, "redirect": None},
    )


def deployment_id(deployment: dict[str, Any]) -> str | None:
    value = deployment.get("uid") or deployment.get("id")
    return str(value) if value else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run guard for the SNUSMIC Vercel production alias.")
    parser.add_argument("--alias", default=os.getenv("VERCEL_ALIAS", DEFAULT_ALIAS))
    parser.add_argument(
        "--project",
        default=os.getenv("VERCEL_PROJECT_ID") or load_linked_project_id() or DEFAULT_PROJECT,
        help="Vercel project id/name. Defaults to VERCEL_PROJECT_ID, .vercel/project.json, then repo name.",
    )
    parser.add_argument("--team", default=os.getenv("VERCEL_TEAM_ID"), help="Optional Vercel team id.")
    parser.add_argument(
        "--token-env", default="VERCEL_TOKEN", help="Environment variable containing the Vercel token."
    )
    parser.add_argument(
        "--repair", action="store_true", help="Repair stale/missing alias if --yes is also set."
    )
    parser.add_argument("--yes", action="store_true", help="Allow the --repair mutation. Omit for dry-run.")
    args = parser.parse_args(argv)

    token = os.getenv(args.token_env)
    if not token:
        print(
            f"DRY RUN: set {args.token_env}=<token> to compare {args.alias} with the latest "
            f"READY production deployment for project {args.project!r}."
        )
        print("No Vercel API mutation was attempted.")
        return 0

    alias_record = get_alias(token, args.alias, args.project, args.team)
    latest = latest_ready_production(token, args.project, args.team)
    if latest is None:
        print(f"ERROR: no READY production deployments found for project {args.project!r}.", file=sys.stderr)
        return 2

    latest_id = deployment_id(latest)
    if latest_id is None:
        print(
            "ERROR: latest production deployment response did not include a deployment id.", file=sys.stderr
        )
        return 2

    current_id = None if alias_record is None else alias_record.get("deploymentId")
    latest_url = latest.get("url") or latest_id

    print(f"alias:              {args.alias}")
    print(f"project:            {args.project}")
    if args.team:
        print(f"team:               {args.team}")
    print(f"latest production:  {latest_id} ({latest_url})")
    print(f"current alias dpl:  {current_id or 'missing'}")

    if current_id == latest_id:
        print("OK: alias already points at the latest READY production deployment.")
        return 0

    print("STALE: alias is missing or points at a different deployment.")
    print(
        "Repair action: POST "
        f"/v2/deployments/{latest_id}/aliases with body "
        f"{{'alias': '{args.alias}', 'redirect': None}}"
    )

    if not args.repair:
        print("DRY RUN: add --repair --yes to execute the alias reassignment.")
        return 2
    if not args.yes:
        print("DRY RUN: --repair was set without --yes; no mutation was attempted.")
        return 2

    result = assign_alias(token, latest_id, args.alias, args.team)
    print("REPAIRED: Vercel accepted the alias reassignment.")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
