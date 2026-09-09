from chukonu_cli.client_core.search import (
    build_patent_advanced_body,
    build_patent_detail_path,
    build_patent_keyword_body,
)


def test_detail_path_defaults_to_lightweight_response() -> None:
    assert (
        build_patent_detail_path("60785350", dataset="epo_docdb_family")
        == "/patent/60785350?dataset=epo_docdb_family"
    )


def test_detail_path_can_request_claims_and_description() -> None:
    assert build_patent_detail_path(
        "60785350",
        dataset="epo_docdb_family",
        include_claims=True,
        include_description=True,
    ) == (
        "/patent/60785350?dataset=epo_docdb_family"
        "&include_claims=true&include_description=true"
    )


def test_detail_path_without_dataset_still_emits_flag_query() -> None:
    """dataset=None 但开 flag：query list 逻辑必须自己起 '?'，不能漏掉分隔符。"""
    assert (
        build_patent_detail_path("CN-102187685-A", include_claims=True)
        == "/patent/CN-102187685-A?include_claims=true"
    )
    assert build_patent_detail_path(
        "CN-102187685-A", include_claims=True, include_description=True
    ) == "/patent/CN-102187685-A?include_claims=true&include_description=true"


def test_detail_path_without_dataset_or_flags_has_no_query() -> None:
    assert build_patent_detail_path("CN-102187685-A") == "/patent/CN-102187685-A"


def test_keyword_body_only_sends_enabled_fulltext_flags() -> None:
    default_body = build_patent_keyword_body(query="battery")
    assert "include_claims" not in default_body
    assert "include_description" not in default_body
    body = build_patent_keyword_body(
        query="battery", include_claims=True, include_description=False
    )
    assert body["include_claims"] is True
    assert "include_description" not in body


def test_advanced_body_only_sends_enabled_fulltext_flags() -> None:
    body = build_patent_advanced_body(
        title="battery", include_claims=False, include_description=True
    )
    assert "include_claims" not in body
    assert body["include_description"] is True
