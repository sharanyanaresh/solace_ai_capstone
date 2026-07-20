# Solace AI — Pitch Deck (Text Format)

> **Document type:** Pitch Deck (text content per slide — not a .pptx)
> **Product:** Solace AI — Clinical-Evidence Research Assistant
> **Status:** Draft v1.0
> **Date:** 2026-06-21
> **Audience:** Investors, evaluation committee, stakeholders

---

## Slide 1 — Title

**Solace AI**
*The Clinical-Evidence Research Assistant*

From an open-ended biomedical question to a fully-cited, evidence-graded literature review — in one workflow.

> Tagline: **Not a chat answer. A deliverable you can defend.**

---

## Slide 2 — The Problem

**Phase 1 literature review is weeks of wasted expert time.**

- Biomedical researchers — PhD students, PG researchers, lab leads — spend **2–6 weeks** manually reviewing literature for *every* new question.
- The cycle: search PubMed → read hundreds of abstracts → cross-reference → judge evidence quality → hand-synthesize.
- It's repeated for **every project, grant, and thesis chapter** — almost entirely manual.
- It's **expert time spent on retrieval and synthesis**, not original research.

> The people best at science spend weeks *not* doing science.

---

## Slide 3 — Why Existing Tools Don't Solve It

**Today's tools optimize for the wrong output.**

| Tool | Built for | Missing |
|---|---|---|
| Consensus.app | Fast consensus Q&A | Exportable cited deliverable |
| Elicit | Search + extraction | Evidence grading, multi-hop reasoning |
| Perplexity | General chat search | Domain rigor, provenance |
| Scite | Citation signal | Synthesized, graded document |

> There's a chasm between *"chat with a paper"* and *the rigor of a real literature review.* **We live in that chasm.**

---

## Slide 4 — Why Now

- **RAG has matured** enough for multi-agent, multi-hop reasoning over scientific corpora.
- Incumbents (Elicit, Consensus, Scite) have **proven willingness-to-pay** in this exact segment.
- The unmet need isn't *speed* — it's the **structured, fully-cited, evidence-graded deliverable** that academic and clinical research actually demands.

> The technology is ready. The market is paying. The gap is unfilled.

---

## Slide 5 — The Solution

**Solace AI turns one question into a structured evidence document.**

- Input: an open-ended biomedical research question.
- Output: a **structured evidence document** — not a chat transcript.
- Three guarantees:
  1. **Every claim is cited** to its source text.
  2. **Every claim is graded** — strong / moderate / weak / contested.
  3. **The system abstains** when evidence is thin — it never fabricates citations.

> Compress 2–6 weeks into a single query-to-document workflow.

---

## Slide 6 — How It Works

**A 7-stage multi-agent pipeline — every step auditable.**

```
Query
  → 1. Researcher      decompose + plan
  → 2. Retriever       hybrid corpus + live PubMed (degrades gracefully)
  → 3. Graph-Builder   multi-hop biology (gene→protein→pathway→disease→drug)
  → 3b. Corroborator   GATE: drop relations not backed by source text
  → 4. Fact-Checker    verify, grade, flag contested, abstain
  → 5. Synthesizer     evidence table + narrative (verified claims only)
  → 6. Editor          format, cite, attach provenance, export
Structured Evidence Document
```

> Tiered LLMs via the Groq API (Llama 3.1 8B + Llama 3.3 70B). Hosted on Render. No GPU to run.

---

## Slide 7 — What Makes Us Different

**The only tool combining all four:**

1. **Structured, exportable deliverable** — not a chat transcript.
2. **Explicit evidence grading** + contested-claim flagging.
3. **Multi-hop biological reasoning** via GraphRAG.
4. **Per-claim provenance / audit trail** — every claim traces back to agent, prompt version, retrieval pass, and source text.

> Purpose-built for biomedicine, where **defensibility matters as much as the answer.**

---

## Slide 8 — The Anti-Hallucination Moat

**We don't down-weight bad evidence. We drop it.**

- Live-extracted graph relations must pass a **Corroborator gate** against the actual source text.
- Uncorroborated relations **never enter the claim chain** — not weighted down, *dropped*.
- Thin evidence → **explicit abstention**, not a confident guess.
- Retrieval fails → **degrade to indexed corpus**, flagged transparently.

> Trust is the product. The architecture enforces it.

---

## Slide 9 — Market

**A validated, addressable niche — not a hypothesis.**

- **India alone:** tens of thousands of biomedical PhD/PG theses and papers annually — IITs, IISc, AIIMS, pharma R&D.
- Incumbents have already proven **willingness-to-pay** in this segment.
- Beachhead: **Indian biomedical academia and healthcare research**, expandable globally.

> The market already pays for worse. We give them defensible.

---

## Slide 10 — Users

| Persona | Need we serve |
|---|---|
| **PhD student** | Cited, gradeable synthesis to defend to a committee |
| **PG researcher** | Rigorous prior-work coverage under deadline |
| **Lab lead / PI** | Trustworthy, auditable evidence to commit resources |

> Everyone who reads primary literature as a core part of their work.

---

## Slide 11 — Traction & Validation Plan

- **Capstone deliverable:** deployed system, full documentation, 20-min video, individual viva.
- **Evaluation:** RAGAS (faithfulness, citation accuracy, relevancy, calibrated abstention) + **PubMedQA locked golden regression set** + LLM-as-judge for live queries.
- **Governance:** pinned model/prompt versions, per-claim provenance — reproducible by design.

> We measure quality the way scientists would demand.

---

## Slide 12 — Roadmap

| Phase | Focus |
|---|---|
| **Now (capstone, 5 sprints)** | Infra + KG → core pipeline → UI + eval → hardening + deploy |
| **Next** | Token-cost optimization (caching, parallelized extraction) |
| **Then** | Persistent growing shared KG; custom KGs (ChEMBL/UniProt) |
| **Production** | User-facing corpus-bias transparency; broader corpora beyond PubMed |

> Known limitations are explicit scope decisions — and a clear product roadmap.

---

## Slide 13 — Honest Limitations (By Design)

- **Token cost** not engineered against a hard budget this version — measured, reported, optimized next (Groq keeps latency low).
- **PubMedQA** is regression-only; live queries judged via LLM-as-judge (documented gap).
- **Corpus bias** (publication/English/PubMed-only) documented internally — a deliberate scope boundary, a production-roadmap item.

> We tell you what we don't yet do. That *is* the value proposition.

---

## Slide 14 — The Ask / Vision

**Give every biomedical researcher weeks of their life back.**

- Replace 2–6 weeks of manual review with a single, defensible workflow.
- Make **traceable, citation-grounded synthesis** the default, not the exception.
- Build the evidence layer that biomedical research can actually cite.

> **Solace AI — evidence you can defend, not just read.**

---

> **Next**: Reply "continue" to generate the next document.
