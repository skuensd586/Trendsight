"""Algo service client --- HTTP wrapper for the algorithm analysis module (module B).

Sends raw documents and comments to the Algo service for NLP analysis
(clustering, sentiment, keywords, lifecycle prediction, etc.).
Reads ALGO_BASE_URL from config.py.
"""

import httpx

from config import ALGO_BASE_URL


def call_algo(
    documents: list[dict],
    comments: list[dict] | None = None,
    sentiment_method: str = "bert",
) -> list[dict]:
    if comments is None:
        comments = []

    url = ALGO_BASE_URL.rstrip("/") + "/analyze"

    payload = {
        "documents": documents,
        "comments": comments,
        "sentiment_method": sentiment_method,
    }
    print("ALGO REQUEST URL:", url)
    print("ALGO REQUEST BODY:", payload)

    try:
        response = httpx.post(
            url,
            json=payload,
            timeout=120.0,
        )
    except httpx.RequestError as e:
        raise RuntimeError(f"Algo API request failed: {e}") from e

    if response.status_code != 200:
        raise RuntimeError(
            f"Algo API returned status {response.status_code}: {response.text}"
        )

    try:
        result = response.json()
    except ValueError as e:
        raise RuntimeError(f"Algo API returned invalid JSON: {e}") from e


    # Support both {"events": [...]} and [...] response formats
    if isinstance(result, dict):
        result = result.get("events", [])
    if not isinstance(result, list):
        raise RuntimeError(
            f"Algo API returned unexpected type: {type(result).__name__}"
        )

    return result
