# Evaluation Report — PowerUp Money Mutual Fund FAQ Assistant

**Run date:** 27 September 2026
**Setup:** `llama3.1:8b` + `nomic-embed-text` via local Ollama 0.34.4, ChromaDB 1.5.9 (669 chunks from 24 official sources), `TOP_K=5`, `RELEVANCE_THRESHOLD=0.70`, RTX 5050 Laptop GPU (8 GB)
**Dataset:** [`sample_qa.csv`](sample_qa.csv), 31 questions
**Runner:** `python evaluation/run_eval.py` (writes `evaluation/results/latest.csv` and `summary.json`)

## Latest run: two AMCs (PPFAS + HDFC), hosted mode

**Setup:** after adding HDFC Mutual Fund, the corpus has 33 sources and 1,854 chunks. The dataset grew to 42 questions: the original 31, 9 HDFC questions, plus 2 cross-AMC questions (an AMC with no scheme named, and "which is better: HDFC or Parag Parikh Flexi Cap").

| Metric | Result |
|---|---|
| Classification | 42/42 |
| Retrieval hit@5 | 29/29 |
| Citation accuracy | 29/29 |
| Answer correctness | 31/31 |
| Grounded numbers | 29/29 |
| Refusals without an LLM call | 11/11 |
| Median latency | 1.9 s |

**HDFC answers checked by hand** against the August 2026 HDFC factsheet:

- Expense ratios (Regular / Direct): Flexi Cap 1.27% / 0.67%, Large Cap 1.52% / 0.98%, Liquid 0.30% / 0.20%.
- Flexi Cap exit load: 1.00% within 1 year.
- Benchmarks: Mid Cap NIFTY Midcap 150 (TRI), Liquid CRISIL Liquid Debt A-I.
- ELSS: 3-year lock-in, from the HDFC ELSS KIM.

**Two gaps found and fixed during this run:**

1. The bare "How do I download my capital-gains statement?" pulled HDFC's guide. Now investor-service questions that name no fund house use the primary AMC, consistent with the default scheme.
2. "Which is better: HDFC … or Parag Parikh …?" wasn't recognised as advice; it was only caught by the retrieval gate. Added "which is better / X or Y" advice rules.

**Not answerable:** HDFC riskometer levels are published only as images, so those questions correctly return "I couldn't verify…".

**Memory under Render limits:** the rebuilt image was run under `--memory=512m --cpus=0.1` and used about 363 MB, with no out-of-memory kills.

## Hosted mode results (Groq + fastembed, the Render configuration)

**Setup:** `LLM_PROVIDER=groq` with `llama-3.1-8b-instant`, and `EMBEDDING_PROVIDER=fastembed` with `BAAI/bge-small-en-v1.5` (384-dim). There are 1,513 chunks of about 350 tokens, with neighbour-chunk expansion at answer time.

