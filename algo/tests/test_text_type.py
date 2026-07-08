from algo.preprocess import normalize_document, resolve_text_type


def test_resolve_text_type_maps_known_platforms():
    assert resolve_text_type("微博") == "comment"
    assert resolve_text_type("新闻客户端") == "article"


def test_resolve_text_type_falls_back_to_auto_for_unknown_platform():
    assert resolve_text_type("某个从没见过的平台") == "auto"


def test_normalize_document_sets_text_type_from_platform():
    raw = {
        "doc_id": "1",
        "title": "t",
        "content": "c",
        "publish_time": "2026-01-01 00:00:00",
        "source": "s",
        "platform": "微博",
        "url": "u",
    }
    assert normalize_document(raw).text_type == "comment"


def test_normalize_document_defaults_to_auto_for_unmapped_platform():
    raw = {
        "doc_id": "1",
        "title": "t",
        "content": "c",
        "publish_time": "2026-01-01 00:00:00",
        "source": "s",
        "platform": "抖音",
        "url": "u",
    }
    assert normalize_document(raw).text_type == "auto"
