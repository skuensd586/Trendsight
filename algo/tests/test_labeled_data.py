from pathlib import Path

import pytest

from algo.sentiment.labeled_data import load_labeled_csv


def test_load_labeled_csv_normalizes_label_aliases(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("label,text\n1,好评\n0,差评\npos,不错\nneg,很差\n", encoding="utf-8")

    texts, labels = load_labeled_csv(path)

    assert labels == ["positive", "negative", "positive", "negative"]
    assert texts == ["好评", "差评", "不错", "很差"]


def test_load_labeled_csv_supports_tsv_by_extension(tmp_path: Path):
    path = tmp_path / "data.tsv"
    path.write_text("label\ttext\npositive\t好评\n", encoding="utf-8")

    texts, labels = load_labeled_csv(path)

    assert texts == ["好评"]
    assert labels == ["positive"]


def test_load_labeled_csv_rejects_unrecognized_label(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("label,text\nmaybe,不知道\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unrecognized label"):
        load_labeled_csv(path)


def test_load_labeled_csv_rejects_missing_columns(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_text("sentiment,body\n1,好评\n", encoding="utf-8")

    with pytest.raises(ValueError, match="'label' and 'text' columns"):
        load_labeled_csv(path)
