# Solace AI — Clarification & Design-Rationale Document

> **Document type:** Decision Log / Design Rationale ("why" behind every choice)
> **Product:** Solace AI — Clinical-Evidence Research Assistant
> **Status:** Draft v1.0
> **Date:** 2026-06-21
> **Audience:** Architects, engineers, reviewers, viva panel, future maintainers
> **Purpose:** Every other document states *what* and *how*. This document states **why** — for each technology, pattern, metric, requirement, and constraint: why it was chosen, what alternatives existed, why they were rejected, and how the choice concretely helps Solace AI.

---

## How to read this document

Each decision uses a consistent frame so it can be audited and challenged:

- **Decision** — what was chosen.
- **Why** — the reasoning in our specific context.
- **Alternatives considered** — the real competitors for the slot.
- **Why not them** — the disqualifying trade-off.
- **How it helps here** — the concrete benefit to *this* product (defensible, cited, graded biomedical evidence on Render + Groq, with no GPU).

A recurring theme: **Solace AI's product is trust, not speed.** Almost every decision below is biased toward *defensibility, traceability, and correctness* over latency, cost, or convenience. Where a choice looks "heavier" than necessary, that bias is usually the reason.

---

# Part I — Foundational Product Decisions

These are the decisions that everything else inherits. If these are wrong, no amount of good engineering saves the product.

## 1.1 Structured deliverable, not a chat answer

- **Decision:** Output a structured, exportable evidence document (table + narrative + citations + provenance), not a conversational chat reply.
- **Why:** Our users — PhD students, PG researchers, lab leads — must *defend* their literature review to advisors, committees, and co-authors. A chat transcript is ephemeral, hard to cite, and mixes reasoning with answer. A structured document is the actual artifact their workflow already requires.
- **Alternatives considered:** (a) Chat interface like Perplexity/Consensus; (b) a hybrid chat-with-export-button.
- **Why not them:** Chat-first design optimizes for *fast reassurance*, not *auditable rigor*. The moment the deliverable is a transcript, evidence grading and per-claim provenance become bolt-ons rather than the spine of the product. The hybrid still trains users to treat the answer as conversational and the export as secondary.
- **How it helps here:** It forces every downstream decision (evidence table schema, provenance store, grading, abstention) to serve a *citable artifact*. It is also the single clearest differentiator versus every incumbent.

## 1.2 Domain focus: biomedical / clinical, Indian academia first

- **Decision:** Narrow to biomedical/life-sciences literature review, beachhead in Indian academia (IITs, IISc, AIIMS, pharma R&D).
- **Why:** Biomedicine is the domain where (a) evidence grading and contested-claim handling are *culturally required* (clinicians already think in evidence levels), (b) public structured knowledge exists (PubMed, MedQuAD, Hetionet/PrimeKG), and (c) defensibility has real stakes. The Indian-academia beachhead is a validated, reachable segment with proven willingness-to-pay (Elicit/Consensus/Scite already monetize it).
- **Alternatives considered:** General-purpose research assistant across all academic fields; or legal/financial evidence synthesis.
- **Why not them:** General-purpose dilutes every advantage — no shared KG, no evidence-grading convention, no focused corpus. Legal/financial lack the rich public biomedical KG and open corpora that make GraphRAG and grounded retrieval tractable on a student budget.
- **How it helps here:** A narrow domain makes retrieval, the knowledge graph, and evaluation *all* tractable and high-quality. Depth beats breadth when the product's value is trust.

## 1.3 Open-ended query scope (no fixed taxonomy)

- **Decision:** Accept any open-ended biomedical question rather than a fixed menu of question types.
- **Why:** Real Phase 1 review questions are unbounded ("Does metformin reduce cancer incidence in T2DM?", "What pathways link APOE4 to Alzheimer's?"). A fixed taxonomy would feel like a form, not a research tool, and would fail exactly when researchers need it for novel questions.
- **Alternatives considered:** Templated question types (drug-efficacy, gene-disease, etc.) with structured slots.
- **Why not them:** Templates are easier to engineer and evaluate but cap the product's usefulness at the boundary of the template set — and research lives at that boundary.
- **How it helps here:** It's a harder bar (and we openly document the strain it puts on retrieval/graph coverage), but it's the only scope that matches the actual job-to-be-done. The graceful-degradation design (Part III) exists *because* of this choice.

## 1.4 Calibrated abstention ("evidence is insufficient")

- **Decision:** The system explicitly abstains or hedges when evidence is thin, instead of producing a confident-sounding answer.
- **Why:** In biomedicine, a fabricated or over-confident claim is worse than "I don't know." A researcher who is told "insufficient evidence" can act on it; one who is given a hallucinated citation is actively harmed and loses trust permanently.
- **Alternatives considered:** Always answer with a confidence score; or answer and let the user judge.
- **Why not them:** A confidence score still emits a claim and a citation, which the user may copy; the harm is already done. Calibrated abstention removes the claim entirely when support is inadequate.
- **How it helps here:** Abstention is a *feature*, not a failure mode — it's the behavior that makes the output defensible. It also gives us a crisp, measurable quality axis (calibrated abstention) that incumbents don't advertise.

## 1.5 Per-claim provenance / audit trail

- **Decision:** Every claim carries provenance: which agent produced it, which prompt version, which model, which retrieval pass, and the supporting source snippet.
- **Why:** Defensibility is not just "there's a citation" — it's "I can reconstruct exactly how this claim was produced." This supports the user (defending to a committee), the developer (debugging a bad claim), and evaluation (replaying a run).
- **Alternatives considered:** Document-level citations only; or no provenance.
- **Why not them:** Document-level citation can't answer "which agent/prompt produced this specific sentence and from which passage?" — which is exactly what fails an audit.
- **How it helps here:** It turns the system from a black box into an auditable pipeline, and it's what makes pinned-version reproducibility (Part VII) meaningful.

---

# Part II — Architecture & Orchestration

## 2.1 Multi-agent pipeline vs a single LLM call

