"""Hybrid retrieval scoring over live PubMed results.

For the MVP this is BM25 (sparse) over the fetched abstracts, which reranks
PubMed's relevance ordering. The LLM-based semantic rerank is layered on in P3
(the Retriever agent). No vector DB / no embedding model is required, keeping
the service within Render's free-tier memory.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from .pubmed import Passage, PubMedError, search_pubmed

_WORD = re.compile(r"[a-z0-9]+")


def _tok(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def bm25_rank(query: str, passages: list[Passage], k: int) -> list[tuple[Passage, float]]:
    """Return top-k (passage, score) by BM25 over title+abstract."""
    if not passages:
        return []
    corpus = [_tok(f"{p.title} {p.abstract}") for p in passages]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tok(query))
    ranked = sorted(zip(passages, scores), key=lambda x: x[1], reverse=True)
    return ranked[:k]


def _rank_to_out(query: str, passages: list[Passage], k: int) -> list[dict]:
    out = []
    for p, score in bm25_rank(query, passages, k):
        d = p.to_dict()
        d["bm25"] = round(float(score), 3)
        out.append(d)
    return out


def retrieve(query: str, k: int = 8, retmax: int | None = None) -> dict:
    """Single-query fetch + BM25 rank. Returns {'passages', 'mode', 'flags'}."""
    flags: list[str] = []
    try:
        passages = search_pubmed(query, retmax=retmax)
        mode = "hybrid"
    except PubMedError:
        passages, mode = [], "degraded"
        flags.append("live_retrieval_unavailable")
    return {"passages": _rank_to_out(query, passages, k), "mode": mode, "flags": flags}


def retrieve_multi(main_query: str, sub_queries: list[str], k: int,
                   retmax: int, sub_retmax: int) -> dict:
    """Deeper retrieval: search the main question AND each sub-question, dedupe by PMID,
    then BM25-rank the union against the main question and keep the top-k.

    This widens coverage (the biggest lever for research depth) while relevance stays
    anchored to the original question. Degrades to whatever was reachable.
    """
    flags: list[str] = []
    by_pmid: dict[str, Passage] = {}
    ok = False
    searches = [(main_query, retmax)] + [(q, sub_retmax) for q in (sub_queries or [])]
    for q, rm in searches:
        try:
            for p in search_pubmed(q, retmax=rm):
                ok = True
                if p.pmid and p.pmid not in by_pmid:
                    by_pmid[p.pmid] = p
        except PubMedError:
            continue
    if not ok:
        flags.append("live_retrieval_unavailable")
        return {"passages": [], "mode": "degraded", "flags": flags}
    return {"passages": _rank_to_out(main_query, list(by_pmid.values()), k),
            "mode": "hybrid", "flags": flags}
