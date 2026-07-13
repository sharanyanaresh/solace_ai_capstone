"""Live PubMed retrieval via NCBI E-utilities (no API key required).

ESearch -> PMIDs (relevance-sorted) -> EFetch -> abstracts.
Returns lightweight Passage dicts the pipeline can rerank and cite.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

import httpx

from ..config import settings

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class PubMedError(RuntimeError):
    """Raised when PubMed is unreachable/rate-limited so callers can degrade."""


@dataclass
class Passage:
    pmid: str
    title: str
    abstract: str
    journal: str
    year: str

    def to_dict(self) -> dict:
        return asdict(self)


def _base_params() -> dict:
    params = {"tool": "solace", "email": settings.ncbi_email}
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    return params


def _esearch(client: httpx.Client, query: str, retmax: int) -> list[str]:
    params = {
        **_base_params(),
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "relevance",
    }
    r = client.get(f"{EUTILS}/esearch.fcgi", params=params)
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def _efetch(client: httpx.Client, pmids: list[str]) -> list[Passage]:
    if not pmids:
        return []
    params = {
        **_base_params(),
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    r = client.get(f"{EUTILS}/efetch.fcgi", params=params)
    r.raise_for_status()
    return _parse_articles(r.text)


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _parse_articles(xml_text: str) -> list[Passage]:
    passages: list[Passage] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return passages
    for art in root.findall(".//PubmedArticle"):
        pmid = _text(art.find(".//PMID"))
        title = _text(art.find(".//ArticleTitle"))
        # abstract may have multiple labelled sections
        abstract_parts = []
        for ab in art.findall(".//Abstract/AbstractText"):
            label = ab.get("Label")
            txt = _text(ab)
            abstract_parts.append(f"{label}: {txt}" if label else txt)
        abstract = " ".join(p for p in abstract_parts if p).strip()
        journal = _text(art.find(".//Journal/Title"))
        year = _text(art.find(".//JournalIssue/PubDate/Year")) or _text(
            art.find(".//JournalIssue/PubDate/MedlineDate")
        )
        if title or abstract:
            passages.append(
                Passage(pmid=pmid, title=title, abstract=abstract, journal=journal, year=year)
            )
    return passages


def search_pubmed(query: str, retmax: int | None = None) -> list[Passage]:
    """Fetch relevance-ranked abstracts for a query. Raises PubMedError on failure."""
    retmax = retmax or settings.pubmed_retmax
    try:
        with httpx.Client(timeout=_TIMEOUT, headers={"User-Agent": "solace/0.1"}) as client:
            pmids = _esearch(client, query, retmax)
            return _efetch(client, pmids)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:  # network / rate limit / 5xx
        raise PubMedError(str(exc)) from exc


if __name__ == "__main__":  # manual smoke test:  python -m backend.app.services.pubmed
    res = search_pubmed("does metformin reduce cancer incidence in type 2 diabetes", retmax=3)
    print(f"{len(res)} passages")
    for p in res[:3]:
        print("-", p.pmid, "|", p.title[:80])
