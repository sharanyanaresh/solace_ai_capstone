"""Query endpoints — submit (researcher-only, runs the pipeline), fetch, list, export."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import Citation, Claim, Provenance, Query, StageLog, User
from ..services.pipeline import run_pipeline

router = APIRouter(prefix="/api/v1/queries", tags=["queries"])


class QueryIn(BaseModel):
    query: str = Field(min_length=5, max_length=2000)


def _persist(db: Session, q: Query, result: dict) -> None:
    q.status = "completed"
    q.retrieval_mode = result.get("retrieval_mode", "hybrid")
    q.reasoning_mode = result.get("reasoning_mode", "graph")
    q.flags = result.get("flags", [])
    q.narrative_md = result.get("narrative_md", "")
    q.explanation_md = result.get("explanation_md", "")
    q.completed_at = datetime.now(timezone.utc)

    for c in result.get("claims", []):
        claim = Claim(
            query_id=q.id,
            claim_text=c["claim_text"],
            evidence_strength=c["evidence_strength"],
            consensus_label=c["consensus_label"],
            is_abstention=c["is_abstention"],
            order_idx=c["order_idx"],
        )
        db.add(claim)
        db.flush()
        for cit in c.get("citations", []):
            db.add(Citation(
                claim_id=claim.id, source_type=cit.get("source_type", "pubmed"),
                source_ref=cit["source_ref"], title=cit.get("title"),
                journal=cit.get("journal"), snippet=cit.get("snippet"),
                relevance=cit.get("relevance", 0), contested=cit.get("contested", False),
            ))
        p = c.get("provenance", {})
        db.add(Provenance(
            claim_id=claim.id, agent_id=p.get("agent_id", "fact_checker"),
            prompt_version=p.get("prompt_version", "v1"), model_id=p.get("model_id", ""),
            retrieval_pass=p.get("retrieval_pass", 1),
        ))
    for s in result.get("stage_logs", []):
        db.add(StageLog(
            query_id=q.id, stage_no=s.get("stage_no", ""), agent_id=s.get("agent_id", ""),
            model_id=s.get("model_id"), latency_ms=s.get("latency_ms", 0),
            tokens=s.get("tokens", 0), status=s.get("status", "ok"),
        ))
    db.commit()


def _payload(db: Session, q: Query) -> dict:
    claims = db.scalars(select(Claim).where(Claim.query_id == q.id).order_by(Claim.order_idx)).all()
    logs = db.scalars(select(StageLog).where(StageLog.query_id == q.id)).all()
    claims_out, cites_flat, seen = [], [], {}
    n_abstentions = 0
    for c in claims:
        if c.is_abstention:
            n_abstentions += 1
        cits = db.scalars(select(Citation).where(Citation.claim_id == c.id)).all()
        prov = db.scalar(select(Provenance).where(Provenance.claim_id == c.id))
        cit_list = [{
            "source_ref": ct.source_ref, "title": ct.title, "journal": ct.journal,
            "snippet": ct.snippet, "relevance": ct.relevance, "contested": ct.contested,
        } for ct in cits]
        claims_out.append({
            "claim_text": c.claim_text, "evidence_strength": c.evidence_strength,
            "consensus_label": c.consensus_label, "is_abstention": c.is_abstention,
            "citations": cit_list,
            "provenance": {
                "agent_id": prov.agent_id if prov else "", "prompt_version": prov.prompt_version if prov else "",
                "model_id": prov.model_id if prov else "", "retrieval_pass": prov.retrieval_pass if prov else 1,
            } if prov else None,
        })
        for ct in cits:
            if ct.source_ref not in seen:
                seen[ct.source_ref] = True
                cites_flat.append({
                    "source_ref": ct.source_ref, "title": ct.title, "journal": ct.journal,
                    "relevance": ct.relevance, "contested": ct.contested,
                    "confidence": c.evidence_strength,
                })
    papers = sum(1 for s in logs if s.agent_id == "retriever")
    return {
        "query_id": str(q.id), "question": q.raw_query, "status": q.status,
        "retrieval_mode": q.retrieval_mode, "reasoning_mode": q.reasoning_mode,
        "flags": q.flags or [], "narrative_md": q.narrative_md or "",
        "explanation_md": q.explanation_md or "", "created_at": q.created_at.isoformat(),
        "claims": claims_out, "citations": cites_flat, "stage_logs": [{
            "stage_no": s.stage_no, "agent_id": s.agent_id, "model_id": s.model_id,
            "latency_ms": s.latency_ms, "tokens": s.tokens, "status": s.status,
        } for s in logs],
        "summary": {
            "citations": len(cites_flat), "claims": len(claims_out) - n_abstentions,
            "abstentions": n_abstentions,
            "tokens": sum(s.tokens for s in logs),
            "total_ms": sum(s.latency_ms for s in logs),
        },
    }


@router.post("", status_code=201)
def submit_query(body: QueryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = Query(user_id=user.id, raw_query=body.query.strip(), status="running")
    db.add(q)
    db.commit()
    db.refresh(q)
    try:
        result = run_pipeline(q.raw_query)
    except Exception as exc:  # noqa: BLE001
        q.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Pipeline error: {exc}")
    _persist(db, q, result)
    db.refresh(q)
    return _payload(db, q)


@router.get("")
def list_queries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Query).where(Query.user_id == user.id).order_by(Query.created_at.desc()).limit(50)
    ).all()
    return [{"query_id": str(r.id), "question": r.raw_query, "status": r.status,
             "created_at": r.created_at.isoformat()} for r in rows]


def _owned(db: Session, query_id: str, user: User) -> Query:
    try:
        qid = uuid.UUID(query_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    q = db.get(Query, qid)
    if q is None or q.user_id != user.id:  # ownership: researchers see only their own
        raise HTTPException(status_code=404, detail="Not found")
    return q


@router.get("/{query_id}")
def get_query(query_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _payload(db, _owned(db, query_id, user))


@router.get("/{query_id}/export")
def export_query(query_id: str, format: str = QueryParam("md"),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = _owned(db, query_id, user)
    data = _payload(db, q)
    md = _to_markdown(data)
    if format == "pdf":
        return Response(content=_to_pdf(data), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="solace-{query_id[:8]}.pdf"'})
    return PlainTextResponse(md, headers={
        "Content-Disposition": f'attachment; filename="solace-{query_id[:8]}.md"'})


def _to_markdown(d: dict) -> str:
    lines = [f"# Solace AI — Evidence Review", "", f"**Question:** {d['question']}", "",
             f"_retrieval: {d['retrieval_mode']} · reasoning: {d['reasoning_mode']}_", "",
             "## Answer", "", d["narrative_md"], "", "## Detailed explanation", "",
             d["explanation_md"], "", "## Citations", ""]
    for i, c in enumerate(d["citations"], 1):
        star = " ★contested" if c["contested"] else ""
        lines.append(f"{i}. **{c['source_ref']}** — {c['title']} · {c['journal']} "
                     f"(confidence: {c['confidence']}, relevance {c['relevance']}%){star}")
    return "\n".join(lines)


def _to_pdf(d: dict) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    def cell(pdf, h, text):
        pdf.multi_cell(0, h, _latin1(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    cell(pdf, 8, "Solace AI - Evidence Review")
    pdf.set_font("Helvetica", "", 11)
    cell(pdf, 6, f"Question: {d['question']}")
    pdf.ln(2)
    for title, body in (("Answer", d["narrative_md"]), ("Detailed explanation", d["explanation_md"])):
        pdf.set_font("Helvetica", "B", 13)
        cell(pdf, 7, title)
        pdf.set_font("Helvetica", "", 10)
        cell(pdf, 5, body)
        pdf.ln(2)
    pdf.set_font("Helvetica", "B", 13)
    cell(pdf, 7, "Citations")
    pdf.set_font("Helvetica", "", 9)
    for i, c in enumerate(d["citations"], 1):
        cell(pdf, 5, f"{i}. {c['source_ref']} - {c['title']} ({c['journal']}) [{c['confidence']}, {c['relevance']}%]")
    return bytes(pdf.output())


def _latin1(text: str) -> str:
    return (text or "").encode("latin-1", "replace").decode("latin-1")
