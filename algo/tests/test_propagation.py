from datetime import datetime

from algo.propagation import detect_propagation
from algo.schema import Document


def _doc(doc_id, when, platform, vt, repost=0, like=0, comment=0, author="a"):
    return Document(
        doc_id=doc_id,
        title=f"帖子{doc_id}",
        content="正文内容用于测试",
        publish_time=datetime.fromisoformat(when),
        source=platform,
        platform=platform,
        url="",
        author=author,
        verification_type=vt,
        repost_count=repost,
        like_count=like,
        comment_count=comment,
    )


def _docs():
    return [
        _doc("p1", "2026-07-01 08:00", "知乎", "普通用户", author="爆料人"),          # earliest → 初始爆料
        _doc("p2", "2026-07-02 09:00", "微博", "头部认证个人", repost=100, like=500, author="大V"),  # first big-V
        _doc("p3", "2026-07-03 10:00", "新浪新闻", "官方平台", author="新浪"),         # first official
        _doc("p4", "2026-07-02 20:00", "微博", "普通用户", repost=2000, like=9000, comment=800, author="路人"),  # peak influence
    ]


def test_key_nodes_cover_expected_roles():
    prop = detect_propagation(_docs())
    roles = {n["role"]: n for n in prop["key_nodes"]}
    assert roles["初始爆料"]["author"] == "爆料人"
    assert roles["首次大V发声"]["author"] == "大V"
    assert roles["首次官方媒体介入"]["platform"] == "新浪新闻"
    assert roles["传播高峰"]["author"] == "路人"


def test_key_nodes_sorted_by_time():
    nodes = detect_propagation(_docs())["key_nodes"]
    times = [n["publish_time"] for n in nodes]
    assert times == sorted(times)


def test_top_influencers_ranked_and_engagement_only():
    prop = detect_propagation(_docs())
    infl = prop["top_influencers"]
    # ranked by influence descending; the zero-engagement posts are excluded
    assert infl[0]["author"] == "路人"
    assert all(x["influence"] > 0 for x in infl)
    assert [x["influence"] for x in infl] == sorted((x["influence"] for x in infl), reverse=True)


def test_platform_chain_ordered_by_first_appearance():
    prop = detect_propagation(_docs())
    order = [n["name"] for n in prop["platform_chain"]["nodes"]]
    assert order == ["知乎", "微博", "新浪新闻"]
    assert len(prop["platform_chain"]["links"]) == len(order) - 1


def test_empty_docs_safe():
    prop = detect_propagation([])
    assert prop == {"key_nodes": [], "top_influencers": [], "platform_chain": {"nodes": [], "links": []}}
