from algo.sentiment import classify_sentiment


def test_classify_sentiment_positive():
    label, score = classify_sentiment(["网友", "纷纷", "点赞", "支持", "此举"])
    assert label == "positive"
    assert score > 0


def test_classify_sentiment_negative():
    label, score = classify_sentiment(["公众", "谴责", "抗议", "此", "事故"])
    assert label == "negative"
    assert score < 0


def test_classify_sentiment_neutral_when_no_sentiment_words():
    label, score = classify_sentiment(["今天", "天气", "多云"])
    assert label == "neutral"
    assert score == 0.0
