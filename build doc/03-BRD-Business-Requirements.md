# Solace AI — Business Requirements Document (BRD)

> **Document type:** Business Requirements Document
> **Product:** Solace AI — Clinical-Evidence Research Assistant
> **Status:** Draft v1.0
> **Date:** 2026-06-21
> **Audience:** Business stakeholders, sponsors, advisors, evaluation committee

---

## 1. Executive Summary

Solace AI addresses a concrete, repeated cost in biomedical research: the **2–6 weeks of expert time** consumed by manual Phase 1 literature review on every new question. By compressing this into a single query-to-document workflow that yields a **structured, fully-cited, evidence-graded deliverable**, Solace AI converts low-leverage retrieval-and-synthesis labour into high-leverage research time — in a market segment (academic literature tooling) that has already demonstrated willingness to pay.

---

## 2. Business Objectives

| # | Objective | Why it matters |
|---|---|---|
| BO1 | Reduce researcher time on Phase 1 review from weeks to a single workflow | Direct expert-time cost savings |
| BO2 | Produce defensible, auditable deliverables | Differentiates from chat-first tools; addresses the trust gap |
| BO3 | Demonstrate viable self-hosted (no paid-API) economics | Sustainable unit economics for an academic-priced product |
| BO4 | Establish a beachhead in Indian biomedical academia | Validated, addressable niche with WTP signal from incumbents |

---

## 2a. Business Requirements (BR)

Numbered business-level requirements that the solution must satisfy to meet the objectives above. (Distinct from the product/functional requirements in the PRD — these state *what the business needs*, not *how the product behaves*.)

| ID | Business requirement | Supports |
|---|---|---|
| **BR-1** | Cut Phase 1 literature-review turnaround from 2–6 weeks to a single query-to-document workflow. | BO1 |
| **BR-2** | Every deliverable must be defensible: per-claim citation, evidence grade, and audit trail. | BO2 |
| **BR-3** | The solution must operate without paid frontier-LLM API spend (self-hosted models). | BO3 |
| **BR-4** | The solution must run within the available cloud budget — an **Azure Student subscription** plus any institutional/Educator credits — with a documented upgrade path for GPU-bound inference. | BO3 |
| **BR-5** | The solution must be reproducible and auditable (pinned model/prompt versions, persisted provenance) to satisfy academic and evaluation scrutiny. | BO2 |
| **BR-6** | Quality must be demonstrable via objective metrics (RAGAS) and a locked regression set (PubMedQA) with no regression across sprints. | BO2, BO4 |
| **BR-7** | Initial go-to-market must target Indian biomedical academia (IITs, IISc, AIIMS, pharma R&D) as a validated beachhead. | BO4 |
| **BR-8** | Known limitations (latency/cost, corpus bias, generalization) must be transparently documented for stakeholders. | BO2 |

---

## 3. Stakeholders

| Stakeholder | Interest | Influence |
|---|---|---|
| Biomedical researchers (end users) | Faster, defensible reviews | High (adoption) |
| Lab leads / PIs | Trustworthy team output | High (buying decision) |
| Academic institutions (IITs, IISc, AIIMS) | Research throughput, cost | Medium–High |
| Pharma R&D teams | Evidence rigor, audit trail | Medium |
| Capstone evaluation committee | Engineering & business rigor | High (assessment) |
| Cloud/credit providers | Sustained GPU usage | Medium (resource) |

---

## 4. Business Context & Market

### 4.1 Market size (rough estimate)

- **India** alone produces **tens of thousands** of biomedical PhD/PG theses and papers annually across IITs, IISc, AIIMS, and pharma R&D institutions.
- The global academic literature-review tooling market (Elicit, Consensus, Scite) has shown **clear willingness-to-pay in this exact user segment** — indicating a **validated, addressable niche**, not a hypothetical one.

### 4.2 Competitive landscape

| Competitor | Positioning | Limitation vs. Solace |
|---|---|---|
| Consensus.app | Fast consensus Q&A | Chat answer, not exportable cited deliverable |
| Elicit | Search + extraction | Limited grading; no multi-hop biological reasoning |
| Perplexity | General conversational search | Not domain-rigorous; no per-claim provenance |
| Scite | Citation context signal | Not a synthesized, graded deliverable |

### 4.3 Unique value proposition

Solace AI is the **only** positioning in this set that combines:

