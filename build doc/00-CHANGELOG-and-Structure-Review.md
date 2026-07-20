# Change Note & Industry-Structure Review

> **Date:** 2026-06-21
> **Trigger:** (1) Target cloud changed to **Azure Student subscription**; (2) explicit **Functional (FR) and Non-Functional (NFR) Requirements** were missing; (3) audit every doc against its industry-standard structure.

---

## 0a. Feature addition (later change) — JWT auth + RBAC

> **Trigger:** Add access control — **JWT authentication** + **RBAC authorization** with two roles (`admin`, `researcher`); **admin holds all authorization powers**.

**Design applied across docs:**
- **Roles:** `researcher` (own data only, via role + **ownership** checks) and `admin` (strict superset — all users' data, user management, system-wide eval/observability, governance/feature flags).
- **AuthN:** JWT (HS256), short-lived access (~15 min) + revocable refresh (~7 days, DB-stored); `Authorization: Bearer` on every protected request. Passwords hashed with **argon2id** (bcrypt acceptable).
- **AuthZ:** server-side, **deny-by-default**, via FastAPI dependencies (`get_current_user`, `require_role`, `owns_or_admin`). 401 = unauthenticated, 403 = not permitted.
- **Secrets:** `JWT_SECRET` in Render env; rotation invalidates tokens.

**Docs changed:** 02 PRD (persona 4.4 Admin, Epic G, FR-19…23, NFR-14…16, MoSCoW), 03 BRD (BR-9, admin stakeholder, auth risk), 04 HLD (auth component + diagram, data-flow auth gate, §7.3a Security), 05 LLD (users table role/password_hash/is_active + refresh_tokens, auth/admin endpoints, JWT claims, §5.5 RBAC matrix + dependency code, patterns, edge cases, config YAML auth block), 06 QA (TC-12…17, traceability, security testing, S1 includes auth bypass), 07 Ops (JWT_SECRET/auth config, seed-admin, auth failure modes), clarification-doc (new Part IX-A + FR/NFR/BR rationale rows). The **frontend** gained a login screen + role-gated admin panel. **01 Vision** unchanged.

**Refinement — separation of duties (admin monitors, does not query):** the model was narrowed from "admin = superset of researcher" to **admin is oversight-only**: it can read/monitor all users' runs and manage users + governance, but **query submission is `researcher`-only** (`POST /queries` → 403 for admin). Updated: PRD (persona 4.4, G3/G7, FR-21, **FR-24**, NFR-15), BRD (BR-9), HLD (§7.3a, data-flow gate), LLD (§5.5 matrix + `require_role("researcher")` on submit, `can_read` for monitoring, edge cases), QA (TC-16 read-only, **TC-18** admin→submit=403), clarification (§9A.2/§9A.3, FR-24 rationale). Frontend: admin no longer sees the query workbench — it lands on the Admin console and monitors read-only.

---

## 0. Implementation-stack pivot (later change) — Render + Groq

> **Trigger:** Two implementation changes — **deploy on Render** (instead of Azure) and **host the LLM via the Groq API** (instead of self-hosted Qwen2.5 on GPU via vLLM).

**What this changed conceptually (the implementation course):**

- **Inference:** self-hosted Qwen2.5-7B/32B on Azure NC-series GPUs (vLLM) → **Groq API**, tiered **Llama 3.1 8B Instant** (small/fast) + **Llama 3.3 70B Versatile** (large/reasoning), model IDs pinned per run and swappable.
- **Hosting:** Azure (Static Web Apps / Container Apps / NC-series GPU / Azure PostgreSQL / Blob / Key Vault / Monitor) → **Render** (Static Site / Web Service / Background Worker / Render PostgreSQL / Qdrant private service / persistent disk / env groups / Render logs).
- **The old "dominant risk" is deleted.** The Azure-Student GPU-quota problem and its mitigation ladder (Pay-As-You-Go, Spot VMs, 4-bit AWQ, etc.) are **gone** — there is no GPU to provision.
- **Two narratives flipped:**
  1. *Economics:* "self-host to avoid paid-API cost" → "managed Groq (free tier + pay-as-you-go, per-token) + Render free/low-cost tiers."
  2. *Governance/privacy:* "on-box, no data egress" → **inference calls a third party (Groq)**; prompts/retrieved public text leave the box. Acceptable (public literature, no PHI) and now explicitly documented (NFR-11, HLD §6.1/§7.4).
- **New dependencies documented:** Groq rate limits / 5xx / model deprecation (→ backoff + small-model fallback + model-ID pinning) and Render free-tier cold starts (→ paid instance for the demo window).
- **Performance framing:** "correctness over latency because GPU is scarce" → "correctness-first, and **Groq keeps latency low**; the reported metric is **per-token cost**, not GPU-hour cost."

**Docs changed in this pivot:** 02 PRD (NFR-5/7/8/9/10/11, FR-18, constraints §10, metrics note), 03 BRD (BO3, BR-3/BR-4, value drivers, risks, success criteria, assumptions, governance, stakeholders, KPIs), 04 HLD (overview, architecture diagram, components, stage table, tech stack, §6.1 Render mapping, §7.1/7.2/7.4/7.5, §8 decisions), 05 LLD (GroqModelClient, patterns, config YAML, storage URIs, agent pseudocode, provenance example), 06 QA (Groq-failure chaos tests, latency/token-cost, integration), 07 Ops (full Render/Groq rewrite: topology, §2.1, environments, CI/CD, config, monitoring, SLOs, failure modes, rollback, backup, runbook), 08 Pitch (slide 6, roadmap, limitations), clarification-doc (Part III rewritten, Part IX rewritten to Render/Groq, FR/NFR/BR + constraints + deferred-decisions tables). **01 Vision** unchanged (infra-agnostic by design). The **frontend dummy UI** still labels the per-agent trace with the old model names — left as-is unless you want it synced.

---

## 1. Structure audit — is each document true to its industry-standard shape?

| Doc | Industry-standard expectation | Verdict | Action |
|---|---|---|---|
| **01 Problem/Vision** | Problem, who, why-now, vision, success, non-goals. FR/NFR **not** expected here. | ✅ Conformant | **No change** |
| **02 PRD** | Goals/metrics, personas, user stories, **explicit FR + NFR**, prioritization, flow, constraints. | ⚠️ FR/NFR missing | **Changed** — added numbered FR + NFR + Azure constraint |
| **03 BRD** | Exec summary, objectives, **numbered business requirements**, stakeholders, market, KPIs, risk, assumptions. | ⚠️ Numbered BRs missing | **Changed** — added BR-1…BR-8 + Azure budget risk/assumptions |
| **04 HLD** | Architecture, components, data flow, **concrete tech/cloud stack**, scalability, reliability, decisions. | ⚠️ Cloud was generic | **Changed** — Azure service mapping + GPU-quota constraint |
| **05 LLD** | Class/module, DB schema, API contracts, algorithms, edge cases, patterns. | ✅ Mostly conformant | **Changed (minor)** — S3 → Azure Blob storage URIs |
| **06 Testing/QA** | Strategy, test types, cases, **requirement traceability**, NFR testing, entry/exit, defects. | ⚠️ No traceability matrix | **Changed** — added FR/NFR traceability matrix + Azure chaos note |
| **07 Ops/Deployment** | Topology, environments, CI/CD, config, flags, monitoring, SLOs, failure modes, rollback, backup. | ⚠️ Cloud was generic | **Changed** — full Azure rewrite (services, GPU plan, Monitor, Cost Mgmt) |
| **08 Pitch Deck** | Problem, solution, market, differentiation, roadmap, ask. Cloud vendor is an internal detail, not investor-facing. | ✅ Conformant | **No change** |

---

## 2. What changed and why

### Added FR / NFR (the main gap)
- **PRD §6 Functional Requirements** — `FR-1 … FR-18`, each numbered, testable, and traced to a user story.
- **PRD §7 Non-Functional Requirements** — `NFR-1 … NFR-13` across correctness, reliability, observability, auditability, reproducibility, performance, scalability, portability/cost, security, usability, maintainability.
- **BRD §2a Business Requirements** — `BR-1 … BR-8` (business-level, distinct from product FRs).
- **QA §5.1 Requirement Traceability Matrix** — maps every test case to the FR/NFR it covers.

### Azure Student subscription (cloud change)
Applied everywhere the cloud was referenced, and surfaced the **single most important new reality**:

> Azure for Students has **limited credit and no GPU quota by default**, which **cannot sustain self-hosted Qwen2.5-32B inference** as originally written.

This is now documented honestly with a mitigation ladder (Pay-As-You-Go + GPU quota request → Spot VMs → institutional/Educator credits → 4-bit AWQ 32B on a smaller GPU) in:
- **PRD** NFR-10 + Constraints §10
- **BRD** BR-4, risk table, assumptions §8
- **HLD** §6.1 Azure service mapping + §7.5 GPU constraint
- **LLD** Azure Blob storage URIs
- **Ops** §2 topology + §2.1 GPU plan, CI/CD (GitHub Actions + ACR + Container Apps), Key Vault, Azure Monitor, Cost Management budget alerts, failure/runbook rows
- **QA** §5.1 Azure chaos/credit-exhaustion note

### Concrete Azure service choices used
Static Web Apps (frontend) · Container Apps (backend) · Container Registry (images) · NC-series GPU VMs (vLLM) · Database for PostgreSQL Flexible Server · Blob Storage (exports) · Key Vault (secrets) · Azure Monitor + Application Insights + Log Analytics (observability) · Cost Management (budget alerts) · GitHub Actions / Azure DevOps (CI/CD).

---

## 3. Unchanged (and why that's correct)
- **01 Problem/Vision** and **08 Pitch Deck** are structurally complete for their genres. Vision docs and investor decks do not carry FR/NFR tables or cloud-vendor specifics — adding them would *break* the industry convention, not improve it. The Azure detail lives in the engineering/ops docs where it belongs.

---

## 4. Note for future instances
- A complete documentation set must include **explicitly numbered FR and NFR** (PRD), **numbered BR** (BRD), and a **requirement-traceability matrix** (QA) — not just user stories.
- Target cloud is **Azure (Student subscription)**. Always reflect the **no-default-GPU-quota** reality for any self-hosted large-model (≥30B) plan and give the mitigation ladder rather than assuming GPU availability.