**How the LLM was run:** the Groq client code path was exercised end to end against an OpenAI-compatible endpoint serving the same Llama 3.1 8B model (Ollama's `/v1`), because no Groq key was available at build time. Re-run `python evaluation/run_eval.py` with a real `GROQ_API_KEY` to confirm against Groq itself.

| Metric | Hosted mode | Local mode (below) |
|---|---|---|
| Classification | 31/31 | 31/31 |
| Retrieval hit@5 | 20/20 | 20/20 |
| Citation accuracy | 20/20 | 20/20 |
| Answer correctness | **21/22** | 22/22 |
| Grounded numbers | 20/20 | 20/20 |
| Refusals without an LLM call | 9/9 | 9/9 |
| Median latency | 1.6 s | 1.9 s |

**Notes on the hosted run:**

- The one miss is Q17, *"Does the ELSS fund have an exit load?"*. It is flaky. Asked on its own, it answers correctly every time ("does not charge an exit load"). In the full sequential run it sometimes returns "I couldn't verify…". That is a safe failure: the assistant declines rather than stating a wrong fact.
- **Fixed during migration:** with the smaller bge-small chunks, the ELSS ₹500 minimum and the first fund manager's name sat in the chunk next to the retrieved one. The fix was to add neighbouring chunks from the same page to the top 3 hits.
- **Relevance separation held with bge-small.** Answerable questions scored 0.86–0.91 and off-topic ones 0.23–0.57, so `RELEVANCE_THRESHOLD=0.70` was kept.
- **Render limits:** the Docker image was run under `--memory=512m --cpus=0.1`. It used about 291 MB with no out-of-memory kills, served the UI and health check, and answered in 3–4 s after a cold first answer of about 13 s.

## Local mode results (Ollama: llama3.1:8b + nomic-embed-text)

| Metric | Result | How it is measured |
|---|---|---|
| Classification accuracy | **31/31** | Predicted `FACTUAL / ADVICE / UNSUPPORTED / PII` matches `expected_classification` |
| Retrieval accuracy (hit@5) | **20/20** | An expected source (`expected_source`) is among the top-5 retrieved chunks |
| Citation accuracy | **20/20** | The single cited source is one of the expected sources |
| Answer correctness | **22/22** | Every fact in `expected_answer_contains` appears in the answer (includes the 2 "couldn't verify" cases) |
| Groundedness (numbers) | **20/20** | Every number in the answer appears on the cited source page |
| Refusal accuracy | **9/9** | Advice, unsupported and PII questions get the safe response and Ollama is **not called** |
| Hallucinated numbers | **0** | Found by the grounding check, plus manual review of all 20 answers |
| Median latency | **1.9 s** | End to end, warm model (first request after start-up about 45 s while the model loads; the backend warms it up at start-up) |

## Methodology

1. **Dataset design.** There are 31 questions:
   - 20 answerable factual questions covering all 5 schemes and every FAQ topic: expense ratio, exit load, minimum SIP, minimum lump sum, lock-in, riskometer, benchmark, objective, fund managers, CAS, capital-gains statement and factsheet location.
   - 2 factual-looking questions the corpus cannot answer: one out-of-domain, and one where the topic matches but the fact is absent.
   - 4 advice, 3 unsupported (prediction or performance) and 2 PII questions.
2. **Ground truth.** Every expected value was checked by hand against the indexed official text, for example the August 2026 factsheet p10: *"Expense Ratio / Regular Plan: 0.48%\* / Direct Plan: 0.14%\*"*. Ground truth was never taken from model output.
3. **Automated scoring.** The runner calls the real pipeline (`answer_pipeline.answer_question`). It separately re-runs retrieval to check hit@k, maps the cited URL back to a registry `source_id`, and checks the answer's numbers against the cited page's stored text. A wrapper around the Ollama client counts LLM calls, which proves refusals never reach the model.
4. **Manual review.** A person read all 20 answered factual responses to check that each claim is supported by the cited page.

## Questions tested (abridged)

| # | Question | Answer (abridged) | Cited source |
|---|---|---|---|
| 1 | What is the expense ratio? | Flexi Cap: 1.05% Regular / 0.53% Direct *(default scheme, disclosed in the UI)* | Factsheet Aug 2026, p. 4 |
| 2 | What is the minimum SIP? | ₹1,000 monthly / ₹3,000 quarterly | Factsheet Aug 2026, p. 2 |
| 6 | What is the ELSS lock-in period? | 3 years | ELSS SID, p. 69 |
| 7 | How do I download my capital-gains statement? | "Request Statements" section (powered by CAMS) on the Investor Desk | PPFAS Investor Desk |
| 11 | Expense ratio of the large cap fund? | 0.48% Regular / 0.14% Direct | Factsheet Aug 2026, p. 10 |
| 12 | Exit load of the liquid fund? | Day 1 0.0070% … Day 7 onwards 0.0000% | Liquid KIM, p. 13 |
| 13 | Benchmark of the liquid fund? | CRISIL Liquid Debt A-I Index | Factsheet Aug 2026, p. 24 |
| 16 | Exit load of the conservative hybrid fund? | 1.00% within 1 year; nil after 1 year | CHF KIM, p. 14 |
| 20 | Who manages the large cap fund? | Rajeev Thakkar, Raunak Onkar, Raj Mehta, … | Factsheet Aug 2026, p. 10 |
| 9, 23–25 | Should I invest…? Which fund is best? | Safe refusal + one official educational source (scheme KIM or AMFI) | KIM / AMFI |
| 10, 26–27 | Returns next year? Outperform? Highest return? | "I can't predict future returns…" + factsheet | Factsheet |
| 28–29 | PAN / folio / email in the question | PII refusal, no retrieval, no LLM call, no logging | — |
| 30–31 | CEO of Tesla? Fund manager's favourite colour? | "I couldn't verify that fact…" (Ollama not called) | — |

The full answers are in `evaluation/results/latest.csv` after a run.

## Retrieval results

Raw cosine similarity alone did **not** separate relevant from irrelevant chunks well with short FAQ questions. For example, the correct ELSS lock-in passage scored 0.63, while "fund manager's favourite colour" also scored 0.63. The retriever therefore uses:

- **A metadata filter** on the detected scheme (`scheme ∈ {scheme, "General"}`), or `scheme = "General"` for investor-service topics (statements, CAS).
- **A second, metadata-filtered query** over the topic's authoritative document type, for example `source_type = "AMC Factsheet"` for expense ratio.
- **Hybrid relevance** = 0.5 × semantic cosine + 0.5 × lexical coverage of the question's key terms. The 0.70 threshold is applied to this score.

Observed separation: answerable questions scored **0.80–0.95**, and unanswerable or off-topic questions **0.26–0.57**.

## Citation accuracy

- The LLM never writes a URL. Any URL, markdown link, "Source:" line or "[1]" reference it produces is stripped. The backend picks one chunk: it combines the retrieval rank with how many of the answer's numbers and words that chunk contains. It then resolves the URL through `data/sources.csv`.
- For values that change monthly (TER, riskometer, NAV, AUM, minimums, managers), only passages from the latest factsheet are used when they are relevant. Before this rule, the large-cap TER question returned the KIM's *regulatory maximum TER slabs* ("2.25%"), which is a real accuracy bug that was fixed.
- PDF citations include the page number, and the UI links with `#page=N`.

## Refusal behaviour

- **ADVICE:** a fixed template. No retrieval and no LLM call. It attaches the scheme's KIM, or the AMFI "Risks in Mutual Funds" page if no scheme is named.
- **UNSUPPORTED:** separate templates for predictions and for performance/ranking questions, with the factsheet attached. No percentages are ever generated.
- **PII:** detected before anything else (PAN, Aadhaar, phone, email, OTP, password, folio, bank account, IFSC, card). The question is not embedded, not sent to Ollama and not logged. Application logs contain only the classification label.
- **Post-generation guard:** advice-shaped phrases ("you should invest", "best fund", "expected return", …) in a generated answer replace it with a safe message. Negated disclaimers such as "does not guarantee returns" are allowed.

## Hallucination checks

- **Numeric grounding:** every number in a generated answer must appear in the retrieved context, or the answer is replaced with "I couldn't verify…". Unit tests cover this, for example a fabricated "0.75%" is rejected.
- **Retrieval gate:** if the best chunk is below the threshold, **Ollama is not called at all**, so pretrained knowledge cannot leak in (questions 30–31).

## Known failures and limitations

1. **Non-numeric embellishment is not caught automatically.** Question 17 (ELSS exit load) answered "Nil", which is correct, but added "This applies to both Regular Plan and Direct Plan". That is true in practice but not stated on the cited page. The grounding check only validates numbers.
2. **Verbose exit-load answers.** Graded exit loads (Liquid Fund, 7 tiers) are listed in full inside one long sentence. This is within the 3-sentence limit but dense.
3. **Default scheme.** A scheme-specific question with no scheme named ("What is the expense ratio?") is answered for the default scheme (`DEFAULT_SCHEME`, Parag Parikh Flexi Cap Fund). The answer and the UI both name the scheme, and users can pick another scheme in the selector.
4. **Rule-based classifier.** It is deterministic and testable, but novel phrasings of advice may be classified as FACTUAL. The post-generation advice guard is the second line of defence.
5. **SEBI sources are not indexed.** `www.sebi.gov.in` timed out during the TLS handshake from the build machine (both curl and httpx). The corpus is therefore PPFAS (AMC) and AMFI only, and the registry already accepts SEBI URLs if they become reachable.
6. **Corpus freshness.** Factsheet data is "as on 31 August 2026". KIMs are dated November/December 2025. Re-run ingestion with `--refresh` after updating `data/sources.csv` to newer documents.
7. **Small evaluation set.** Thirty-one questions show the behaviour but are not a statistically strong benchmark. Results can vary slightly with different model builds.