1. A **structured, exportable deliverable** (not a chat transcript).
2. **Explicit evidence grading** and contested-claim flagging.
3. **Multi-hop biological entity reasoning** via GraphRAG.
4. A **verifiable per-claim provenance/audit trail**.

Purpose-built for biomedical questions where **defensibility matters as much as the answer**.

---

## 5. Business Value & KPIs

### 5.1 Value drivers

| Driver | Mechanism | Business outcome |
|---|---|---|
| **Cost savings** | Weeks → single workflow | Expert hours redeployed to original research |
| **Quality/defensibility** | Grading + provenance | Lower rework; committee/co-author trust |
| **Differentiation** | Structured deliverable + audit trail | Pricing power vs. chat-first incumbents |
| **Sustainable economics** | Self-hosted Qwen2.5 (no paid API) | Viable at academic price points |

### 5.2 Business KPIs

| KPI | Definition | Baseline | Target direction |
|---|---|---|---|
| Time-to-review | Wall-clock from question to defensible draft | 2–6 weeks (manual) | Single workflow session |
| Cost per review | GPU + infra cost per query | Measured post-hoc | Optimize post-capstone |
| Deliverable defensibility | % claims with citation + grade + provenance | — | 100% |
| Faithfulness / citation accuracy | RAGAS metrics | Tracked per sprint | Trend ↑ |
| Adoption (post-capstone) | Active researchers / institutions | 0 | Beachhead growth |

---

## 6. Compliance, Governance & Risk

### 6.1 Governance requirements

- **Pinned model + prompt versions** per evaluated run (reproducibility).
- **Per-claim provenance metadata persisted** alongside every output (auditability).
- **Stateless graph design** — no persistent cross-session data store for the GraphRAG layer (data-governance simplicity).

### 6.2 Known limitations documented as business risk

- **Corpus bias** (publication bias, English-language bias, PubMed-only coverage) is **documented internally and in the capstone writeup** as a known limitation — a deliberate scope decision, not an oversight, and a natural production-roadmap extension. **Not surfaced in the exported document in this version.**

### 6.3 Business risks & mitigations

| Risk | Business impact | Mitigation |
|---|---|---|
| Open-ended scope strains retrieval/graph coverage | Lower output quality | Graceful degradation to flat vector RAG |
| Self-hosted models underperform paid frontier APIs on fact-checking precision | Trust erosion | Track RAGAS per sprint; escalate 7B→32B on reasoning-critical agents |
| Live graph extraction adds latency/cost | Higher cost per review | No hard budget this capstone; documented as post-capstone optimization (caching, parallelization) |
| PubMedQA doesn't generalize to live open-ended queries | Misleading quality signal | PubMedQA = regression-only; live via LLM-as-judge with documented limitation |
| Graph-Builder hallucinates relations | Defensibility failure | Dedicated Corroborator gate drops uncorroborated relations |
| Corpus bias shapes findings unseen | Reputational / scientific risk | Documented as known limitation; production-roadmap item |
| **Azure Student subscription lacks GPU quota / sufficient credit for 32B inference** | Could block the core pipeline | Upgrade to Pay-As-You-Go + GPU quota request; use Spot VMs; lean on institutional/Educator credits; fall back to 4-bit quantized 32B on a single mid-tier GPU (see HLD §7.5, Ops §2) |

---

## 7. Success Criteria (Business)

The initiative is successful (capstone scope) when:

1. A deployed system produces structured, cited, graded, exportable deliverables from open-ended queries.
2. Every claim carries complete provenance and governance metadata.
3. RAGAS metrics and PubMedQA regression demonstrate no quality regression across sprints.
4. Self-hosted economics are demonstrated (no paid-API dependency).
5. Limitations (latency/cost, corpus bias, generalization) are transparently documented.

---

## 8. Assumptions & Dependencies

- **Cloud is Microsoft Azure**, primarily an **Azure Student subscription**, supplemented by institutional/Azure Educator credits where needed for GPU-backed inference across all sprints.
- The team can either secure GPU quota (via Pay-As-You-Go upgrade) or run a 4-bit quantized 32B model on a single mid-tier GPU — see HLD §7.5.
- Public dataset access (PubMedQA, MedQuAD) and public KG (Hetionet/PrimeKG).
- 3-person engineering team for the full sprint duration.
- No paid LLM API budget — all inference self-hosted on Azure GPU compute.

---

> **Next**: Reply "continue" to generate the next document.
