# Solace AI — Problem / Vision Document

> **Document type:** Problem / Vision (One-Pager)
> **Product:** Solace AI — Clinical-Evidence Research Assistant
> **Status:** Draft v1.0
> **Date:** 2026-06-21
> **Audience:** Founders, stakeholders, advisors, product & engineering leads

---

## 1. The One-Line Vision

> **Compress 2–6 weeks of manual Phase 1 biomedical literature review into a single query-to-document workflow that produces a fully-cited, evidence-graded deliverable a researcher can actually defend — not just a chat answer they have to re-verify by hand.**

---

## 2. The Problem

### 2.1 What is broken today

Biomedical researchers — PhD students, postgraduate (PG) researchers, and lab leads — begin nearly every new research question with **Phase 1 literature review**: the foundational survey of existing primary literature that grounds any new project, grant proposal, or thesis chapter.

Today this process is almost entirely **manual, low-leverage expert labour**:

1. Search PubMed with iteratively refined queries.
2. Read hundreds of abstracts (and many full papers).
3. Cross-reference claims across sources.
4. Judge evidence quality by hand (study design, sample size, replication).
5. Hand-synthesize findings into a defensible written document with citations.

This cycle takes **2–6 weeks per question** and is **repeated for almost every new project**. It is expert time spent on *retrieval and synthesis* rather than on *original research* — the exact opposite of where a researcher's comparative advantage lies.

### 2.2 Why it matters

- **Time cost:** Weeks of a highly-trained researcher's time, multiplied across every new question, every lab, every institution.
- **Quality risk:** Manual synthesis is inconsistent. Evidence grading is subjective and rarely documented. Contested findings get flattened or missed.
- **Defensibility gap:** Researchers must defend their synthesis to advisors, thesis committees, and co-authors. They need a **traceable, citation-grounded** chain from each claim back to its source — something hand-built reviews rarely preserve cleanly.
- **Repetition tax:** The same low-leverage workflow is re-run from scratch every time, with little reusable structure.

---

## 3. Who We Serve

### Primary users

| Segment | Role | Core need |
|---|---|---|
| **PhD students** | Building thesis chapters, qualifying surveys | Defensible, cited synthesis for committees |
| **PG researchers** | Scoping new projects, supporting grant writing | Fast, rigorous coverage of prior work |
| **Lab leads / PIs** | Reviewing directions, validating hypotheses | Trustworthy, auditable evidence summaries |

### Geographic & domain focus

- **Primary market:** Indian academia and the healthcare research industry (IITs, IISc, AIIMS, pharma R&D).
- **Domain:** Biomedical and life sciences — users who read primary literature as a **core part of their workflow**.

### Defining user trait

These users do not want a quick answer they then have to re-verify. They need **traceable, citation-grounded synthesis they can defend** — to advisors, committees, or co-authors. **Defensibility matters as much as the answer.**

---

## 4. Why Now

### 4.1 The technical inflection

LLM-based **retrieval-augmented generation (RAG)** — the technique of grounding a language model's output in retrieved source documents rather than its trained-in memory — has matured to the point where **multi-agent, multi-hop reasoning over scientific corpora** is feasible. ("Multi-hop" means chaining facts across steps, e.g. *gene → protein → pathway → disease → drug*, rather than answering from a single passage.)

### 4.2 The market gap

Existing tools optimize for the **wrong deliverable**:

| Tool | Optimized for | Gap |
|---|---|---|
| Consensus.app | Fast consensus Q&A | Chat answer, not a structured cited document |
| Elicit | Search + extraction | Limited evidence grading, no multi-hop biological reasoning |
| Perplexity | General conversational search | Not domain-rigorous; no per-claim provenance |
| Scite | Citation context | Citation signal, not a synthesized deliverable |

All of these are **chat-first or search-first**. None produce the **structured, fully-cited, evidence-graded deliverable** that academic and clinical research actually requires.

> **The gap is clear:** there is a chasm between *"chat with a paper"* tools and *the rigor of a real literature review*. Solace AI is built to fill exactly that chasm.

---

## 5. Our Approach (in Brief)

Solace AI takes an **open-ended biomedical research question** and returns a **structured evidence document** — not a chat transcript — produced by a **7-stage multi-agent pipeline** operating over PubMedQA, MedQuAD, and live PubMed (via the E-utilities API).

Three principles define the product:

1. **Every claim is cited** to its source text.
2. **Every claim is graded** for evidence strength (strong / moderate / weak / contested).
3. **The system abstains** — it explicitly says *"evidence is insufficient"* rather than fabricating citations or guessing.

---

## 6. What Success Looks Like

- A researcher submits one open-ended question and receives an **exportable, fully-cited literature review draft** (Markdown/PDF) with a structured evidence table.
- Every claim carries a **provenance trail** (which agent produced it, which prompt version, which retrieval pass) — auditable end-to-end.
- The output is something a researcher can **cite and defend**, not merely read.
- Weeks of manual review collapse into a **single query-to-document workflow**.

---

## 7. Non-Goals (for this scope)

- Not a chat interface — a **structured workbench**, not a conversation window.
- Not building a custom knowledge graph over ChEMBL/UniProt — **public KG + live extension only**.
- Not a persistent, growing shared knowledge graph — **stateless by design** per session.
- Not engineered against a hard latency/cost budget — **correctness is prioritized**; performance is measured and reported.
