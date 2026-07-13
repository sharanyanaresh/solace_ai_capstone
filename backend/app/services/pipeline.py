"""The 7-stage multi-agent pipeline (LangGraph), grounded in live PubMed + Groq.

Researcher -> Retriever -> Graph-Builder -> Corroborator -> Fact-Checker
           -> Synthesizer -> Editor -> structured evidence document.

Every stage logs latency + tokens. Claims carry provenance and citations.
Designed to *degrade* rather than fail: no sources -> abstention; graph gaps ->
flat RAG; Groq hiccups are handled inside the LLM client (key + model failover).
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..config import settings
from .llm import get_llm
from .retrieval import retrieve, retrieve_multi

PROMPT_VERSION = "v1"


class State(TypedDict, total=False):
    query: str
    sub_questions: list[str]
    entities: list[str]
    passages: list[dict]
    retrieval_mode: str
    reasoning_mode: str
    flags: list[str]
    relations: list[dict]
    claims: list[dict]
    abstentions: list[dict]
    overall: str
    narrative_md: str
    explanation_md: str
    factcheck_model: str
    final_claims: list[dict]
    stage_logs: list[dict]


def _log(state: State, no: str, agent: str, model: str | None, latency_ms: int, tokens: int, status: str):
    state.setdefault("stage_logs", []).append(
        {"stage_no": no, "agent_id": agent, "model_id": model,
         "latency_ms": latency_ms, "tokens": tokens, "status": status}
    )


def _fmt_passages(passages: list[dict], n: int, abs_chars: int) -> str:
    lines = []
    for p in passages[:n]:
        ab = (p.get("abstract") or "")[:abs_chars]
        lines.append(f"[PMID {p['pmid']}] {p.get('title','')} ({p.get('journal','')} {p.get('year','')})\n{ab}")
    return "\n\n".join(lines) if lines else "(no sources retrieved)"


# ---------------- stages ----------------

def researcher(state: State) -> State:
    llm = get_llm()
    q = state["query"]
    data, r = llm.complete_json(
        "You are a biomedical research planner. Decompose the question into 2-4 focused, "
        "answerable sub-questions and list key biomedical entities. Respond with valid JSON.",
        f'Question: "{q}"\nReturn JSON: {{"sub_questions": ["..."], "entities": ["..."]}}',
        tier="small", max_tokens=400,
    )
    subs = [str(s) for s in (data.get("sub_questions") or [])][:4] if isinstance(data, dict) else []
    ents = [str(e) for e in (data.get("entities") or [])][:12] if isinstance(data, dict) else []
    _log(state, "1", "researcher", r.model, r.latency_ms, r.tokens, "ok")
    return {"sub_questions": subs or [q], "entities": ents}


def retriever(state: State) -> State:
    import time
    t0 = time.perf_counter()
    subs = state.get("sub_questions") or []
    if settings.pipeline_multi_query and subs:
        res = retrieve_multi(state["query"], subs[:3], k=settings.pipeline_top_k,
                             retmax=settings.pubmed_retmax, sub_retmax=settings.pipeline_subquery_retmax)
        agent_model = f"pubmed+bm25 (multi-query x{1+min(len(subs),3)})"
    else:
        res = retrieve(state["query"], k=settings.pipeline_top_k, retmax=settings.pubmed_retmax)
        agent_model = "pubmed+bm25"
    ms = int((time.perf_counter() - t0) * 1000)
    status = "degraded" if res["mode"] == "degraded" else f"{len(res['passages'])} hits"
    _log(state, "2", "retriever", agent_model, ms, 0, status)
    return {"passages": res["passages"], "retrieval_mode": res["mode"], "flags": res["flags"]}


def graph_builder(state: State) -> State:
    passages = state.get("passages") or []
    if not passages:
        _log(state, "3", "graph_builder", None, 0, 0, "skipped (no sources)")
        return {"relations": []}
    llm = get_llm()
    data, r = llm.complete_json(
        "You extract biomedical relations that are EXPLICITLY stated in the given abstracts. "
        "Do not infer. Respond with valid JSON.",
        _fmt_passages(passages, 8, 800) +
        '\n\nReturn JSON: {"relations":[{"subject":"..","relation":"..","object":"..",'
        f'"pmid":"..","evidence":"short quote"}}]}}  Max {settings.graph_max_relations} relations, '
        'each pmid MUST be from above.',
        tier="small", max_tokens=1200,
    )
    rels = data.get("relations", []) if isinstance(data, dict) else []
    _log(state, "3", "graph_builder", r.model, r.latency_ms, r.tokens, f"{len(rels)} candidates")
    return {"relations": rels}


def corroborator(state: State) -> State:
    rels = state.get("relations") or []
    passages = {p["pmid"]: p for p in (state.get("passages") or [])}
    if not rels:
        _log(state, "3b", "corroborator", None, 0, 0, "skipped")
        return {"relations": [], "reasoning_mode": "flat_rag"}
    llm = get_llm()
    items = []
    for i, rel in enumerate(rels):
        ab = (passages.get(str(rel.get("pmid")), {}).get("abstract") or "")[:700]
        items.append(f'#{i} ({rel.get("subject")} -{rel.get("relation")}-> {rel.get("object")}) '
                     f'[PMID {rel.get("pmid")}] source: {ab}')
    data, r = llm.complete_json(
        "You verify whether each proposed relation is EXPLICITLY supported by its source abstract. "
        "Keep only supported ones. Respond with valid JSON.",
        "\n\n".join(items) + '\n\nReturn JSON: {"kept":[indices of supported relations]}',
        tier="large", max_tokens=300,
    )
    kept_idx = set(data.get("kept", [])) if isinstance(data, dict) else set()
    kept = [rels[i] for i in range(len(rels)) if i in kept_idx]
    dropped = len(rels) - len(kept)
    _log(state, "3b", "corroborator", r.model, r.latency_ms, r.tokens,
         f"ok · {dropped} dropped")
    return {"relations": kept, "reasoning_mode": "graph" if kept else "flat_rag"}


def fact_checker(state: State) -> State:
    passages = state.get("passages") or []
    if not passages:
        _log(state, "4", "fact_checker", None, 0, 0, "no sources")
        return {"claims": [], "abstentions": [{"topic": state["query"],
                "reason": "No sources were retrieved (live retrieval unavailable or no matches)."}],
                "overall": "low", "factcheck_model": None}
    llm = get_llm()
    rels = state.get("relations") or []
    rel_txt = "\n".join(f'- {x.get("subject")} -{x.get("relation")}-> {x.get("object")} [PMID {x.get("pmid")}]'
                        for x in rels) or "(none)"
    subs = "; ".join(state.get("sub_questions") or [])
    data, r = llm.complete_json(
        "You are a rigorous clinical-evidence fact-checker. Using ONLY the provided abstracts, "
        "produce a thorough set of claims that answer the question and its sub-questions. "
        "Each claim should be a substantive, self-contained finding — where the abstracts state them, "
        "include the specifics that matter: study design (RCT, cohort, meta-analysis), population, "
        "direction and size of effect, and any caveats. Grade each claim high/moderate/low on the "
        "strength of the underlying evidence. Mark consensus vs contested (contested = sources "
        "disagree). Cite supporting PMIDs from the provided set only. Prioritise PRECISION over "
        "quantity: only assert what an abstract supports; if evidence is thin or absent for a "
        "sub-question, ABSTAIN for it rather than fabricate. Respond with valid JSON.",
        f'QUESTION: "{state["query"]}"\nSUB-QUESTIONS: {subs}\n\n'
        f'CORROBORATED RELATIONS:\n{rel_txt}\n\nABSTRACTS:\n'
        f'{_fmt_passages(passages, settings.factcheck_passages, settings.factcheck_abstract_chars)}\n\n'
        'Return JSON: {"claims":[{"text":"a detailed 1-3 sentence finding with specifics",'
        '"evidence_strength":"high|moderate|low","consensus_label":"consensus|contested",'
        '"contested":false,"citations":["PMID",...]}],'
        '"abstentions":[{"topic":"..","reason":".."}],"overall":"high|moderate|low"}. '
        'Every claim MUST cite >=1 PMID from the abstracts above. Aim for 6-12 well-supported claims '
        'that cover the sub-questions (mechanism, efficacy, populations, contested points).',
        tier="large", max_tokens=settings.factcheck_max_tokens,
    )
    claims = data.get("claims", []) if isinstance(data, dict) else []
    absts = data.get("abstentions", []) if isinstance(data, dict) else []
    overall = (data.get("overall") if isinstance(data, dict) else None) or "moderate"
    _log(state, "4", "fact_checker", r.model, r.latency_ms, r.tokens,
         f"{len(claims)} claims · {len(absts)} abstentions")
    return {"claims": claims, "abstentions": absts, "overall": overall, "factcheck_model": r.model}


def synthesizer(state: State) -> State:
    claims = state.get("claims") or []
    if not claims:
        msg = ("## Evidence insufficient\n\nSolace could not find enough corroborated evidence in the "
               "retrieved literature to answer this question, so it abstains rather than guess.")
        _log(state, "5", "synthesizer", None, 0, 0, "abstained")
        return {"narrative_md": msg, "explanation_md": msg}
    llm = get_llm()
    import json as _json
    q = state.get("query", "")
    data, r = llm.complete_json(
        "You are a scientific writer producing a defensible literature-review deliverable. Using ONLY "
        "the given verified claims and their citations, write two Markdown fields. Introduce NO new "
        "facts and cite inline as [PMID xxxxx] wherever a statement rests on a source.\n"
        "1) narrative_md — a thorough ANSWER of 3-5 paragraphs that directly answers the question, "
        "states the overall strength of evidence, and notes contested points and gaps.\n"
        "2) explanation_md — a LONG, in-depth explanation (research-review depth) organised with "
        "these Markdown '##' sections: Overview; Mechanisms & background; Evidence by theme "
        "(use '###' sub-sections and, where useful, bullet lists of the key studies with their "
        "design/effect); Contested & uncertain; Limitations of the evidence base; Bottom line. "
        "Be expansive — this is a full literature-review section, not a short summary: expand each "
        "theme with the mechanism, the specific studies, the direction/size of effect, and caveats "
        "drawn from the claims. But every sentence must trace to the provided claims/citations — "
        "depth must not cost accuracy. Respond with valid JSON.",
        f'QUESTION: "{q}"\n\nVERIFIED CLAIMS (with citations):\n' + _json.dumps(claims)[:8000] +
        '\n\nReturn JSON: {"narrative_md":"..","explanation_md":".."}',
        tier="large", max_tokens=settings.synth_max_tokens,
    )
    nar = (data.get("narrative_md") if isinstance(data, dict) else "") or ""
    exp = (data.get("explanation_md") if isinstance(data, dict) else "") or nar
    _log(state, "5", "synthesizer", r.model, r.latency_ms, r.tokens, "ok")
    return {"narrative_md": nar, "explanation_md": exp}


def editor(state: State) -> State:
    """Non-LLM: assemble final claim objects with citations + provenance (no fabrication)."""
    passages = {p["pmid"]: p for p in (state.get("passages") or [])}
    # normalize bm25 -> relevance %
    bm = [p.get("bm25", 0.0) for p in passages.values()] or [1.0]
    top = max(bm) or 1.0
    model = state.get("factcheck_model") or settings.groq_model_large

    import re
    out_claims: list[dict] = []
    for i, c in enumerate(state.get("claims") or []):
        cits = []
        for pmid in c.get("citations", [])[:6]:
            pmid_key = re.sub(r"\D", "", str(pmid))  # normalize 'PMID 123' -> '123'
            p = passages.get(pmid_key)
            if not p:
                continue
            cits.append({
                "source_ref": f"PMID:{pmid_key}", "source_type": "pubmed",
                "title": p.get("title", ""), "journal": p.get("journal", ""),
                "snippet": (p.get("abstract", "") or "")[:280],
                "relevance": int(round(100 * (p.get("bm25", 0.0) / top))),
                "contested": bool(c.get("contested")),
            })
        out_claims.append({
            "claim_text": c.get("text", ""),
            "evidence_strength": _norm_strength(c.get("evidence_strength")),
            "consensus_label": "contested" if c.get("contested") else _norm_consensus(c.get("consensus_label")),
            "is_abstention": False,
            "order_idx": i,
            "citations": cits,
            "provenance": {"agent_id": "fact_checker", "prompt_version": PROMPT_VERSION,
                           "model_id": model, "retrieval_pass": 1},
        })
    # abstentions become flagged rows
    for j, a in enumerate(state.get("abstentions") or []):
        out_claims.append({
            "claim_text": f'Insufficient evidence — {a.get("topic","")}: {a.get("reason","")}'.strip(),
            "evidence_strength": "low", "consensus_label": "insufficient",
            "is_abstention": True, "order_idx": len(out_claims),
            "citations": [],
            "provenance": {"agent_id": "fact_checker", "prompt_version": PROMPT_VERSION,
                           "model_id": model, "retrieval_pass": 1},
        })
    _log(state, "6", "editor", None, 0, 0, "ok")
    return {"final_claims": out_claims}


def _norm_strength(s) -> str:
    s = (s or "").lower()
    return s if s in ("high", "moderate", "low") else ("high" if s in ("strong",) else "moderate")


def _norm_consensus(s) -> str:
    s = (s or "").lower()
    return s if s in ("consensus", "contested", "insufficient") else "consensus"


# ---------------- graph ----------------

def _build_graph():
    g = StateGraph(State)
    g.add_node("researcher", researcher)
    g.add_node("retriever", retriever)
    g.add_node("graph_builder", graph_builder)
    g.add_node("corroborator", corroborator)
    g.add_node("fact_checker", fact_checker)
    g.add_node("synthesizer", synthesizer)
    g.add_node("editor", editor)
    g.add_edge(START, "researcher")
    g.add_edge("researcher", "retriever")
    g.add_edge("retriever", "graph_builder")
    g.add_edge("graph_builder", "corroborator")
    g.add_edge("corroborator", "fact_checker")
    g.add_edge("fact_checker", "synthesizer")
    g.add_edge("synthesizer", "editor")
    g.add_edge("editor", END)
    return g.compile()


_graph = None


def run_pipeline(query: str) -> dict:
    """Run the full pipeline synchronously and return a structured result dict."""
    global _graph
    if _graph is None:
        _graph = _build_graph()
    state: State = {"query": query, "stage_logs": [], "flags": [], "reasoning_mode": "graph"}
    final = _graph.invoke(state)
    return {
        "retrieval_mode": final.get("retrieval_mode", "hybrid"),
        "reasoning_mode": final.get("reasoning_mode", "graph"),
        "flags": final.get("flags", []),
        "overall": final.get("overall", "moderate"),
        "claims": final.get("final_claims", []),
        "narrative_md": final.get("narrative_md", ""),
        "explanation_md": final.get("explanation_md", ""),
        "stage_logs": final.get("stage_logs", []),
    }
