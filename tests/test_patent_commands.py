"""patent 子命令的命令层测试。

builder 单测过不等于命令层拼对了：`patent get` 的最终路径是
`/patent/api` 前缀 + builder 的 `/patent/{key}`，双 patent 段很容易写错，
这里用 CliRunner + mock `_call` 直接断言最终 path。
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from chukonu_cli.commands import patent as patent_cmd
from chukonu_cli.main import app

runner = CliRunner()


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """截获 _call，避免命令层真的发请求。"""
    captured: list[dict[str, Any]] = []

    async def _fake_call(method: str, path: str, body: Any, json_out: bool) -> None:
        captured.append(
            {"method": method, "path": path, "body": body, "json_out": json_out}
        )

    monkeypatch.setattr(patent_cmd, "_call", _fake_call)
    return captured


# ---------- patent get：路径拼装 ----------


def test_get_builds_gateway_prefixed_detail_path(calls: list[dict[str, Any]]) -> None:
    result = runner.invoke(app, ["patent", "get", "CN-102187685-A"])
    assert result.exit_code == 0, result.output
    assert calls[0]["method"] == "GET"
    # `/patent/api` 网关前缀 + 后端 `/patent/{key}`：两段 patent 都必须在
    assert calls[0]["path"] == "/patent/api/patent/CN-102187685-A?dataset=epo_docdb"
    assert calls[0]["body"] is None


def test_get_family_key_with_flags(calls: list[dict[str, Any]]) -> None:
    result = runner.invoke(
        app,
        [
            "patent",
            "get",
            "60785350",
            "--dataset",
            "epo_docdb_family",
            "--include-claims",
            "--include-description",
        ],
    )
    assert result.exit_code == 0, result.output
    assert calls[0]["path"] == (
        "/patent/api/patent/60785350?dataset=epo_docdb_family"
        "&include_claims=true&include_description=true"
    )


def test_get_quotes_key_but_not_dataset(calls: list[dict[str, Any]]) -> None:
    runner.invoke(app, ["patent", "get", "US 15/637,265"])
    path = calls[0]["path"]
    assert "US%2015%2F637%2C265" in path
    # dataset 是 query 取值，不做路径段转义
    assert path.endswith("?dataset=epo_docdb")


def test_get_rejects_unknown_dataset_locally(calls: list[dict[str, Any]]) -> None:
    result = runner.invoke(app, ["patent", "get", "X", "--dataset", "google_patents"])
    assert result.exit_code != 0
    assert "google_patents" in result.output
    assert not calls  # 本地拒绝，不打后端


# ---------- keyword：--dataset ----------


def test_keyword_sends_dataset(calls: list[dict[str, Any]]) -> None:
    result = runner.invoke(
        app, ["patent", "keyword", "battery", "--dataset", "epo_docdb_family"]
    )
    assert result.exit_code == 0, result.output
    assert calls[0]["path"] == "/patent/api/search/keyword"
    assert calls[0]["body"]["dataset"] == "epo_docdb_family"


def test_keyword_defaults_to_document_dataset(calls: list[dict[str, Any]]) -> None:
    runner.invoke(app, ["patent", "keyword", "battery"])
    assert calls[0]["body"]["dataset"] == "epo_docdb"
    assert "include_claims" not in calls[0]["body"]


def test_keyword_rejects_unknown_dataset(calls: list[dict[str, Any]]) -> None:
    result = runner.invoke(app, ["patent", "keyword", "x", "--dataset", "nope"])
    assert result.exit_code != 0
    assert not calls


# ---------- advanced：CLI flag 覆盖 JSON body ----------


def _write_body(tmp_path: Any, payload: dict[str, Any]) -> str:
    p = tmp_path / "body.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return str(p)


def test_advanced_flags_override_json_body(
    calls: list[dict[str, Any]], tmp_path: Any
) -> None:
    body_file = _write_body(
        tmp_path, {"title": "battery", "dedup": "none", "include_claims": False}
    )
    result = runner.invoke(
        app,
        [
            "patent",
            "advanced",
            "--json-body",
            body_file,
            "--dedup",
            "family",
            "--include-claims",
            "--include-description",
        ],
    )
    assert result.exit_code == 0, result.output
    body = calls[0]["body"]
    assert body["dedup"] == "family"
    assert body["include_claims"] is True
    assert body["include_description"] is True
    assert body["title"] == "battery"  # 未覆盖的键原样保留


def test_advanced_keeps_json_body_when_flags_absent(
    calls: list[dict[str, Any]], tmp_path: Any
) -> None:
    body_file = _write_body(tmp_path, {"title": "battery", "include_claims": True})
    runner.invoke(app, ["patent", "advanced", "--json-body", body_file])
    assert calls[0]["body"]["include_claims"] is True
    assert "dedup" not in calls[0]["body"]


def test_advanced_dedup_auto_is_dropped_from_body(
    calls: list[dict[str, Any]], tmp_path: Any
) -> None:
    """auto 是后端默认：与 builder 一致，显式传 auto 也不进 body。"""
    body_file = _write_body(tmp_path, {"title": "battery", "dedup": "family"})
    runner.invoke(
        app, ["patent", "advanced", "--json-body", body_file, "--dedup", "auto"]
    )
    assert "dedup" not in calls[0]["body"]


def test_advanced_negative_flag_forces_false(
    calls: list[dict[str, Any]], tmp_path: Any
) -> None:
    body_file = _write_body(tmp_path, {"title": "battery", "include_claims": True})
    runner.invoke(
        app,
        ["patent", "advanced", "--json-body", body_file, "--no-include-claims"],
    )
    assert calls[0]["body"]["include_claims"] is False


def test_advanced_rejects_bad_dedup(calls: list[dict[str, Any]], tmp_path: Any) -> None:
    body_file = _write_body(tmp_path, {"title": "battery"})
    result = runner.invoke(
        app, ["patent", "advanced", "--json-body", body_file, "--dedup", "collapse"]
    )
    assert result.exit_code != 0
    assert not calls
