from pathlib import Path

import pytest

from algo.sentiment import ml_sentiment

_TOY_COMMENT_TEXTS = [
    "这次活动办得太好了，大家都很开心",
    "客服态度非常好，问题很快就解决了",
    "新功能用起来很顺手，点赞",
    "谢谢官方及时处理，效率很高",
    "终于等到更新了，超级满意",
    "服务态度很热情，下次还来",
    "这个方案我觉得很合理，认可",
    "老师讲得很清楚，收获很大",
    "客服小姐姐很耐心，赞",
    "商家很讲信誉，值得信赖",
    "客服态度太差了，一直在踢皮球",
    "这个功能改版之后难用死了",
    "等了三天都没有回复，太让人失望",
    "质量太差了，用两天就坏了",
    "物流慢到离谱，等得心烦",
    "售后一直推诿，根本不解决问题",
    "商家态度恶劣，以后不会再买了",
    "客服机器人根本听不懂人话",
    "这次体验糟糕透顶，浪费时间",
    "这服务态度真的让人心寒",
]
_TOY_COMMENT_LABELS = ["positive"] * 10 + ["negative"] * 10


@pytest.fixture(autouse=True)
def _reset_ml_sentiment_state():
    """ml_sentiment's model cache/warning-seen set are module-level globals; reset them
    around every test so one test's loaded model or fired warning can't leak into another."""
    ml_sentiment._model_cache.clear()
    ml_sentiment._warned_fallback_types.clear()
    yield
    ml_sentiment._model_cache.clear()
    ml_sentiment._warned_fallback_types.clear()


@pytest.fixture
def toy_comment_model_dir(tmp_path: Path) -> Path:
    """A real (tiny, not remotely accurate) trained comment model in an isolated tmp_path,
    for exercising predict_sentiment/get_model_status without touching the real models/ dir
    or depending on train_sentiment_model.py's CLI."""
    from scripts.train_sentiment_model import save_model, train_and_evaluate

    vectorizer, results = train_and_evaluate(
        _TOY_COMMENT_TEXTS, _TOY_COMMENT_LABELS, confidence_threshold=0.6, test_size=0.3, random_seed=0
    )
    best_name = max(results, key=lambda name: results[name]["accuracy"])
    save_model(vectorizer, results[best_name]["classifier"], "comment", tmp_path)
    return tmp_path
