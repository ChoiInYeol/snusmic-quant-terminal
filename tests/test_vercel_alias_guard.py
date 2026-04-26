from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_vercel_alias.py"
spec = importlib.util.spec_from_file_location("check_vercel_alias", MODULE_PATH)
assert spec and spec.loader
check_vercel_alias = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_vercel_alias)


def test_no_token_is_safe_dry_run(monkeypatch, capsys):
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)

    result = check_vercel_alias.main(["--project", "snusmic-quant-terminal"])

    assert result == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_stale_alias_reports_repair_without_mutation(monkeypatch, capsys):
    monkeypatch.setenv("VERCEL_TOKEN", "token")
    monkeypatch.setattr(
        check_vercel_alias,
        "get_alias",
        lambda token, alias, project, team: {"deploymentId": "dpl_old"},
    )
    monkeypatch.setattr(
        check_vercel_alias,
        "latest_ready_production",
        lambda token, project, team: {"uid": "dpl_new", "url": "snusmic-new.vercel.app"},
    )

    calls: list[tuple[str, str, str, str | None]] = []
    monkeypatch.setattr(
        check_vercel_alias,
        "assign_alias",
        lambda token, deployment_id, alias, team: calls.append((token, deployment_id, alias, team)),
    )

    result = check_vercel_alias.main(["--project", "snusmic-quant-terminal"])

    assert result == 2
    assert calls == []
    out = capsys.readouterr().out
    assert "STALE" in out
    assert "/v2/deployments/dpl_new/aliases" in out
    assert "DRY RUN" in out


def test_repair_requires_explicit_yes(monkeypatch, capsys):
    monkeypatch.setenv("VERCEL_TOKEN", "token")
    monkeypatch.setattr(
        check_vercel_alias,
        "get_alias",
        lambda token, alias, project, team: {"deploymentId": "dpl_old"},
    )
    monkeypatch.setattr(
        check_vercel_alias,
        "latest_ready_production",
        lambda token, project, team: {"uid": "dpl_new", "url": "snusmic-new.vercel.app"},
    )
    monkeypatch.setattr(
        check_vercel_alias,
        "assign_alias",
        lambda token, deployment_id, alias, team: (_ for _ in ()).throw(AssertionError("unexpected mutation")),
    )

    result = check_vercel_alias.main(["--project", "snusmic-quant-terminal", "--repair"])

    assert result == 2
    assert "without --yes" in capsys.readouterr().out


def test_repair_with_yes_assigns_latest_alias(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "token")
    monkeypatch.setattr(
        check_vercel_alias,
        "get_alias",
        lambda token, alias, project, team: None,
    )
    monkeypatch.setattr(
        check_vercel_alias,
        "latest_ready_production",
        lambda token, project, team: {"uid": "dpl_new", "url": "snusmic-new.vercel.app"},
    )
    calls: list[tuple[str, str, str, str | None]] = []

    def fake_assign(token: str, deployment_id: str, alias: str, team: str | None) -> dict[str, str | None]:
        calls.append((token, deployment_id, alias, team))
        return {"alias": alias, "oldDeploymentId": None}

    monkeypatch.setattr(check_vercel_alias, "assign_alias", fake_assign)

    result = check_vercel_alias.main(
        ["--project", "snusmic-quant-terminal", "--team", "team_1", "--repair", "--yes"]
    )

    assert result == 0
    assert calls == [("token", "dpl_new", "snusmic-quant-terminal.vercel.app", "team_1")]
