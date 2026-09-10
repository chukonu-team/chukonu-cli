"""family 平行数组的成员表格渲染（规范 §6）。

核心不变量：null 必须占位输出。跳过 null 会让整列相对成员下标错位，
用户读到的就是错误的「某公开号属于某国别」。
"""
from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from chukonu_cli.commands.patent import (
    _family_length_warnings,
    _family_member_table,
    _member_row_count,
    _render,
)


def _hit(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "family_key": "60785350",
        "member_count": 3,
        # 中间成员缺申请号/标题：正是会导致错位的形态
        "application_numbers": ["CN-1-A", None, "US-1-B2"],
        "publication_numbers": ["CN-1-A", "EP-1-A1", "US-1-B2"],
        "countries": ["CN", "EP", "US"],
        "patent_types": ["A", "A1", "B2"],
        "patent_names": ["中文标题", None, "English title"],
    }
    payload.update(overrides)
    return payload


def _render_text(data: Any, width: int = 200) -> str:
    console = Console(record=True, width=width, force_terminal=False)
    console.print(_family_member_table(data) if isinstance(data, dict) and "family_key" in data else data)
    return console.export_text()


# ---------- 行数 ----------


def test_row_count_uses_member_count() -> None:
    assert _member_row_count(_hit()) == 3


def test_row_count_falls_back_to_longest_array() -> None:
    hit = _hit()
    hit.pop("member_count")
    assert _member_row_count(hit) == 3


def test_v2_singular_names_are_not_treated_as_member_arrays() -> None:
    """v2 单数名已撤销：若它们仍被当成平行数组，v3 载荷会渲染出零列表格。

    这是本次改名的回归防线——只给 v2 名字时，行数应退化为 0（认不出成员数组），
    而不是把 doc 级单数字段误当族成员铺开。
    """
    v2_only = {
        "family_key": "60785350",
        "family_size": 3,
        "publication_number": ["CN-1-A", "EP-1-A1", "US-1-B2"],
        "country": ["CN", "EP", "US"],
    }
    assert _member_row_count(v2_only) == 0
    assert _family_length_warnings(v2_only) == []


# ---------- null 占位（错位防线） ----------


def test_null_members_render_as_placeholder_rows() -> None:
    text = _render_text(_hit())
    lines = [ln for ln in text.splitlines() if "│" in ln]
    # 表头 + 3 个成员行
    body = [ln for ln in lines if ln.strip().startswith("│ 0")
            or ln.strip().startswith("│ 1")
            or ln.strip().startswith("│ 2")]
    assert len(body) == 3, text

    row1 = next(ln for ln in body if ln.strip().startswith("│ 1"))
    # 第 1 号成员申请号与标题为 null → 占位符，且该行的国别/类型仍对齐到 EP/A1
    assert "-" in row1
    assert "EP" in row1
    assert "A1" in row1
    assert "EP-1-A1" in row1


def test_every_member_index_is_rendered() -> None:
    text = _render_text(_hit())
    for pub in ("CN-1-A", "EP-1-A1", "US-1-B2"):
        assert pub in text


def test_row_count_equals_member_count_even_when_array_shorter() -> None:
    """数组比 member_count 短时仍按 member_count 出行，缺位补占位符（不静默少一行）。"""
    hit = _hit(member_count=4)
    text = _render_text(hit)
    body = [ln for ln in text.splitlines() if ln.strip().startswith("│ 3")]
    assert len(body) == 1, text


# ---------- 契约告警 ----------


def test_length_mismatch_is_reported() -> None:
    warns = _family_length_warnings(_hit(member_count=4))
    assert warns
    assert any("member_count 4" in w for w in warns)


def test_no_warning_when_lengths_match() -> None:
    assert _family_length_warnings(_hit()) == []


# ---------- _render 路由 ----------


def test_render_search_response_emits_member_table(capsys: Any) -> None:
    _render({"total": 1, "total_unit": "families", "results": [_hit()]})
    out = capsys.readouterr().out
    assert "family_key 60785350" in out
    assert "EP-1-A1" in out


def test_render_detail_response_emits_member_table(capsys: Any) -> None:
    _render(_hit())
    out = capsys.readouterr().out
    assert "family_key 60785350" in out


def test_render_document_hit_falls_back_to_json(capsys: Any) -> None:
    """文献级命中没有 family_key：保持原始 JSON dump 行为。"""
    _render({"total": 1, "results": [{"application_number": "CN-102187685-A"}]})
    out = capsys.readouterr().out
    assert "CN-102187685-A" in out
    assert "family_key" not in out


def test_render_keeps_non_member_fields_visible(capsys: Any) -> None:
    # latest_publication_date 是族级标量（v3 已删除 earliest_*），不进成员表格，须原样补出
    _render(_hit(latest_publication_date="2023-07-11", max_member_citation_count=12))
    out = capsys.readouterr().out
    assert "latest_publication_date" in out
    assert "2023-07-11" in out


def test_render_does_not_mutate_payload() -> None:
    """显示层不得改变 API 数组（规范 §6）。"""
    hit = _hit()
    before = json.dumps(hit, ensure_ascii=False, sort_keys=True)
    _render({"results": [hit]})
    assert json.dumps(hit, ensure_ascii=False, sort_keys=True) == before
