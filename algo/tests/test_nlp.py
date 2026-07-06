from algo.nlp import extract_keywords, tokenize


def test_tokenize_removes_stopwords():
    tokens = tokenize("这是一个关于交通事故的新闻")
    assert "的" not in tokens
    assert "交通事故" in tokens or "交通" in tokens


def test_extract_keywords_ranks_distinctive_terms_higher():
    corpus = [
        ["交通事故", "受伤", "救援", "现场"],
        ["交通事故", "受伤", "医院", "抢救"],
        ["经济数据", "增长", "报告"],
    ]
    keywords = extract_keywords(corpus, top_k=2)
    assert len(keywords) == 3
    top_terms_doc3 = {term for term, _ in keywords[2]}
    assert "经济数据" in top_terms_doc3 or "增长" in top_terms_doc3
