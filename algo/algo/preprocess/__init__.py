from .clean import normalize_document
from .dedup import simhash, hamming_distance, is_near_duplicate

__all__ = ["normalize_document", "simhash", "hamming_distance", "is_near_duplicate"]
