from algo.cluster import purity, single_pass_cluster
from algo.preprocess import normalize_document
from algo.sample_data import RAW_RECORDS


def test_single_pass_cluster_reaches_perfect_purity_against_labeled_events():
    docs = [normalize_document(raw) for raw in RAW_RECORDS]
    true_labels = [raw["event_id"] for raw in RAW_RECORDS]

    assignment = single_pass_cluster(docs)

    assert purity(assignment, true_labels) == 1.0
    # With single-character CJK tokens filtered, two events each split into
    # sub-clusters due to reduced vocabulary overlap:
    #   phone: "launch" vs "hands-on review" reports (vocabulary shift)
    #   flood: "scene news" vs "expert analysis" reports (different register)
    # This is expected — purity stays 1.0, cluster count is the meaningful bound.
    assert len(set(assignment)) <= 6


def test_purity_penalizes_cross_event_contamination():
    predicted = [0, 0, 0, 1, 1]
    true = ["a", "a", "b", "b", "b"]
    # cluster 0: majority "a" (2/3 correct), cluster 1: majority "b" (2/2 correct) -> 4/5
    assert purity(predicted, true) == 4 / 5


def test_purity_of_empty_input_is_zero():
    assert purity([], []) == 0.0
