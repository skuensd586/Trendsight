from pathlib import Path

import pytest

from algo.sentiment import ml_sentiment
from algo.sentiment.ml_sentiment import get_model_status, label_from_proba, predict_sentiment

_SAMPLE_TEXTS = {
    "positive": "客服态度非常好，问题很快就解决了",
    "negative": "这次体验糟糕透顶，浪费时间",
    "neutral": "今天天气多云",
}


@pytest.mark.parametrize("text_type", ["comment", "article"])
@pytest.mark.parametrize("expected_tone", ["positive", "negative", "neutral"])
def test_predict_sentiment_returns_a_valid_label_for_every_tone_and_text_type(
    toy_comment_model_dir, text_type, expected_tone
):
    # No article model exists yet, so text_type="article" exercises the fallback path;
    # either way the call must not raise and must return one of the three labels.
    ml_sentiment.MODEL_DIR = toy_comment_model_dir
    label = predict_sentiment(_SAMPLE_TEXTS[expected_tone], text_type=text_type)
    assert label in ("positive", "negative", "neutral")


def test_article_request_falls_back_to_comment_model_and_status_reflects_it(toy_comment_model_dir):
    ml_sentiment.MODEL_DIR = toy_comment_model_dir

    predict_sentiment("这是一段用于测试的文本", text_type="article")
    status = get_model_status()

    assert status["article"]["is_fallback"] is True
    assert status["article"]["loaded"] is True
    assert status["article"]["model_path"] == status["comment"]["model_path"]


def test_get_model_status_reports_not_loaded_before_any_request(toy_comment_model_dir):
    ml_sentiment.MODEL_DIR = toy_comment_model_dir
    status = get_model_status()
    # comment's model file exists on disk, so status can resolve its path without a full
    # load; it just shouldn't claim to have loaded it yet.
    assert status["comment"]["loaded"] is False
    assert status["comment"]["model_path"] is not None


def test_predict_sentiment_raises_clear_error_when_no_model_exists_at_all(tmp_path: Path):
    ml_sentiment.MODEL_DIR = tmp_path  # empty directory, nothing trained
    with pytest.raises(FileNotFoundError, match="no sentiment model found"):
        predict_sentiment("随便什么文本", text_type="comment")


def test_predict_sentiment_rejects_unsupported_text_type(toy_comment_model_dir):
    ml_sentiment.MODEL_DIR = toy_comment_model_dir
    with pytest.raises(ValueError, match="text_type"):
        predict_sentiment("文本", text_type="video")


def test_label_from_proba_neutral_when_both_below_threshold():
    assert label_from_proba({"positive": 0.55, "negative": 0.45}, confidence_threshold=0.6) == "neutral"


def test_label_from_proba_picks_the_higher_class_above_threshold():
    assert label_from_proba({"positive": 0.8, "negative": 0.2}, confidence_threshold=0.6) == "positive"
    assert label_from_proba({"positive": 0.1, "negative": 0.9}, confidence_threshold=0.6) == "negative"