- **Decision:** Decompose the work into specialized agents (Researcher, Retriever, Graph-Builder, Corroborator, Fact-Checker, Synthesizer, Editor) rather than one big prompt.
- **Why:** Each stage has a different objective, a different failure mode, and a different ideal model size. Separating them lets us (a) route the cheap small Groq model to extraction/reranking and the large Groq model to reasoning, (b) checkpoint and replay each stage, (c) attach provenance at each boundary, and (d) evaluate each stage independently with RAGAS.
- **Alternatives considered:** (a) One large prompt doing retrieve-reason-write; (b) a generic ReAct agent looping with tools.
- **Why not them:** A monolithic prompt is impossible to audit (you can't say which step hallucinated) and impossible to cost-tier. A free-form ReAct loop is non-deterministic in path and token cost, and its trajectory is hard to evaluate or reproduce — fatal for a product whose value is reproducible defensibility.
- **How it helps here:** Specialization + explicit stage boundaries is what makes provenance, tiered model serving, graceful degradation, and stage-level evaluation all *possible*. The architecture is shaped by the product promise.

## 2.2 Why these specific 7 stages (and why a separate Corroborator)

- **Decision:** The exact pipeline is Researcher → Retriever → Graph-Builder → **Corroborator** → Fact-Checker → Synthesizer → Editor.
- **Why each stage exists:**
  - **Researcher** — decomposition is necessary because open-ended questions are multi-part; retrieving against the raw question retrieves mush.
  - **Retriever** — grounding in real sources is the whole point of RAG; without it the model answers from memory.
  - **Graph-Builder** — enables multi-hop reasoning (gene→protein→pathway→disease→drug) that flat retrieval can't do, since the connecting facts live in *different* documents.
  - **Corroborator** — see below; this is the anti-hallucination keystone.
  - **Fact-Checker** — grading and abstention need a dedicated reasoning pass distinct from synthesis, so a claim is judged *before* it's written up.
  - **Synthesizer** — composes only from verified claims, keeping unverified material out of prose.
  - **Editor** — formatting, citation consistency, provenance attachment, export — a separate concern from reasoning.
- **Why the Corroborator is its own stage (drop, not down-weight):** The biggest risk in live graph extraction is the LLM inventing a relation that the source text never stated. If we merely *down-weighted* shaky relations, they could still leak into the claim chain. A dedicated gate that **drops** any relation not literally supported by source text guarantees uncorroborated facts never reach the user.
- **Alternatives considered:** Fold corroboration into the Fact-Checker; or weight relations by extraction confidence.
- **Why not them:** Folding it in mixes "is this relation real?" with "how strong is the evidence?" — two different questions, and the first must be answered first. Confidence-weighting is a soft filter; for a trust product we want a hard gate.
- **How it helps here:** It converts "GraphRAG might hallucinate" from a fatal risk into a controlled one, and it's a concrete, demonstrable safety mechanism for the viva.

## 2.3 LangGraph for orchestration

- **Decision:** Orchestrate with LangGraph.
- **Why:** LangGraph models the pipeline as an explicit stateful graph with typed state, checkpointing, and conditional edges — which maps one-to-one onto our needs: structured state passed between stages, checkpoint-and-resume on failure, and conditional branches (degrade to indexed corpus, fall back to flat RAG).
- **Alternatives considered:** Plain LangChain chains; CrewAI; AutoGen; a hand-rolled orchestrator.
- **Why not them:**
  - *LangChain (classic chains)* — linear, weak at conditional branching and checkpointed state; we'd fight it for our degradation paths.
  - *CrewAI / AutoGen* — oriented toward conversational, role-playing autonomous agents; their strength (emergent multi-agent dialogue) is our anti-goal (non-deterministic trajectories, hard to audit).
  - *Hand-rolled* — we'd reinvent state management, checkpointing, and tracing with more bugs and less tooling.
- **How it helps here:** Explicit graph + checkpoint state directly enables NFR-4 (graceful degradation), FR-16 (no upstream re-runs on downstream failure), and per-stage provenance/eval boundaries.

## 2.4 FastAPI for the backend

- **Decision:** Python + FastAPI.
- **Why:** The entire ML/RAG ecosystem (LangGraph, the Groq SDK, RAGAS, DSPy, vector-DB SDKs) is Python-first, so the backend should be Python to avoid a language boundary. FastAPI adds async I/O (critical when stages wait on the Groq API and the PubMed API), automatic OpenAPI docs, and Pydantic models that double as our structured-state contracts.
- **Alternatives considered:** Flask; Django; a Node/TypeScript backend.
- **Why not them:** Flask is sync-first and lacks built-in schema validation; Django is heavyweight for an API-only service; Node would force the ML work into a separate Python service and a cross-process hop for no benefit.
- **How it helps here:** Pydantic-validated request/response and pipeline state (LLD) come for free, and async lets a single instance hold many in-flight queries that are mostly waiting on Groq/PubMed.

## 2.5 React + Tailwind for the workbench

- **Decision:** React + Tailwind, built as a structured workbench (query input → evidence table → export panel), not a chat window.
- **Why:** The UI must *reinforce* that the output is a document, not a conversation. React gives us a component model for the evidence table, provenance drill-downs, and export panel; Tailwind gives fast, consistent styling without a design system overhead.
- **Alternatives considered:** Streamlit/Gradio (fast ML demo UIs); Vue/Svelte.
- **Why not them:** Streamlit/Gradio are excellent for demos but steer hard toward chat/notebook layouts and are awkward for a polished, stateful workbench with tables and drill-downs. Vue/Svelte are fine but React has the deepest ecosystem and team familiarity, lowering risk on a 5-sprint timeline.
- **How it helps here:** The workbench layout operationalizes NFR-12 (usability: a document, not a chat) at the UI layer.

---

# Part III — Models & Serving

## 3.1 Managed inference via the Groq API (not self-hosted)

- **Decision:** Use the **Groq API** for all LLM inference rather than self-hosting open weights on our own GPUs.
- **Why:** A 3-person, 5-sprint capstone should not spend its time provisioning GPUs, serving weights, and chasing quota. Groq is a managed, OpenAI-compatible inference API whose LPU hardware delivers very high tokens/sec at low latency, with a usable free tier plus pay-as-you-go. It removes the single biggest infra risk (GPU availability/cost) entirely, while still giving us strong open models (Llama 3.x, and others) and the ability to pin model IDs per run.
- **Alternatives considered:** Self-hosting Qwen2.5/Llama on our own GPUs (via vLLM); paid frontier APIs (GPT-4-class, Claude); other inference APIs (Together, Fireworks, OpenRouter).
- **Why not them:**
  - *Self-hosting on GPU* — was the prior plan; it forces GPU provisioning, quota, and ops that a managed API eliminates. Re-introducing it would trade the product's actual differentiator (defensibility) for infra work.
  - *Paid frontier APIs* — strong, but cost more per token and are closed; Groq runs open models we can name/pin and is cheaper for this workload.
  - *Other inference APIs* — viable substitutes; Groq is chosen for its latency/throughput and free tier. The pipeline is provider-agnostic behind `GroqModelClient`, so this is a swappable decision.
- **How it helps here:** Zero GPU ops + low latency + low, predictable per-token cost — directly serving BO3, BR-3/BR-4, NFR-8, and NFR-10. The trade is a third-party data path (NFR-11), acceptable because the corpus is public literature (no PHI).

## 3.2 Two model tiers on Groq (small fast model + large reasoning model)

- **Decision:** **Llama 3.1 8B Instant** (Groq) for retrieval reranking and entity/relation extraction; **Llama 3.3 70B Versatile** (Groq) for corroboration, fact-checking, synthesis, and editing. Model IDs are pinned per evaluated run and swappable for other Groq-hosted models (e.g. Qwen, Gemma, DeepSeek-distill).
- **Why:** Reranking and extraction are high-volume, lower-reasoning tasks where the 8B model is adequate and cheaper/faster; corroboration/fact-checking/synthesis are high-stakes reasoning tasks where the 70B model's quality is worth the extra tokens. Routing the cheap stages to the small model keeps token cost and rate-limit pressure down.
- **Alternatives considered:** Single large model everywhere; single small model everywhere.
- **Why not them:** Large-everywhere wastes tokens and rate-limit budget on stages that don't need it; small-everywhere risks faithfulness on exactly the stages where defensibility is decided.
- **How it helps here:** Tiering controls per-token cost and stays within Groq rate limits (NFR-9) without compromising reasoning-critical stages — and because Groq is fast, even the large tier is low-latency.

## 3.3 Resilience: retry + small-model fallback (no serving stack to run)

- **Decision:** Wrap Groq calls in exponential-backoff retries; on sustained failure, fall back to the small Groq model for that stage and flag the run.
- **Why:** With a managed API there is no serving stack to operate — the failure modes shift from "GPU saturated" to "API rate-limited / 5xx / timeout." The right defense is client-side: retry transient errors, and degrade to the small model rather than fail the run.
- **Alternatives considered:** No retry (fail fast); queue-and-wait only; self-hosting a fallback model.
- **Why not them:** Fail-fast is hostile under normal rate-limit bursts; a self-hosted fallback re-introduces exactly the GPU ops we removed.
- **How it helps here:** Keeps the pipeline resilient to Groq hiccups (NFR-9/NFR-4) with zero infrastructure, and the fallback event is captured in provenance/logs for transparency.

---

# Part IV — Retrieval

## 4.1 Retrieval-Augmented Generation at all

- **Decision:** Ground every claim in retrieved sources (RAG), never in the model's parametric memory.
- **Why:** Parametric "knowledge" is unciteable and prone to hallucination; the product *requires* citations. RAG makes every claim traceable to a real passage.
- **Alternatives considered:** Fine-tuning the model on biomedical text and answering from weights; long-context "dump all papers in the prompt."
- **Why not them:** Fine-tuning still produces unciteable, stale, hallucination-prone output and is costly to update. Long-context dumping is expensive, hits context limits, and provides no principled retrieval/grading.
- **How it helps here:** RAG is the precondition for FR-12 (link each claim to its source) and the whole grading/abstention apparatus.

## 4.2 Hybrid dense + sparse retrieval

- **Decision:** Combine dense (embedding) and sparse (keyword/BM25-style) retrieval with rank fusion.
- **Why:** Biomedical queries mix conceptual similarity (where dense wins) with exact technical tokens — gene symbols, drug names, identifiers (where sparse/lexical wins, because an embedding may blur "IL-6" vs "IL-10"). Hybrid recovers both.
- **Alternatives considered:** Pure dense; pure sparse/BM25.
- **Why not them:** Pure dense misses exact-token matches that matter intensely in biomedicine; pure sparse misses paraphrase and conceptual matches.
- **How it helps here:** Higher retrieval recall directly raises grounding quality (NFR-1 faithfulness) — and faithfulness is gated on having the right passage in front of the model.

## 4.3 Vector DB: Qdrant / Weaviate

- **Decision:** Use a dedicated vector DB (Qdrant or Weaviate) for the indexed corpus.
- **Why:** We need hybrid (dense+sparse) search, metadata filtering, and horizontal scaling over a large biomedical corpus, with a production-grade, self-hostable engine (no managed-service fee).
- **Alternatives considered:** `pgvector` in our existing PostgreSQL; FAISS; Pinecone; Milvus.
- **Why not them:**
  - *pgvector* — attractive (one fewer system), but its hybrid-search and large-scale ANN ergonomics lag dedicated engines; we'd outgrow it.
  - *FAISS* — a library, not a service: no metadata filtering, persistence, or hybrid search out of the box; we'd build a DB around it.
  - *Pinecone* — managed and paid; conflicts with the no-extra-cost, self-hosted-on-Render posture.
  - *Milvus* — capable but heavier to operate than Qdrant/Weaviate for a 3-person team.
- **How it helps here:** Self-hostable hybrid search with metadata filters fits both the budget (no SaaS fee, runs as a Render private service) and the retrieval-quality need.

## 4.4 Corpora: PubMedQA + MedQuAD, plus live PubMed (E-utilities)

- **Decision:** Index PubMedQA and MedQuAD; query live PubMed via the E-utilities API.
- **Why:** PubMedQA gives us biomedical QA grounded in abstracts *with known answers* — invaluable as both a corpus and a locked evaluation set. MedQuAD adds curated medical Q&A breadth. Live PubMed via E-utilities provides coverage beyond the indexed snapshot for novel/open-ended questions (which our open scope demands), and E-utilities is the official, free, programmatic NCBI interface.
- **Alternatives considered:** Scraping PubMed/Google Scholar; commercial literature APIs (Semantic Scholar bulk, Scopus); indexing all of PubMed ourselves.
- **Why not them:** Scraping is brittle and against terms; commercial APIs cost money or have restrictive licensing; indexing all of PubMed is infeasible on a student budget and unnecessary when E-utilities serves live coverage on demand.
- **How it helps here:** The combination gives us a *stable, evaluable base* (indexed) plus *fresh, open-ended reach* (live) — and the same PubMedQA doubles as our golden set, which is a deliberate efficiency.

---

# Part V — Knowledge Graph Layer

## 5.1 GraphRAG (multi-hop) on top of flat RAG

- **Decision:** Add a knowledge-graph reasoning layer for multi-hop questions.
- **Why:** Many biomedical questions require *chaining* facts that live in different papers — gene → protein → pathway → disease → drug. Flat retrieval returns passages independently and can't traverse these links; a graph can.
- **Alternatives considered:** Flat vector RAG only; iterative multi-query retrieval ("retrieve, read, retrieve again").
- **Why not them:** Flat RAG can't reliably assemble a chain whose links are never co-located in one passage. Iterative retrieval helps but is unstructured, costly in LLM calls, and hard to audit compared to an explicit graph traversal.
- **How it helps here:** It's a genuine capability differentiator (incumbents are largely flat) and it directly serves the kind of mechanistic questions biomedical researchers actually ask. Crucially, we keep flat RAG as the *fallback* (Part VI), so graph is upside, not a single point of failure.

## 5.2 Public KG base: Hetionet / PrimeKG

- **Decision:** Use a public biomedical KG (Hetionet or PrimeKG) as the base schema, extended live per query.
- **Why:** Building a biomedical KG from scratch is a multi-year effort; Hetionet/PrimeKG already encode curated gene/disease/drug/pathway relations with provenance. We get a high-quality backbone for free and extend only where coverage is missing.
- **Alternatives considered:** Build a custom KG over ChEMBL/UniProt; no base KG (extract everything live).
- **Why not them:** Custom KG construction is explicitly out of scope (infeasible in 5 sprints). Extracting *everything* live would be slow, costly, and far more hallucination-prone than starting from a curated base.
- **How it helps here:** The base KG covers the common cases reliably; live extension (gated by the Corroborator) handles the long tail. It's the pragmatic 80/20 for a capstone budget.

## 5.3 Stateless per-session graph (no persistence)

- **Decision:** Live-extracted relations are used within a query session and then discarded — nothing persists across sessions.
- **Why:** A persistent, growing, auto-extended KG would accumulate unverified, possibly-hallucinated relations over time and create a data-governance burden (who curates it? how is bad data removed?). Statelessness keeps the system simple, auditable, and free of cross-session contamination.
- **Alternatives considered:** A persistent shared KG that grows with every query.
- **Why not them:** A self-growing KG is a quality and governance liability at capstone scope — one bad extraction could poison future queries. The value (faster repeated queries) is a *post-capstone optimization*, not a core need.
- **How it helps here:** Statelessness is a deliberate scope boundary that buys governance simplicity (NFR-11) and removes a whole class of "where did this stale relation come from?" failures.

## 5.4 Neo4j vs in-memory NetworkX for the session graph

- **Decision:** Allow either Neo4j or in-memory NetworkX for per-session graph work.
- **Why:** Because the graph is small and stateless (one session's worth), an in-memory NetworkX graph is often sufficient and avoids running another service. Neo4j is available if traversal complexity or graph size warrants a real graph engine with Cypher.
- **Alternatives considered:** Mandating Neo4j always; mandating in-memory always.
- **Why not them:** Mandating Neo4j adds an always-on service (and Render cost) for graphs that may be tiny. Mandating in-memory would cap us if a session graph grows or needs rich traversal.
- **How it helps here:** It keeps the common case cheap (NetworkX, no extra infra — important on a free/low-cost Render budget) while leaving a scale path open.

---

# Part VI — Reliability & Graceful Degradation

## 6.1 Degrade to indexed corpus when live PubMed fails

- **Decision:** On PubMed API failure/rate-limit, fall back to the indexed corpus and flag "live retrieval unavailable."
- **Why:** PubMed is an external dependency we don't control. A research tool that simply errors when PubMed rate-limits is unusable. Degrading to the indexed corpus keeps the system answering, and the explicit flag preserves honesty about reduced coverage.
- **Alternatives considered:** Hard-fail the query; silently use indexed only.
- **Why not them:** Hard-fail is hostile to the user. Silent fallback is *dishonest* — the user would think they got full live coverage when they didn't, undermining defensibility.
- **How it helps here:** Availability without deception — the flag is itself a form of provenance, telling the user exactly what the result is based on.

## 6.2 Fall back to flat RAG when graph extraction/corroboration fails

- **Decision:** If graph coverage is missing and live extraction can't be corroborated, answer that sub-question with flat vector RAG (no multi-hop).
- **Why:** Multi-hop is upside, not a hard requirement for every question. When the graph can't safely help, degrading to grounded flat RAG still produces a cited, gradeable answer.
- **Alternatives considered:** Abstain whenever graph fails; force graph reasoning anyway.
- **Why not them:** Abstaining on every graph miss would make the system uselessly silent on the open-ended questions that are its whole point. Forcing graph reasoning on uncorroborated relations would reintroduce hallucination — the exact thing the Corroborator exists to prevent.
- **How it helps here:** It makes the ambitious open-ended scope (1.3) survivable: the system always has a safe grounded path to fall back to.

## 6.3 Checkpointed stage state

- **Decision:** Each stage's output is checkpointed in LangGraph so a downstream failure doesn't re-run upstream stages.
- **Why:** Upstream stages (retrieval, extraction) are the expensive ones (Groq tokens, external API). Re-running them because the Editor crashed would waste Groq tokens and PubMed rate limit.
- **Alternatives considered:** Re-run the whole pipeline on any failure.
- **Why not them:** Full re-runs multiply token cost and latency and burn the PubMed rate budget — unnecessary waste under per-token/rate-limit constraints.
- **How it helps here:** Directly protects the budget (and the PubMed quota) and enables fast iteration during development.

---

# Part VII — Evaluation, Observability, Governance

This is where a "demo" becomes a "defensible system." Each evaluation choice answers: *how do we know it's working, and how do we prove it?*

## 7.1 RAGAS as the core evaluation framework

- **Decision:** Use RAGAS for automated, reference-light evaluation of the RAG pipeline.
- **Why:** RAGAS is purpose-built to score RAG systems on exactly the axes we care about — faithfulness, citation/context accuracy, answer relevancy — without needing a full human-labeled gold answer for every query. That fits our open-ended scope, where gold answers don't exist for most live queries.
- **Alternatives considered:** Pure human evaluation; BLEU/ROUGE-style overlap metrics; building a bespoke eval harness.
- **Why not them:** Human eval doesn't scale to per-sprint regression. BLEU/ROUGE measure surface overlap, not factual grounding — useless for "is this claim supported by the source?". A bespoke harness reinvents RAGAS with less rigor.
- **How it helps here:** RAGAS gives us a repeatable, per-sprint quality signal (NFR-1) that maps onto the product promise.

### 7.1.1 Why each RAGAS metric — and what it protects

- **Faithfulness** — *Are the claims actually supported by the retrieved text?* This is the anti-hallucination metric; it's the single most important number because the product's promise is "every claim is grounded." A drop here means the system is inventing.
- **Citation / context accuracy** — *Do the cited sources actually support the claim, and did we retrieve the right context?* Protects against "right answer, wrong citation," which in academia is as damaging as a wrong answer.
- **Answer relevancy** — *Did we answer the question asked?* Guards against the failure where the system retrieves and grounds well but drifts off-topic — common with aggressive decomposition.
- **Calibrated abstention** — *Do we abstain exactly when evidence is thin, and answer when it's sufficient?* This is our distinctive metric; it measures the behavior (1.4) that makes us defensible. Measured on PubMedQA known-answer cases where we can tell whether abstention was warranted.
- **How they combine:** Faithfulness + citation accuracy protect *each claim*; answer relevancy protects *the whole response*; calibrated abstention protects *the decision to speak at all*. Together they cover claim-level, response-level, and meta-level quality.

## 7.2 PubMedQA as a *locked* golden regression set

- **Decision:** Use PubMedQA strictly as a fixed regression set with known answers; never tune on it.
- **Why:** We need *one* stable, trustworthy ground-truth anchor to detect regressions sprint-over-sprint. Locking it (no tuning, no expansion) keeps it an honest held-out signal.
- **Alternatives considered:** Create our own human-labeled gold set; let the golden set evolve.
- **Why not them:** Creating new human labels is out of scope (no labeling budget/time) and risks bias. An evolving golden set silently moves the goalposts and hides regressions.
- **How it helps here:** It's the deployment gate (Ops §4) — "no regression on PubMedQA" is a hard release criterion (NFR-7), giving objective evidence of stability for the viva.

## 7.3 LLM-as-judge for live, open-ended queries

- **Decision:** Score live open-ended queries (which have no gold answer) with an LLM-as-judge, and explicitly document this as a limitation.
- **Why:** Our open scope means most real queries have no reference answer, so RAGAS-with-references and PubMedQA can't cover them. An LLM-as-judge gives a scalable proxy quality signal where no gold exists.
- **Alternatives considered:** Only evaluate on PubMedQA; human-judge every live query.
- **Why not them:** PubMedQA-only would leave the product's actual use case (open-ended) unevaluated — and we openly flag that PubMedQA doesn't generalize to live queries. Human-judging every live query doesn't scale.
- **How it helps here:** It honestly closes the evaluation gap that the open-ended scope creates, while we transparently note the judge's own limitations (a deliberate, documented trade-off).

## 7.4 DSPy for prompt/pipeline optimization

- **Decision:** Use DSPy to optimize prompts/pipeline, then pin the resulting prompt versions.
- **Why:** Hand-tuning prompts across seven agents is slow, subjective, and unreproducible. DSPy systematically optimizes prompts against our metrics and produces versioned artifacts we can pin.
- **Alternatives considered:** Manual prompt engineering; no systematic optimization.
- **Why not them:** Manual tuning doesn't scale to seven interacting agents and leaves no reproducible record of *why* a prompt is what it is.
- **How it helps here:** It turns prompt engineering into a measurable, versioned, reproducible step (feeding NFR-7), and its output (pinned prompt versions) plugs straight into governance.

## 7.5 Per-agent observability (mandatory, not optional)

- **Decision:** Trace latency, token cost, retrieval hit rate, and cache hit rate per agent stage.
- **Why:** With seven stages, an aggregate "the query was slow/wrong" tells you nothing. Per-stage tracing localizes problems (which stage hallucinated, which stage is slow, which stage burns tokens) and produces the cost numbers we promised to *measure and report*.
- **Alternatives considered:** Aggregate request-level logging only.
- **Why not them:** Aggregate logging can't attribute cost or failure to a stage — debugging and cost reporting both become guesswork in a deep pipeline.
- **How it helps here:** It's the data source for NFR-5/NFR-8, for the failure runbook (Ops §12), and for the post-hoc latency/cost report we committed to instead of a hard budget.

## 7.6 Pinned model + prompt versions (governance)

- **Decision:** Pin and record model IDs and prompt versions per evaluated/deployed run.
- **Why:** Reproducibility is meaningless if the model or prompts can drift between runs. Pinning makes a result replayable and a regression diagnosable ("which version changed?").
- **Alternatives considered:** Use "latest" models/prompts implicitly.
- **Why not them:** "Latest" makes every result a moving target — you can't reproduce a number or attribute a regression.
- **How it helps here:** It's the backbone of NFR-7 (reproducibility) and the rollback story (Ops §10) — you can always restore a known-good, recorded configuration.

---

# Part VIII — Data & Schema Decisions (LLD)

## 8.1 PostgreSQL as the system of record

- **Decision:** PostgreSQL for users, query history, exported documents, and provenance logs.
- **Why:** Our durable data is relational and integrity-critical (claims belong to documents, citations and provenance belong to claims). Postgres gives ACID guarantees, foreign keys, and constraints (e.g., unique citations) that *enforce* defensibility at the storage layer. It's also free, self-hostable, and available as managed Render PostgreSQL.
- **Alternatives considered:** A document store (MongoDB); SQLite.
- **Why not them:** A document store wouldn't enforce the referential integrity that our provenance/audit guarantees depend on. SQLite doesn't fit a concurrent, deployed, multi-user service.
- **How it helps here:** Constraints like the unique `(claim_id, source_type, source_ref)` citation key make "no duplicate/garbled citations" a *schema invariant*, not a hope (supports FR-12/FR-14).

## 8.2 Separate `provenance` and `stage_logs` tables

- **Decision:** Keep per-claim `provenance` distinct from per-stage `stage_logs`.
- **Why:** They answer different questions. `provenance` answers "how was *this claim* produced?" (user/audit facing). `stage_logs` answers "how did *this run's pipeline* behave?" (ops/eval facing — latency, tokens, hit rates). Conflating them would muddle an audit record with operational telemetry.
- **Alternatives considered:** One combined log table.
- **Why not them:** A combined table couples a durable audit artifact to high-volume operational metrics with different retention and access needs.
- **How it helps here:** Clean separation supports both the user-facing audit trail (NFR-6) and the ops observability (NFR-5) without compromise.

## 8.3 No table for the session graph

- **Decision:** The per-session graph has no backing table.
- **Why:** It's stateless by design (5.3) — persisting it would contradict the governance decision and create the very contamination risk we avoided.
- **How it helps here:** The absence is intentional and documented, so a future reader doesn't "fix" a missing table that was never meant to exist.

---

# Part IX — Hosting (Render) & Inference (Groq) Decisions

The binding real-world setup: **app/data hosted on Render**, **LLM inference via the Groq API**, **no GPU anywhere**.

## 9.1 Render as a single managed PaaS

- **Decision:** Host the frontend, backend, database, and vector store on **Render**.
- **Why:** Render gives a 3-person team managed Static Sites, Web Services, managed PostgreSQL, private services, persistent disks, and Git-based auto-deploy — on free/low-cost tiers — with almost no DevOps overhead. The whole stack is declared as code in `render.yaml`.
- **Alternatives considered:** Self-managed VMs; a Kubernetes platform; a hyperscaler (AWS/GCP/Azure).
- **Why not them:** All add operational surface (clusters, IAM, networking) that buys nothing at capstone scope. Render's PaaS model lets us ship the product, not operate infrastructure.
- **How it helps here:** Concrete, low-cost, low-ops deployment (BR-4, NFR-10) with a one-file Blueprint and built-in rollback to prior deploys.

## 9.2 Why managed inference removes the old dominant risk

- **Decision:** Put inference on **Groq** so there is **no GPU to provision** anywhere in the system.
- **Why:** The previous plan's dominant risk was GPU availability/cost (quota, drivers, serving). A managed inference API deletes that risk class outright: no weights to host, no quota to request, no serving stack to operate. What remains is ordinary third-party-API management.
- **Alternatives considered:** Keep self-hosting on a rented GPU; split inference across providers.
- **Why not them:** Renting a GPU re-introduces exactly the ops/cost we removed; multi-provider adds complexity we don't need (the client is provider-agnostic if we ever want it).
- **How it helps here:** The new "risks" — Groq rate limits, model deprecation, free-tier cold starts — are small, well-understood, and handled with backoff/fallback, model-ID pinning, and a paid instance for the demo window. A hidden blocker became a routine dependency.

## 9.3 Render service selections (one line each)

- **Static Site (frontend)** — CDN-served React build; no server to pay for.
- **Web Service (backend + LangGraph)** — runs the FastAPI app and pipeline; auto-deploys from GitHub; scales by instance type.
- **Background Worker (optional)** — for long multi-agent runs, keeps the web service responsive by offloading the pipeline to a worker + queue.
- **Groq API (inference)** — external managed service; no Render compute; configured by env var (`GROQ_API_KEY`, model IDs).
- **Render PostgreSQL** — managed Postgres with automated backups + PITR; the natural store for history/provenance.
- **Render Persistent Disk (exports)** — simple durable file storage for generated PDFs/Markdown (`documents.storage_uri`); external Cloudflare R2 if we outgrow it.
- **Render env groups / secret files** — keep `GROQ_API_KEY` and DB URL out of the repo (NFR-11).
- **Render logs + metrics** — captures our stdout structured traces without standing up a separate observability stack; optional external sink for richer dashboards.
- **GitHub → Render auto-deploy + GitHub Actions eval gate** — tests and the RAGAS/PubMedQA gate run in Actions; Render builds and deploys on green.

## 9.4 Correctness-first, with Groq keeping latency low

- **Decision:** Do not engineer against a hard latency budget; measure and report instead. Track **per-token Groq cost** rather than GPU-hour cost.
- **Why:** The product's value is trust, so sprint time goes to faithfulness/abstention, not micro-optimizing speed. With Groq, latency is already low, so it is no longer even a documented weakness — the reported metric of interest is token cost.
- **Alternatives considered:** Set and enforce latency/cost SLAs now.
- **Why not them:** A hard SLA would pressure us to cut reasoning passes or downshift models — directly harming the core promise.
- **How it helps here:** Effort stays aligned with the differentiator; the measured numbers (low latency, modest token cost) become an honest report plus a small post-capstone optimization backlog (caching, parallel extraction).

---

# Part IX-A — Authentication & Authorization (RBAC) Decisions

## 9A.1 JWT (stateless) for authentication

- **Decision:** Authenticate with **JWT** — a short-lived access token plus a revocable refresh token — rather than server-side session cookies.
- **Why:** The backend is a stateless Render web service that may scale to multiple instances and cold-start on the free tier; a stateless token avoids a shared server-side session store and works cleanly with the React SPA and a JSON API. The access token carries the role claim, so the common authz check needs no DB round-trip.
- **Alternatives considered:** Server-side sessions (cookie + session store); an external IdP/OAuth (Auth0, Clerk); API keys.
- **Why not them:** Sessions need a shared store (extra infra) and don't add value at this scale. A managed IdP is overkill for a 2-role capstone and adds a vendor. API keys don't model human users/roles well.
- **How it helps here:** Stateless, infra-light auth that fits Render + SPA, serving FR-19/FR-20 and NFR-14. The refresh-token table gives us revocation (logout, compromise) without making the access path stateful.

## 9A.2 RBAC with two roles + separation of duties (admin monitors, researcher queries)

- **Decision:** Role-Based Access Control with two roles — `researcher` and `admin` — enforced **server-side, deny-by-default**. **Admin is an oversight/management role, not a superset:** it can *read/monitor* all users' data and manage users + governance, but it **cannot submit research queries**. Querying is `researcher`-only.
- **Why:** The product has two distinct access shapes: a **doer** (researcher) who runs queries on their own work, and an **overseer** (admin) who monitors everyone and administers the system. This is classic **separation of duties** — the role that audits/oversees the system should not also generate the work it audits. It keeps ownership semantics clean (every run has exactly one researcher owner), keeps the audit trail trustworthy (admins can't quietly create-and-grade their own runs), and follows least privilege (admin gets monitoring power, not query power).
- **Alternatives considered:** Admin as a strict superset (can also query); ABAC / per-permission scopes; a single role with ad-hoc `if user.is_admin` checks; client-side gating only.
- **Why not them:** A superset-admin blurs duties and pollutes per-user ownership/audit (the original "admin has all powers" reading — the user explicitly narrowed it to *monitor, not query*). ABAC's flexibility is unused complexity for two roles (kept as a "could-have"). Ad-hoc checks scatter authz logic and invite bypass. Client-side gating is not security — it must be enforced on the server.
- **How it helps here:** A tiny, auditable policy surface (one matrix, `require_role("researcher")` on submit, `require_role("admin")` on management, `can_read` for monitoring) that satisfies FR-21/FR-22/FR-24 and NFR-15, and is trivially testable (QA TC-14–18, including admin→submit = 403).

## 9A.3 Role in JWT claim **and** ownership checks (not role alone)

- **Decision:** Read role from the JWT claim for fast authz, but **also** enforce per-resource access via `can_read` — a researcher may read only `resource.user_id == current_user.id`, while an admin may read **any** resource (monitoring); confirm `is_active`/role against the DB on sensitive paths.
- **Why:** Role alone answers "can this *kind* of user do this?" but not "is this *their* record?". A researcher must not read another researcher's query just because both are researchers; an admin, by contrast, is *meant* to read all (oversight). Ownership-vs-admin is the second axis.
- **Alternatives considered:** Role-only checks; DB lookup on every request.
- **Why not them:** Role-only leaks data across users. A DB lookup on every call is unnecessary for the cheap role check (the claim suffices) but *is* used where revocation matters (disabled users, refresh).
- **How it helps here:** Closes the cross-user data-leak hole (the most likely RBAC bug) — directly the TC-15 test — while keeping the hot path claim-based.

## 9A.4 Password hashing: argon2id (bcrypt acceptable)

- **Decision:** Store only salted **argon2id** hashes (bcrypt acceptable); never plaintext, never return a hash.
- **Why:** argon2id is the current OWASP-recommended memory-hard KDF, resistant to GPU/ASIC cracking; per-user salts defeat rainbow tables.
- **Alternatives considered:** bcrypt; plain SHA-256; storing reversible/encrypted passwords.
- **Why not them:** Fast hashes (SHA-256) are brute-forceable; reversible storage is a breach waiting to happen. bcrypt is fine and is our fallback.
- **How it helps here:** Satisfies FR-23/NFR-16 and contains the blast radius of a DB compromise.

---

# Part X — Why each Functional Requirement (FR)

For each FR: *why it exists* and *what breaks without it*.

| FR | Why it exists / what breaks without it |
|---|---|
| **FR-1** (workbench input) | The non-chat entry point is what frames the whole interaction as document-production, not conversation. Without it we drift into chat (violating 1.1). |
| **FR-2** (decompose) | Open-ended questions are multi-part; without decomposition, retrieval is unfocused and recall collapses. |
| **FR-3** (hybrid retrieval) | Grounding is the basis of every citation; without retrieval the system hallucinates from memory. |
| **FR-4** (degrade on retrieval failure) | PubMed is external and flaky; without a flagged fallback the product either errors or silently misleads. |
| **FR-5** (graph coverage + extraction) | Enables multi-hop answers that flat RAG can't assemble; without it, mechanistic questions get shallow answers. |
| **FR-6** (corroborate, drop) | The anti-hallucination keystone; without it, invented relations reach the user and defensibility dies. |
| **FR-7** (flat-RAG fallback) | Keeps open-ended scope survivable; without it, every graph miss becomes an abstention and the tool goes quiet. |
| **FR-8** (verify + grade) | Evidence grading is the academic convention users expect; without it, all claims look equally certain. |
| **FR-9** (abstain) | Prevents confident fabrication; without it, thin-evidence questions produce the most dangerous outputs. |
| **FR-10** (flag contested) | Science is often contested; flattening disagreement is a correctness failure, not a simplification. |
| **FR-11** (evidence table) | The structured deliverable itself; without it we've built a chatbot. |
| **FR-12** (link claim→source) | The literal definition of "citable"; without it claims are unverifiable. |
| **FR-13** (synthesize from verified only) | Stops unverified material leaking into prose; without it, the narrative can contradict the table. |
| **FR-14** (provenance) | Enables audit and debugging per claim; without it, a bad claim is untraceable. |
| **FR-15** (export MD/PDF) | The output must leave the tool and enter a thesis/grant; without export it's a dead end. |
| **FR-16** (checkpointing) | Protects Groq-token/PubMed budget on failure; without it, every crash re-burns expensive upstream work. |
| **FR-17** (persist history/provenance) | Makes runs reviewable and reproducible later; without it, there's no record. |
| **FR-18** (pin versions) | Makes results reproducible and regressions diagnosable; without it, nothing can be replayed. |
| **FR-19** (login → JWT) | The front door; without identity there is no per-user privacy or admin oversight. |
| **FR-20** (verify every request) | Authn is worthless if endpoints don't actually check the token; closes the "forgot to protect a route" hole. |
| **FR-21** (RBAC deny-by-default) | The core access rule; without deny-by-default, a missing check silently grants access. Encodes separation of duties (researcher queries, admin monitors). |
| **FR-22** (admin management) | Gives the admin its oversight powers — user/role management and governance — in one controlled surface. |
| **FR-23** (hash passwords) | Without it, a DB leak hands over every credential; non-negotiable security hygiene. |
| **FR-24** (admin can't query) | Enforces separation of duties; without it, the oversight role could generate and grade its own runs, polluting ownership and the audit trail. |

---

# Part XI — Why each Non-Functional Requirement (NFR)

For each NFR: *the quality it guarantees* and *how it's enforced here*.

| NFR | Quality guaranteed / how it's enforced |
|---|---|
| **NFR-1** (faithfulness/citation no-regression) | The core trust signal; enforced by per-sprint RAGAS + PubMedQA gate. |
| **NFR-2** (~0% hallucinated relations) | Defensibility of multi-hop claims; enforced by the FR-6 corroboration gate (drop, not weight). |
| **NFR-3** (calibrated abstention) | The "know when to stay silent" quality; enforced via PubMedQA known-answer calibration. |
| **NFR-4** (graceful degradation) | Availability under external failure; enforced by the two fallback paths + checkpointing. |
| **NFR-5** (per-agent observability) | Debuggability and token-cost attribution in a deep pipeline; enforced by structured per-stage traces → Render logs (+ `stage_logs`). |
| **NFR-6** (100% provenance completeness) | Auditability of every claim; enforced by the Editor attaching provenance before export. |
| **NFR-7** (reproducibility) | Trust in reported numbers; enforced by pinned model/prompt versions + locked golden set. |
| **NFR-8** (measure/report perf) | Honesty about latency/cost without distorting priorities; enforced by tracing + post-hoc reporting. |
| **NFR-9** (tiered + resilient inference) | Token-cost/rate-limit viability; enforced by small/large Groq routing plus backoff + small-model fallback. |
| **NFR-10** (Render + Groq) | Makes the deployment *actually runnable* on free/low-cost tiers with no GPU; enforced by Render hosting + Groq config. |
| **NFR-11** (security/privacy/statelessness) | Secret hygiene + governance simplicity; enforced by Render secrets + discarding the session graph; third-party (Groq) data path disclosed (public corpus, no PHI). |
| **NFR-12** (usability: document not chat) | Preserves the product's identity; enforced by the workbench UI. |
| **NFR-13** (maintainability) | Testability of a 7-agent system; enforced by the shared BaseAgent + structured-state contract. |
| **NFR-14** (JWT authn) | Stateless identity that fits Render + SPA; enforced by signed short-lived access + revocable refresh tokens. |
| **NFR-15** (RBAC authz) | Prevents privilege escalation and cross-user leaks; enforced server-side, deny-by-default, role + ownership. |
| **NFR-16** (credential security) | Contains breach blast radius; enforced by argon2id hashing and secrets in Render env (never repo/logs). |

---

# Part XII — Why each Business Requirement (BR)

| BR | Why it's a *business* (not just product) requirement |
|---|---|
| **BR-1** (weeks→one workflow) | This time-saving *is* the value proposition and the basis of willingness-to-pay. |
| **BR-2** (defensible deliverables) | Defensibility is the differentiator that lets us charge more than chat-first incumbents. |
| **BR-3** (low-cost inference) | Required for viable unit economics at academic price points; Groq free tier + pay-as-you-go, metered per token. |
| **BR-4** (run on Render/Groq budget) | The project must be deliverable on free/low-cost tiers with no GPU — a hard business constraint, not a preference. |
| **BR-5** (reproducible/auditable) | Academic and evaluation scrutiny demand it; it's a market-entry requirement, not a nicety. |
| **BR-6** (demonstrable quality metrics) | Buyers and the viva panel need objective evidence, not claims. |
| **BR-7** (Indian-academia beachhead) | Focuses go-to-market on a validated, reachable, paying segment. |
| **BR-8** (transparent limitations) | In a trust market, documented honesty about limits is itself a credibility asset. |
| **BR-9** (access control) | Researchers' work is private and defensible only if isolated per user; admin oversight + governance control make the system operable and trustworthy for an institution. |

---

# Part XIII — Why each major Constraint / Assumption

| Constraint / assumption | Why we accept it (and what it buys us) |
|---|---|
| **Managed Groq inference (no self-hosting)** | Zero GPU ops + low, predictable per-token cost; buys simplicity and speed, at the cost of a third-party data path (public corpus, no PHI). |
| **PubMedQA = locked regression only** | Avoids the cost/bias of new labeling; buys an honest, stable quality anchor. |
| **Stateless graph** | Avoids KG-contamination and curation burden; buys governance simplicity. |
| **No custom ChEMBL/UniProt KG** | Out of scope for 5 sprints; buys focus, with public KG + live extension covering the need. |
| **Correctness over latency/cost** | Aligns scarce effort with the actual differentiator; buys a better core product, with perf as documented future work. |
| **Render + Groq** | The real stack; buys low-cost, low-ops deployment with no GPU, at the cost of third-party dependencies (rate limits, model lifecycle, free-tier cold starts). |
| **Corpus bias documented, not user-surfaced (this version)** | A scoped decision: building bias-surfacing UI is a project of its own; buys honesty (it's written down) without overpromising a feature we can't finish. |

---

# Part XIV — Decisions we deliberately deferred (and why that's a decision too)

- **No persistent shared KG** — deferred because its governance risk outweighs its (speed) benefit at capstone scope. Revisit when there's a curation process.
- **No hard latency/cost SLA** — deferred until correctness is proven; premature optimization would harm the core promise.
- **No user-facing corpus-bias disclosure** — deferred as a standalone production feature; documenting it now prevents it from looking like an oversight later.
- **No biomedical-specialized model (yet)** — deferred behind a metric: we'll switch a reasoning-critical agent to a different Groq-hosted (or domain) model *only if* RAGAS shows the general large model underperforming. This keeps the decision evidence-driven rather than fashion-driven.

> Deferring explicitly, with a documented trigger for revisiting, is itself a design discipline: it keeps scope honest and gives future maintainers the *reason* a thing was left out — not just the fact that it was.

---

## Closing note

If there is one sentence to carry away: **almost every choice in Solace AI trades convenience, speed, or breadth for defensibility, traceability, and correctness — because in clinical-evidence research, an answer you cannot defend is worse than no answer at all.** Every "why not the lighter option?" in this document ultimately resolves to that principle.
