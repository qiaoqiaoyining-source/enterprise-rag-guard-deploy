# EnterpriseRAG-Guard

## Positioning

The upgraded project is now:

```text
EnterpriseRAG-Guard: A Transferable Defense Framework for Company-Specific Knowledge Agents
```

The normal deployment model is not one mixed cross-company agent. Each company
keeps its own knowledge base and agent boundary:

```text
Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base
```

The shared contribution is the transferable guard layer.

## Technical Contributions

### 1. Provenance-Aware Secure Retrieval

Each chunk carries company and source metadata:

- `company_id`
- `source_url`
- `source_host`
- `trust_level`
- `content_hash`
- `document_version`
- `effective_date`
- `instruction_risk_score`

Retrieval no longer ranks only by relevance. It combines relevance, source
credibility, company consistency, and attack risk. High-risk or wrong-company
chunks are quarantined before generation.

### 2. Instruction-Evidence Isolation

The guard treats retrieved text as untrusted evidence, not instructions. The
pipeline separates:

- trusted system/task intent;
- user request;
- untrusted evidence;
- extracted factual claims.

This is a lightweight implementation inspired by structured instruction/data
separation and document spotlighting.

### 3. Extractor-Generator Isolation

The generator does not need to directly use raw retrieved documents. The guard
first extracts claim-like evidence records:

```json
{
  "claim": "...",
  "company_id": "gitlab",
  "chunk_id": "GL0149",
  "evidence_span": "..."
}
```

Suspicious spans are marked as embedded instructions and are not passed as facts.

### 4. Deterministic Policy Engine

Each company has a security profile:

- allowed source domains;
- sensitive fields;
- allowed tasks;
- citation requirements;
- company-scope requirements;
- risk threshold.

The universal defense code stays the same; only the company profile changes.

### 5. Citation and Policy Verification

Final answers are checked for:

- missing citations;
- fabricated citations;
- poisoned citations;
- cross-company citations;
- unsafe content in the final answer.

If verification fails, the full guard repairs once or refuses.

## Dataset

The current generated corpus has 500 clean chunks:

| Company | Chunks |
| --- | ---: |
| Made Tech | 146 |
| GitLab | 150 |
| 37signals/Basecamp | 125 |
| Valve | 79 |

The builder is:

```bash
python3 build_multi_company_corpus.py --target-total 500
```

It uses local Made Tech chunks, public GitLab handbook pages, public Basecamp
handbook pages, and Valve's public employee handbook PDF when PDF dependencies
are available. If a source cannot be fetched, fallback seed chunks are explicitly
marked as `offline_seed`.

## Transfer Experiment

Run:

```bash
python3 run_guard_transfer_experiment.py --skip-build-corpus
```

This evaluates eight ablation groups:

| Group | Defense |
| --- | --- |
| B0 | Plain RAG |
| B1 | System prompt guardrail |
| B2 | Query/chunk detector |
| B3 | Provenance-aware retrieval |
| B4 | Structured spotlighting |
| B5 | Extractor-generator isolation |
| B6 | Citation/policy verifier |
| B7 | Full guard with repair/refuse |

The balanced evaluation set has 128 questions across four companies and five
attack surfaces: normal, direct user injection, credential extraction,
cross-company contamination, adaptive stealth amendment, and retrieved-document
poisoning.

Current local summary:

| System | Normal task success | Attack success rate | Citation error | Poison survival |
| --- | ---: | ---: | ---: | ---: |
| B0 plain RAG | 81.25% | 90.62% | 58.59% | 100.00% |
| B7 full guard | 100.00% | 25.00% | 0.00% | 0.00% |

Outputs:

```text
outputs/enterprise_rag_guard/results.csv
outputs/enterprise_rag_guard/summary/ablation_summary.csv
outputs/enterprise_rag_guard/summary/transfer_summary.json
outputs/enterprise_rag_guard/by_company/
```

## Visual Demo

Run:

```bash
python3 guard_demo_server.py
```

Open:

```text
http://127.0.0.1:8765
```

The demo includes:

- employee portal;
- red-team attack templates;
- control-vs-secure comparison;
- defense trace;
- safe evidence and quarantine panels;
- transfer/security metrics.

## Limitations

- The evaluation uses deterministic proxy metrics, not human grading.
- Some public sources may be unavailable during rebuilds; fallback chunks are
  clearly marked.
- The lightweight extractor and verifier are interpretable but not equivalent to
  a trained entailment model.
- The system should be presented as a practical defense framework, not a claim
  that prompt injection is solved.
