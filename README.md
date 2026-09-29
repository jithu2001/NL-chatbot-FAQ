# PowerUp Money — Mutual Fund FAQ Assistant

A **facts-only** mutual fund FAQ assistant. It answers factual questions about five PPFAS Mutual Fund schemes using **only official public sources** from the AMC and AMFI. Every factual answer includes **exactly one official source link** and the source's official **last-updated date**.

It has a React UI built with the [Atlassian Design System](https://atlassian.design/), a FastAPI backend and a persistent **ChromaDB** vector store, and supports two provider modes:

| Mode | LLM | Embeddings | Use for |
|---|---|---|---|
| **Hosted** (default) | **Groq** API (`openai/gpt-oss-20b`) | **fastembed** `BAAI/bge-small-en-v1.5`, in-process on CPU | Render free tier or any small server |
| **Local** | **Ollama** `llama3.1:8b` | **Ollama** `nomic-embed-text` | Fully offline, private use |

Switch modes with `LLM_PROVIDER` and `EMBEDDING_PROVIDER`; see [Providers](#providers).

> **Facts-only. No investment advice.** The assistant never recommends, ranks or compares funds, and never predicts returns. It never asks for or stores personal information.

---

## Contents

- [Product scope](#product-scope)
- [Selected AMC and schemes](#selected-amc)
- [Official sources](#official-sources)
- [Architecture](#architecture) · [Why Groq, fastembed and Ollama](#why-groq-fastembed-and-ollama) · [Why ChromaDB](#why-chromadb) · [RAG pipeline](#rag-pipeline)
- [Project structure](#project-structure)
- [Requirements](#requirements) · [Ollama installation (local mode)](#ollama-installation-local-mode) · [Model installation](#model-installation) · [Environment variables](#environment-variables)
- [Backend setup](#backend-setup) · [Frontend setup](#frontend-setup) · [Source ingestion](#source-ingestion) · [Running ChromaDB](#running-chromadb) · [Running the backend](#running-backend) · [Running the frontend](#running-frontend)
- [Providers](#providers) · [Deploy on Render (free)](#deploy-on-render-free) · [Docker (optional)](#docker-optional)
- [Testing](#testing) · [Evaluation](#evaluation) · [Known limitations](#known-limitations) · [Deliverables](#deliverables) · [Disclaimer](#disclaimer)

---

## Project overview

| Question | Response |
|---|---|
| *What is the expense ratio?* | "The expense ratio of Parag Parikh Flexi Cap Fund is 1.05% for the Regular Plan and 0.53% for the Direct Plan." **Source:** PPFAS Mutual Fund Factsheet – August 2026, p. 4 ↗ · **Last updated from sources:** 31 August 2026 |
| *What is the ELSS lock-in period?* | "The ELSS lock-in period for Parag Parikh ELSS Tax Saver Fund is 3 years." **Source:** Scheme Information Document – ELSS Tax Saver Fund, p. 69 ↗ |
| *Should I invest in this fund?* | Safe refusal plus one official educational source |
| *What return will this fund give next year?* | "I can't predict future returns…" plus the official factsheet |
| *My PAN is ABCDE1234F…* | PII refusal. The question never reaches the LLM and is never logged. |

The project demonstrates three skills:

- **W1: thinking like a model.** It identifies the exact fact requested and classifies each question as FACTUAL, ADVICE, UNSUPPORTED or PII.
- **W2: LLMs and prompting.** It uses a strict system prompt, grounded generation, concise answers, safe refusals and hallucination checks.
- **W3: RAG.** It uses an official-source corpus, HTML/PDF ingestion, structure-aware chunking, self-hosted embeddings, ChromaDB with metadata filtering, a relevance gate, and citations controlled by the backend.

## Product scope

**The assistant does:**

- Answer factual questions about expense ratio (TER), exit load, minimum SIP and lump sum, ELSS lock-in, riskometer, benchmark, investment objective, fund managers, NAV/AUM (as published), and where to find statements, CAS, capital-gains statements, factsheets and scheme documents.
- Keep answers to at most 3 sentences, with one source and the official last-updated date.

**The assistant does not:**

- Give advice, recommendations, rankings or performance comparisons.
- Predict or calculate returns, or suggest portfolio allocations.
- Handle account-specific queries or personal data.
- Accept user-supplied URLs as sources.

## Selected AMC

**PPFAS Mutual Fund** (PPFAS Asset Management Pvt. Ltd., SEBI Registration No. MF/069/12/01), website <https://amc.ppfas.com>.

Why PPFAS: its site publishes server-rendered HTML pages and text-based PDFs (factsheet, KIM, SID) that can be ingested reliably and cited page by page. Its schemes span equity, ELSS, debt and hybrid categories.

## Selected schemes

| # | Scheme | Category |
|---|---|---|
| 1 | Parag Parikh Flexi Cap Fund | Flexi Cap (Equity) |
| 2 | Parag Parikh Large Cap Fund | Large Cap (Equity) |
| 3 | Parag Parikh ELSS Tax Saver Fund | ELSS (3-year statutory lock-in) |
| 4 | Parag Parikh Liquid Fund | Liquid (Debt) |
| 5 | Parag Parikh Conservative Hybrid Fund | Conservative Hybrid |

The monthly factsheet also covers two other PPFAS schemes (Arbitrage, Dynamic Asset Allocation). Ingestion **skips those pages** because they are out of scope.

## Official sources

There are 24 sources: 18 from PPFAS (AMC) and 6 from AMFI. The registry is [`data/sources.csv`](data/sources.csv), with columns `source_id, title, scheme, topic, source_type, url, publication_date, last_updated, retrieved_date, authority`.

| ID | Source | Type | Authority | Last updated |
|---|---|---|---|---|
| SRC-001 | [PPFAS Mutual Fund Factsheet - August 2026](https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-August-2026.pdf) | AMC Factsheet | AMC | 2026-08-31 |
| SRC-002 | [Key Information Memorandum - Parag Parikh Flexi Cap Fund](https://amc.ppfas.com/downloads/parag-parikh-flexi-cap-fund/KIM_PPFCF.pdf) | KIM | AMC | 2025-11-27 |
| SRC-003 | [Key Information Memorandum - Parag Parikh Large Cap Fund](https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/kim-parag-parikh-large-cap-fund.pdf) | KIM | AMC | 2025-12-10 |
| SRC-004 | [Key Information Memorandum - Parag Parikh ELSS Tax Saver Fund](https://amc.ppfas.com/downloads/parag-parikh-tax-saver-fund/kim-parag-parikh-tax-saver-fund.pdf) | KIM | AMC | 2025-11-27 |
| SRC-005 | [Key Information Memorandum - Parag Parikh Liquid Fund](https://amc.ppfas.com/downloads/parag-parikh-liquid-fund/kim-parag-parikh-liquid-fund.pdf) | KIM | AMC | 2025-11-27 |
| SRC-006 | [Key Information Memorandum - Parag Parikh Conservative Hybrid Fund](https://amc.ppfas.com/downloads/parag-parikh-conservative-hybrid-fund/kim-parag-parikh-conservative-hybrid-fund.pdf) | KIM | AMC | 2025-11-27 |
| SRC-007 | [Scheme Information Document - Parag Parikh ELSS Tax Saver Fund](https://amc.ppfas.com/downloads/parag-parikh-tax-saver-fund/sid-parag-parikh-tax-saver-fund.pdf) | SID | AMC | 2025-11-28 |
| SRC-008 | [Scheme Information Document - Parag Parikh Flexi Cap Fund](https://amc.ppfas.com/downloads/parag-parikh-flexi-cap-fund/SID_PPFCF.pdf) | SID | AMC | 2025-11-28 |
| SRC-009 | [Scheme Page - Parag Parikh Flexi Cap Fund](https://amc.ppfas.com/schemes/parag-parikh-flexi-cap-fund/) | AMC Scheme Page | AMC | Not specified |
| SRC-010 | [Scheme Information Document - Parag Parikh Large Cap Fund](https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/sid-parag-parikh-large-cap-fund.pdf) | SID | AMC | 2025-12-10 |
| SRC-011 | [Scheme Page - Parag Parikh ELSS Tax Saver Fund](https://amc.ppfas.com/schemes/parag-parikh-elss-tax-saver-fund/) | AMC Scheme Page | AMC | Not specified |
| SRC-012 | [Scheme Page - Parag Parikh Liquid Fund](https://amc.ppfas.com/schemes/parag-parikh-liquid-fund/) | AMC Scheme Page | AMC | Not specified |
| SRC-013 | [Scheme Page - Parag Parikh Conservative Hybrid Fund](https://amc.ppfas.com/schemes/parag-parikh-conservative-hybrid-fund/) | AMC Scheme Page | AMC | Not specified |
| SRC-014 | [KIM, SID and SAI Downloads](https://amc.ppfas.com/downloads/kim-sid-and-sai/) | AMC Downloads Page | AMC | Not specified |
| SRC-015 | [Factsheet Downloads](https://amc.ppfas.com/downloads/factsheet/) | AMC Downloads Page | AMC | Not specified |
| SRC-016 | [Investor Desk - PPFAS Mutual Fund](https://amc.ppfas.com/investor-desk/) | AMC Investor Services | AMC | Not specified |
| SRC-017 | [Account Statement via Missed Call](https://amc.ppfas.com/investor-desk/statement-via-missed-call/) | AMC Investor Services | AMC | Not specified |
| SRC-018 | [MFCentral - PPFAS Mutual Fund](https://amc.ppfas.com/investor-desk/MFCentral/) | AMC Investor Services | AMC | Not specified |
| SRC-019 | [AMFI Investor Corner - Expense Ratio](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio) | AMFI Investor Education | AMFI | Not specified |
| SRC-020 | [AMFI Investor Corner - Consolidated Account Statement (CAS)](https://www.amfiindia.com/investor/become-mf-distributor?zoneName=consolidatedAcct) | AMFI Investor Education | AMFI | Not specified |
| SRC-021 | [AMFI - Download CAS](https://www.amfiindia.com/online-center/download-cas) | AMFI Investor Services | AMFI | Not specified |
| SRC-022 | [AMFI Investor Corner - Investor Service FAQs](https://www.amfiindia.com/investor/become-mf-distributor?zoneName=InvestorService) | AMFI Investor Education | AMFI | Not specified |
| SRC-023 | [AMFI Investor Corner - Risks in Mutual Funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds) | AMFI Investor Education | AMFI | Not specified |
| SRC-024 | [AMFI Investor Corner - Categorization of Mutual Fund Schemes](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=CategorizationOfMutualFundSchemes) | AMFI Investor Education | AMFI | Not specified |

**Date rules (no dates are invented):**

- `publication_date` / `last_updated` for KIMs and SIDs come from the document's own statement, for example *"This Key Information Memorandum (KIM) is dated November 27, 2025"*.
- The factsheet's `last_updated` is its printed data date (*"as on August 31, 2026"*). Its publication date is not printed, so it is `Not specified`.
- Web pages carry no update date, so `last_updated = Not specified`. The UI then shows *"Last updated from sources: Not specified · Source retrieved: 27 September 2026"*.
- `retrieved_date` is when the document was downloaded.

**Prohibited sources are never used:** Groww, Zerodha, Moneycontrol, ET Money, BankBazaar, Wikipedia, Reddit, Quora, blogs, YouTube, news or comparison sites. The registry loader rejects any URL whose host is not the official domain for its `authority` (`amc.ppfas.com`, `amfiindia.com`, `sebi.gov.in`).

## Architecture

```text
┌───────────────────────────┐      POST /api/chat       ┌──────────────────────────────────────────────┐
│ React + TS + Vite +       │ ────────────────────────► │ FastAPI backend                              │
│ Atlassian DS (:5173)      │ ◄──────────────────────── │                                              │
└───────────────────────────┘   answer + 1 source       │  1. PII detector ──► refuse (no LLM, no log) │
                                                        │  2. Classifier  ──► ADVICE / UNSUPPORTED     │
                                                        │                     templates + registry src │
                                                        │  3. Scheme & topic detection                 │
                                                        │  4. Retriever ──► embed (fastembed / Ollama) │
                                                        │       └─► ChromaDB (metadata filters)        │
                                                        │  5. Relevance gate (< 0.70 ⇒ no LLM call)    │
                                                        │  6. Context ──► LLM (Groq / Ollama)          │
                                                        │  7. Answer validator (URLs, advice, numbers, │
                                                        │     ≤ 3 sentences)                           │
                                                        │  8. Backend selects ONE source from metadata │
                                                        └──────────────────────────────────────────────┘
                     Hierarchy of truth:  OFFICIAL SOURCE → CHROMADB → RETRIEVED CONTEXT → LLM → ANSWER
```

**The LLM only writes the answer text.** It is told not to output URLs, and anything citation-like it does produce is stripped. The displayed source always comes from ChromaDB metadata written from `data/sources.csv`, and is re-resolved through the registry at response time.

### Why Groq, fastembed and Ollama

- **Groq** serves `openai/gpt-oss-20b` on its free developer tier (Llama models now need an enterprise plan). It is fast (about 1 s per answer) and has a free developer tier. It needs only an API key and no GPU, so it fits Render's free plan.
- **fastembed** runs `bge-small-en-v1.5` through ONNX Runtime inside the backend process, using about 150 MB RAM and no API key. Questions are embedded on your own server, and no cloud embedding API is used.
- **Ollama (local mode)** keeps everything on your machine: questions never leave it. It uses a simple HTTP API (`/api/chat`, `/api/embed`) called with `httpx`.
- Models are always set by environment variables, never hard-coded.

### Why ChromaDB

- An **embedded, persistent** vector store: no separate server, and data lives in `data/chroma/`.
- **Metadata filtering** (`where={"scheme": ...}`, `source_type`, `source_id`, `page`) is central to scheme-aware retrieval.
- **Deterministic IDs + upsert** make ingestion idempotent.

### RAG pipeline

**Ingestion** ([`backend/app/rag/ingest.py`](backend/app/rag/ingest.py)):

```text
Official URL (sources.csv) → download (cached in data/documents/) → extract (HTML / PDF)
  → clean → chunk → embed (fastembed bge-small, or Ollama nomic-embed-text) → upsert into ChromaDB
```

- **PDFs** ([`extractors.py`](backend/app/rag/extractors.py)) are rebuilt **column by column from word positions** with PyMuPDF. Factsheets are 3-column layouts, and naive extraction separates "Expense Ratio" from "1.05%". Rotated riskometer lettering is dropped, and running headers/footers that repeat across pages are removed. Each chunk keeps its `page`. In the multi-scheme factsheet, each page's scheme is detected from its **largest-font heading**, and pages of out-of-scope schemes are skipped. pypdf's layout mode is a fallback.
- **HTML**: navigation, menus and footers are removed. Headings become `## …`, list items become `- …`, and tables become `cell | cell` rows.
- **Chunking** ([`chunker.py`](backend/app/rag/chunker.py)): chunks are split on blocks, then lines, then sentences. **A line is never split**, so a label and its value stay together. Chunk size depends on the embedding model: about 350 tokens with 60 overlap for bge-small (which reads at most 512 word pieces), and about 900 with 150 for nomic-embed-text. At answer time, the top hits are **expanded with their neighbouring chunks from the same page** (small-to-big), so facts that straddle a boundary, such as a list of fund managers, stay intact.
- **Metadata per chunk**: all registry fields plus `page`, `chunk_index`, `content_hash`. IDs look like `SRC-001-chunk-0001`.

**Retrieval** ([`retriever.py`](backend/app/rag/retriever.py)):

1. Detect the **scheme** (names and aliases such as "ELSS", "liquid fund") and the **topic** (expense ratio, exit load, SIP, lock-in, riskometer, benchmark, statements, CAS, …).
2. Apply a **metadata filter**: `scheme ∈ {detected scheme, "General"}`, or `scheme = "General"` for investor-service topics. A scheme-specific question with no scheme named uses `DEFAULT_SCHEME`, and the UI says so.
3. Run a **second filtered query** over the topic's authoritative source type (for example `AMC Factsheet` for TER).
4. Re-rank with **hybrid relevance** = 0.5 × cosine similarity + 0.5 × lexical coverage of the question's key terms, plus small boosts for authority and scheme match, with ties broken by recency.
5. **Relevance gate:** if the best chunk scores below `RELEVANCE_THRESHOLD` (0.70), return *"I couldn't verify that fact from the official sources in my current knowledge base."* and **do not call the LLM**.

**Generation and validation** ([`answer_pipeline.py`](backend/app/services/answer_pipeline.py), [`answer_validator.py`](backend/app/safety/answer_validator.py)):

- Only chunks at or above the threshold become context. For monthly-changing facts (TER, riskometer, NAV, AUM, minimums, managers), only the **latest factsheet** passages are used when available.
- The system prompt ([`system_prompt.py`](backend/app/prompts/system_prompt.py)) is the mandated prompt plus output-format notes. Generation uses temperature 0.
- The validator strips URLs and "Source:" lines, blocks advice-shaped phrases, **rejects answers containing any number not present in the context**, and truncates to 3 sentences.
- **Source selection** picks the one chunk that best supports the answer, based on retrieval rank plus the answer's numbers and words found in that chunk. Its registry entry supplies `title`, `url`, `source_type`, `last_updated` and `page`.

## Project structure

```text
.
├── frontend/                     React + TypeScript + Vite + Atlassian Design System (@atlaskit)
│   ├── src/
│   │   ├── components/           ChatMessage, ChatInput, ExampleQuestions, SourceCitation, Disclaimer, HealthStatus
│   │   ├── api/chat.ts           API client (/api/chat, /api/health, /api/schemes)
│   │   ├── App.tsx               app shell: top navigation, page header, empty state, conversation
│   │   ├── index.css             layout only; every colour/space/font is an ADS token (--ds-*)
│   │   └── main.tsx              loads the ADS light/dark, spacing, typography and shape themes
│   ├── package.json
│   ├── vite.config.ts            dev proxy /api → http://localhost:8000
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI app, CORS, error handlers, model warm-up
│   │   ├── api/chat.py           POST /api/chat, GET /api/health, GET /api/schemes
│   │   ├── llm/                  provider.py (switch), groq_client.py, ollama_client.py, errors.py
│   │   ├── rag/                  ingest.py, extractors.py, chunker.py, embeddings.py, retriever.py, vector_store.py
│   │   ├── classifier/question_classifier.py
│   │   ├── safety/               pii_detector.py, answer_validator.py, rate_limit.py
│   │   ├── prompts/system_prompt.py
│   │   ├── services/answer_pipeline.py
│   │   ├── core/                 config.py, catalog.py (schemes/topics), sources.py (registry)
│   │   └── models/schemas.py
│   ├── tests/                    pytest unit tests (84)
│   ├── requirements.txt, requirements-dev.txt, .env.example
├── data/
│   ├── sources.csv               official source registry
│   ├── documents/                downloaded source files (cache, git-ignored)
│   └── chroma/                   persistent ChromaDB, prebuilt fastembed index (committed; shipped in the image)
├── evaluation/
│   ├── sample_qa.csv             31 evaluation questions
│   ├── run_eval.py               automated evaluation runner
│   └── README.md                 evaluation report
├── scripts/
│   ├── ingest_sources.py         build/update the index
│   ├── reset_vector_db.py        drop and recreate the collection
│   └── share_ngrok.sh            share a local instance through ngrok
├── Dockerfile                    single image: built UI + API (Render)
├── render.yaml                   Render Blueprint (free web service)
├── docker-compose.yml
├── .env.example
└── README.md
```

## Requirements

- **Python 3.11+** (developed and tested on 3.14)
- **Node.js 20+** and npm (tested on Node 22)
- **Hosted mode:** a free Groq API key from <https://console.groq.com/keys>. The fastembed model (about 130 MB) downloads automatically on first use.
- **Local mode only:** Ollama 0.3+ (tested on 0.34.4) and about 6 GB of disk for models. A GPU is recommended (tested on an 8 GB RTX 5050).

## Providers

| Variable | Hosted (default) | Local |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `ollama` |
| `EMBEDDING_PROVIDER` | `fastembed` | `ollama` |
| Credentials | `GROQ_API_KEY` | none |

- **The LLM provider can be switched at any time.** The embedding provider cannot: the index must be built with the same embedding model that embeds the questions. The collection records its model. If they differ, the app refuses to query and reports the knowledge base as unavailable. Running `python scripts/ingest_sources.py` rebuilds it for the configured model.
- **The committed index in `data/chroma/` is built with fastembed**, which is what Render uses. For local Ollama mode, set both providers to `ollama` and re-run ingestion. Don't commit that index, or Render will refuse it until it is rebuilt with fastembed.
- **In hosted mode, questions go to Groq**, but only after the PII check has passed. PII questions, advice questions and unsupported questions never reach any LLM. Retrieval and citations stay on your server.

## Ollama installation (local mode)

Install Ollama from <https://ollama.com/download>. On Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Check the installation:

```bash
ollama --version
```

The Ollama server must be running. The desktop app and the Linux service start it automatically; otherwise run `ollama serve`.

## Model installation

Pull the LLM:

```bash
ollama pull llama3.1:8b
```

Pull the embedding model:

```bash
ollama pull nomic-embed-text
```

Verify both are installed:

```bash
ollama list
```

Optionally chat with the model once (type `/bye` to exit):

```bash
ollama run llama3.1:8b
```

Verify the Ollama API:

```bash
curl http://localhost:11434/api/tags
```

The application assumes Ollama is running locally at `http://localhost:11434`.

## Environment variables

Copy the example file and adjust it if needed:

```bash
cp backend/.env.example backend/.env
```

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` or `ollama` |
| `EMBEDDING_PROVIDER` | `fastembed` | `fastembed` or `ollama` (re-ingest after changing) |
| `GROQ_API_KEY` | *(empty)* | Groq key (secret) |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq chat model (must be enabled for your key; Llama models are enterprise-only on Groq) |
| `FASTEMBED_MODEL` | `BAAI/bge-small-en-v1.5` | CPU embedding model |
| `RATE_LIMIT_PER_MINUTE` | `12` | Chat requests per visitor per minute (0 = off) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3.1:8b` | Chat model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model (re-ingest after changing it) |
| `CHROMA_PERSIST_DIRECTORY` | `../data/chroma` | ChromaDB folder, relative to the `.env` file's folder |
| `TOP_K` | `5` | Chunks returned by retrieval |
| `RELEVANCE_THRESHOLD` | `0.70` | Minimum hybrid relevance to answer |
| `DEFAULT_SCHEME` | `Parag Parikh Flexi Cap Fund` | Scheme used when a scheme-specific question names none |
| `OLLAMA_NUM_CTX` | `8192` | Context window requested from Ollama |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed browser origins |

A root [`.env.example`](.env.example) (with `./data/chroma`) is also provided. The backend reads `backend/.env` first, then `./.env`, and resolves relative paths from the folder of the file they came from. **Never commit real `.env` files**; they are git-ignored.

## Backend setup

```bash
cd backend

python -m venv .venv

source .venv/bin/activate
```

On Windows, activate with:

```bash
.venv\Scripts\activate
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

## Frontend setup

```bash
cd frontend

npm install
```

## Source ingestion

With the backend virtualenv active (and Ollama running in local mode), run from the **project root**:

```bash
python scripts/ingest_sources.py
```

Example output:

```text
Loading source registry...
24 sources registered

[1/24] PPFAS Mutual Fund Factsheet - August 2026  (SRC-001)
  ✓ Downloaded (PDF, 4130 KB)
  ✓ Extracted 32 page(s), 96,202 characters
  ✓ 35 chunks
  ✓ Embedded
  ✓ Added to ChromaDB
...
Ingestion complete.
24 sources
1513 chunks
```

A first run takes a few minutes on CPU with fastembed, or about a minute with Ollama on a GPU. The run is **idempotent**: re-running skips sources whose content, chunking settings and embedding model are unchanged (`✓ Already indexed and unchanged - skipped`). A changed source has its old chunks replaced, never duplicated.

Useful flags:

```bash
python scripts/ingest_sources.py --refresh              # re-download all documents
python scripts/ingest_sources.py --force                # re-embed everything
python scripts/ingest_sources.py --only SRC-001 SRC-004 # specific sources
```

**Reset the vector database** (downloaded documents are kept):

```bash
python scripts/reset_vector_db.py          # asks for confirmation
python scripts/reset_vector_db.py --yes
python scripts/ingest_sources.py           # rebuild
```

**Adding or updating a source:** edit `data/sources.csv` (official domains only, real dates or `Not specified`), then run `python scripts/ingest_sources.py --only SRC-0XX --refresh`.

## Running ChromaDB

There is nothing to start. ChromaDB runs **embedded** in the backend process (`chromadb.PersistentClient`) and stores its data in `data/chroma/`. The data persists across restarts, and the backend never rebuilds the index on start-up. The collection name is `mutual_fund_faq` (cosine distance).

## Running backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- Health check: <http://localhost:8000/api/health> returns `{"status":"ok","llm":true,"chromadb":true}`
- Interactive API docs: <http://localhost:8000/api/docs>

```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is the expense ratio?"}'
```

```json
{
  "answer": "The expense ratio of Parag Parikh Flexi Cap Fund is 1.05% for the Regular Plan and 0.53% for the Direct Plan.",
  "classification": "FACTUAL",
  "source": {
    "title": "PPFAS Mutual Fund Factsheet - August 2026",
    "url": "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-August-2026.pdf",
    "source_type": "AMC Factsheet",
    "authority": "AMC",
    "last_updated": "2026-08-31",
    "retrieved_date": "2026-09-27",
    "page": 4
  },
  "last_updated": "2026-08-31",
  "retrieved_date": "2026-09-27",
  "scheme": "Parag Parikh Flexi Cap Fund",
  "scheme_defaulted": true
}
```

The request also accepts an optional `"scheme"` (one of the five scheme names), which the UI's scheme selector sends. If the LLM is unreachable, `/api/chat` returns HTTP 503. The message is *"The AI service is currently unavailable…"* in hosted mode, or *"…Please make sure Ollama is running."* in local mode. If Groq's rate limit is hit, the message is *"The assistant is handling many questions right now…"*. If the knowledge base is missing or empty, it returns 503 with *"The knowledge base is currently unavailable. Please try again."*

At start-up the backend loads the embedding model in the background, and in local mode the Ollama model too, which takes about 45 s. After that, answers take about 1–3 s.

## Running frontend

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to `http://localhost:8000`. If port 5173 is busy, Vite picks the next free port (for example 5174). The proxy works regardless, and the browser only talks to the Vite origin.

In development mode, a small "AI model ✓ · Knowledge Base ✓" status is shown in the header on wider screens.

Production build: `npm run build` writes `frontend/dist/`. Set `SERVE_FRONTEND_DIR=../frontend/dist` and the backend serves the UI itself on port 8000.

## Sharing publicly with ngrok

One tunnel is enough. The production build is served by `vite preview` on port 4173, which proxies `/api` to the backend. The backend itself is never exposed directly.

```bash
ngrok config add-authtoken <your-token>   # once; get the token from https://dashboard.ngrok.com
./scripts/share_ngrok.sh                  # starts backend if needed, builds the UI, serves it on :4173, opens the tunnel
```

To do it manually, start the backend as usual, then run `cd frontend && npm run build && npx vite preview --port 4173`, and in another terminal `ngrok http 4173`. Share the `https://….ngrok-free.app` Forwarding URL.

**Before sharing:**

- **Your machine does the work.** The app is reachable only while your computer and the tunnel are running. In local mode, every question also runs on your GPU.
- **Visitors are rate-limited.** `/api/chat` allows `RATE_LIMIT_PER_MINUTE` (default 12) requests per visitor. The limiter keys on a salted hash of the IP from `X-Forwarded-For`, keeps it in memory only, and never logs it.
- **Only tunnel hostnames are served.** Vite accepts `*.ngrok-free.app`, `*.ngrok-free.dev`, `*.ngrok.app` and `*.ngrok.dev` as hosts and rejects others with 403.
- **ngrok's free tier shows a one-time warning page** to browser visitors, which they click through. The app's API calls skip it.

## Deploy on Render (free)

The repo contains a Render Blueprint ([`render.yaml`](render.yaml)) and a single [`Dockerfile`](Dockerfile). The Dockerfile builds the React app, installs the backend, and **bakes in the embedding model and the prebuilt index**, which matters because Render's free filesystem is ephemeral. FastAPI then serves both the UI and `/api` from one URL.

1. **Get a Groq API key** at <https://console.groq.com/keys>.
2. **Push the repo to GitHub.** Include `data/chroma/`, the prebuilt fastembed index of about 40 MB. If it is missing, the image builds it during the Docker build, which is slower and needs about 1 GB RAM.
3. **Create the service on Render.** Choose **New → Blueprint**, pick the repo, and Render reads `render.yaml`. When prompted, paste `GROQ_API_KEY`. It is stored as a Render secret and never committed.
4. **Wait for the build** (about 5–10 min). Then open `https://<service-name>.onrender.com`. `/api/health` should show `{"status":"ok","llm":true,"chromadb":true}`.

**Free-plan behaviour to expect:**

| Limit | Effect |
|---|---|
| 512 MB RAM, 0.1 CPU | Fits: about 350 MB at runtime (FastAPI + ChromaDB + bge-small). Embedding a question takes about 0.2–0.5 s. |
| Sleeps after 15 min idle | The first visit after a quiet period takes about 1 min to wake up. |
| No persistent disk | Fine: the index is read-only and baked into the image. Redeploy to update it. |
| 750 free instance hours per month | Enough for one always-on service. |
| Groq free tier rate limits | Heavy traffic may get *"handling many questions right now"*. The app's own limit is `RATE_LIMIT_PER_MINUTE` (10 on Render). |

**Updating the knowledge base:** edit `data/sources.csv`, run `python scripts/ingest_sources.py --refresh` locally in hosted (fastembed) mode, then commit `data/chroma/` and push. Render redeploys automatically.

## Docker (optional)

The same image runs locally. Put `GROQ_API_KEY` in `backend/.env`, then:

```bash
docker compose up --build   # → http://localhost:8080
```

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

There are 84 unit tests covering:

- The classifier: FACTUAL, ADVICE and UNSUPPORTED examples, including false-positive traps such as *"What is the exit load if I redeem it within a year?"*.
- The PII detector: positives and negatives.
- The answer validator: URL stripping, self-citation removal, number grounding, advice blocking, the 3-sentence limit, and abbreviations such as "Rs." and "Mr.".
- The chunker (labels stay with values, overlap), scheme and topic detection, and registry validation (third-party domains are rejected).

## Demo script (3 minutes)

1. Open the app. The header shows **PowerUp Money / Mutual Fund FAQ Assistant**, with the **Facts-only. No investment advice.** banner and 3 example questions.
2. Click **What is the expense ratio?** The answer is 1.05% / 0.53% for Flexi Cap, with **Source: Factsheet – August 2026, p. 4 ↗** and **Last updated from sources: 31 August 2026**.
3. Click **What is the minimum SIP?** The answer is ₹1,000 monthly / ₹3,000 quarterly, with the official factsheet as the source.
4. Type **What is the ELSS lock-in period?** The answer is 3 years, with the ELSS SID p. 69 as the source.
5. Type **Should I invest in this fund?** The response is a safe refusal with a "No investment advice" badge and an AMFI educational source.
6. Type **What return will this fund give next year?** The response is "I can't predict future returns…" with a "No predictions" badge and the factsheet.
7. (Optional) Type **My PAN is ABCDE1234F. What is my balance?** The response is the PII refusal, with nothing sent to the LLM.

## Evaluation

```bash
python evaluation/run_eval.py
```

These are the latest results on 31 questions; see [`evaluation/README.md`](evaluation/README.md) for methodology and known failures.

| Metric | Result |
|---|---|
| Classification accuracy | 31/31 |
| Retrieval accuracy (hit@5) | 20/20 |
| Citation accuracy | 20/20 |
| Answer correctness | 22/22 |
| Grounded numbers (in cited page) | 20/20 |
| Refusal accuracy (no LLM call) | 9/9 |
| Median latency (warm) | 1.9 s |

## Security and privacy

- **No accounts, no authentication, and no conversation storage.** Questions exist only in memory during a request, and the UI keeps the chat only in page memory.
- **PII is refused before any processing.** It is never embedded, never sent to any LLM, and never written to logs. Application logs record only the classification label. Request-validation errors do not echo input.
- Responses never include prompts, file paths, environment values or ChromaDB internals. Only the registry's official URLs are ever shown, and user-supplied URLs are never fetched or cited.

## Known limitations

- **Corpus snapshot.** Factsheet data is as on 31 August 2026; KIMs and SIDs are dated November/December 2025. Update `sources.csv` and re-ingest to refresh.
- **SEBI pages are not in the corpus.** `sebi.gov.in` was unreachable during the TLS handshake from the development network, so the corpus uses AMC and AMFI sources only. The registry and domain allow-list already support SEBI URLs.
- **One JavaScript-rendered page.** The Large Cap scheme page renders its content with JavaScript, so its SID is indexed instead.
- **Rule-based classification** is transparent and testable, but unusual phrasings of advice may slip through to retrieval. The post-generation advice guard is the second line of defence.
- **Non-numeric embellishment** by the LLM (for example "applies to both plans") is not caught automatically; numbers are.
- **Default scheme.** Questions that name no scheme are answered for the Flexi Cap fund; the answer and the UI say so.
- **Single-turn.** "This fund" is not resolved from earlier messages. Use the scheme selector or name the scheme.
- Answers are for **Regular and Direct plans as published**. Account-specific data (holdings, balances, transactions) is out of scope by design.

## Deliverables

| Brief requirement | Where |
|---|---|
| Working prototype link | <https://nl-chatbot-faq.onrender.com/> (Render free plan; first visit after 15 min idle takes about 1 min to wake) |
| Source list (15–25 URLs) | [`data/sources.csv`](data/sources.csv): 24 official PPFAS (AMC) and AMFI URLs, also tabled under [Official sources](#official-sources) |
| README: setup, scope, known limits | This file: [setup](#backend-setup), [scope](#selected-amc), [known limitations](#known-limitations) |
| Sample Q&A (5–10 queries with answers and links) | [`evaluation/sample_answers.md`](evaluation/sample_answers.md): 10 real answers, regenerate with `python evaluation/generate_sample_answers.py` |
| Disclaimer snippet used in the UI | [Below](#disclaimer-snippet-used-in-the-ui) |

**Behaviour required by the brief:**

- **Answers:** every answer carries exactly one official source link, including refusals. Advice and portfolio questions link the scheme's KIM or AMFI investor education. Performance questions link the official factsheet. Personal-data refusals link the AMC's Investor Desk. "Couldn't verify" answers link the scheme's KIM or the official KIM/SID downloads page.
- **Length and dates:** answers are at most 3 sentences and show "Last updated from sources: …".
- **Personal data:** PAN, Aadhaar, account or folio numbers, OTPs, emails and phone numbers are refused before any processing, and are never stored or logged.
- **Performance:** returns are never computed or compared.

### Disclaimer snippet used in the UI

Shown as a warning banner at the top of every page ([`Disclaimer.tsx`](frontend/src/components/Disclaimer.tsx)):

> **Facts-only. No investment advice.**
> Information is provided from publicly available official AMC (PPFAS Mutual Fund) and AMFI sources. Always verify the latest official scheme documents.

## Disclaimer

**Facts-only. No investment advice.** This is a prototype for educational purposes. Information is drawn from publicly available official PPFAS Mutual Fund (AMC) and AMFI documents, and may be out of date. Always verify with the latest official scheme documents at <https://amc.ppfas.com>. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. PowerUp Money is not affiliated with PPFAS Mutual Fund or AMFI.
