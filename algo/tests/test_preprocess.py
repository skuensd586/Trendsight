from datetime import datetime

from algo.preprocess import hamming_distance, is_near_duplicate, normalize_document, simhash


def test_normalize_document_strips_boilerplate_and_parses_time():
    raw = {
        "doc_id": "1",
        "title": "<b>某地发生突发事件</b>",
        "content": "事件经过描述。责任编辑:张三 扫描二维码关注我们",
        "publish_time": "2026-01-02 10:00:00",
        "source": "新华社",
        "platform": "微博",
        "url": "https://example.com/1",
    }
    doc = normalize_document(raw)
    assert doc.title == "某地发生突发事件"
    assert "责任编辑" not in doc.content
    assert "扫描二维码" not in doc.content
    assert doc.publish_time == datetime(2026, 1, 2, 10, 0, 0)


def test_simhash_identical_text_is_a_near_duplicate_of_itself():
    fp = simhash("某地今日发生一起交通事故，事故造成多人受伤，现场救援人员迅速赶到")
    assert is_near_duplicate(fp, fp)


def test_simhash_edited_report_is_much_closer_than_unrelated_report():
    # SimHash needs enough shingles to be stable, so use paragraph-length text
    # rather than a short headline (real articles, not single sentences).
    a = simhash(
        "某地今日发生一起交通事故，事故造成多人受伤，现场救援人员迅速赶到，"
        "将伤者送往附近医院救治，目击者称事故发生时路面湿滑。"
    )
    b = simhash(
        "某地今日发生一起交通事故，事故造成多人受伤，现场救援人员迅速赶到，"
        "将伤者送往附近医院救治，据目击者称事故发生时路面较为湿滑。"
    )
    c = simhash(
        "国家统计局今日发布最新经济数据，显示第三季度国内生产总值同比增长，"
        "多个行业出现回暖迹象，专家表示这一趋势有望延续。"
    )
    assert hamming_distance(a, b) < hamming_distance(a, c) / 2
