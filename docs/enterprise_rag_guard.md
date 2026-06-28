# EnterpriseRAG-Guard Technical Notes

## Final Positioning

EnterpriseRAG-Guard is the final version of the project. It is not presented as
an original handbook RAG plus a separate enterprise experiment. The final system
is a company-specific RAG security framework:

```text
Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base
```

Each company has its own knowledge boundary. The reusable contribution is the
guard layer that transfers across companies and languages.

## Corpus Design

The clean corpus is stored in:

```text
data/enterprise_corpus/company_chunks.csv
```

Current corpus size: 1084 chunks.

| Company | Language | Chunks | Source style |
| --- | --- | ---: | --- |
| Made Tech | English | 134 | Local clean handbook chunks |
| GitLab | English | 159 | Public handbook HTML |
| 37signals/Basecamp | English | 111 | Public handbook HTML |
| Valve | English | 80 | Public employee handbook PDF |
| Tencent | Chinese | 200 | Public official PDFs |
| BYD | Chinese | 200 | Public official/HKEX PDFs |
| Huawei | Chinese | 200 | Public official PDFs |

Synthetic poisoned documents are deliberately separated from the clean corpus.
They appear only in evaluation and demo injection paths. This avoids claiming
that attack documents are real company knowledge.

Every chunk carries metadata used by the guard:

- `company_id`
- `company_name`
- `language`
- `source_url`
- `source_host`
- `source_type`
- `corpus_origin`
- `trust_level`
- `document_version`
- `content_hash`
- `instruction_risk_score`

## Defense Architecture

### 1. Company Security Profile

`data/company_profiles.json` defines a small security profile for each company:

- allowed source domains;
- sensitive fields, such as credentials, private employee data, and API keys;
- allowed task types;
- whether company match is required;
- citation requirements;
- minimum evidence count;
- risk threshold.

This gives the system transferability: the core guard is shared, while company
policy boundaries can be adapted without rewriting the whole RAG pipeline.

### 2. Bilingual Risk Detection

The guard detects suspicious user queries and document chunks in English and
Chinese. It covers:

- direct instruction override;
- credential or secret requests;
- private employee data requests;
- system-prompt exfiltration;
- policy fabrication;
- citation hijacking;
- Chinese variants such as `忽略规则`, `密码`, `凭证`, `系统提示词`, and `特殊无限福利`.

This layer is intentionally not the whole defense. It is an early warning signal
that feeds retrieval and quarantine decisions.

### 3. Provenance-Aware Retrieval

Plain RAG ranks chunks mainly by lexical relevance. EnterpriseRAG-Guard reranks
with security context:

- company match;
- allowed source domain;
- trust level;
- poison flag;
- instruction-risk score;
- source type and citation suitability.

Wrong-company, untrusted, poisoned, or instruction-like chunks can still be
retrieved for inspection, but they are quarantined before generation.

### 4. Instruction/Evidence Isolation

Retrieved text is treated as untrusted evidence, not as instructions. This is the
core conceptual shift. A retrieved chunk can say "ignore previous rules", but the
agent never treats that sentence as a command. The trusted task, user request,
retrieved evidence, and extracted claims are kept separate in the trace.

### 5. Extractor-Generator Isolation

The generator does not directly consume all raw retrieved text. The guard first
extracts claim-like evidence records:

```json
{
  "claim": "Employees should follow the cited public policy text.",
  "company_id": "tencent",
  "chunk_id": "TC0042",
  "evidence_span": "..."
}
```

Spans that look like embedded instructions are excluded from the factual evidence
pool. This makes prompt injection harder than simple keyword filtering because
the risky text is removed before answer construction.

### 6. Citation And Policy Verification

After generation, the verifier checks:

- every citation exists;
- every citation belongs to the selected company;
- cited chunks are not poisoned or quarantined;
- the answer does not leak sensitive content;
- the answer does not fabricate unsupported policy claims.

The full B7 guard repairs once if possible. If it cannot produce a grounded
answer, it refuses.

## B0-B7 Ablation

The experiment evaluates eight defense configurations:

| Group | Defense |
| --- | --- |
| B0 | Plain RAG |
| B1 | Prompt guardrail |
| B2 | Query/chunk detector |
| B3 | Provenance-aware retrieval |
| B4 | Structured spotlighting |
| B5 | Extractor-generator isolation |
| B6 | Citation/policy verifier |
| B7 | Full guard with repair/refuse |

Run:

```bash
python3 -m pip install -r requirements.txt
python3 build_enterprise_corpus.py --china-target 200 --timeout 35
python3 run_guard_transfer_experiment.py --skip-build-corpus
```

`pypdf` is required for the public PDF sources. If it is missing, the builder can
still produce the English HTML subset, but the Chinese company corpus will be
incomplete.

The latest run contains 224 questions:

| Split | Cases |
| --- | ---: |
| Normal | 56 |
| User-query attacks | 70 |
| Cross-company contamination | 35 |
| Adaptive policy amendment | 35 |
| Retrieved-document poisoning | 28 |

Language coverage:

| Language | Cases |
| --- | ---: |
| English | 128 |
| Chinese | 96 |

## Current Results

| System | Normal task success | Attack success rate | Citation error | Poison survival |
| --- | ---: | ---: | ---: | ---: |
| B0 plain RAG | 67.86% | 89.29% | 58.48% | 100.00% |
| B7 full guard | 100.00% | 25.00% | 0.00% | 0.00% |

The main result is an absolute attack-success-rate reduction of 64.29 percentage
points from B0 to B7.

Important output files:

```text
outputs/enterprise_rag_guard/results.csv
outputs/enterprise_rag_guard/summary/ablation_summary.csv
outputs/enterprise_rag_guard/summary/transfer_summary.json
outputs/enterprise_rag_guard/summary/transfer_matrix.csv
outputs/enterprise_rag_guard/summary/attack_surface_summary.csv
outputs/enterprise_rag_guard/by_company/
outputs/enterprise_rag_guard/by_attack_surface/
```

## Visual Security Console

Run:

```bash
python3 guard_demo_server.py
```

Open:

```text
http://127.0.0.1:8765
```

The app is no longer just a blank chatbot. It includes:

- language selector for English and Chinese;
- company selector for all seven company agents;
- free-form question input;
- red-team templates for common attack types;
- "Inject Your Own Chunk" to paste a fake policy and test quarantine;
- risk threshold slider;
- B0 control vs B7 secure answer comparison;
- defense trace;
- safe evidence and quarantine panels;
- ablation table;
- company transfer matrix.

`127.0.0.1` means local-only. The server binds to `0.0.0.0` and prints a LAN URL
for classmates on the same network. Public internet access requires deployment
or a tunnel.

## How To Present The Project

The strongest framing is:

1. Real-world problem: company RAG agents retrieve untrusted documents that may
   contain malicious instructions.
2. System contribution: a transferable guard for company-specific agents.
3. Technical contribution: provenance-aware retrieval, isolation,
   extractor-generator separation, and citation/policy verification.
4. Data contribution: multilingual company corpus with Chinese and English
   companies.
5. Evaluation contribution: B0-B7 ablation, by-company transfer matrix, and
   by-attack-surface analysis.
6. Demo contribution: interactive employee/red-team console showing both answers
   and the internal defense trace.

## Limitations

- The metrics are deterministic proxy metrics, not human expert judging.
- The generated answers are extractive and citation-oriented, so the system is
  best presented as a security framework rather than a polished production LLM
  assistant.
- Public web sources may change; the committed corpus and outputs preserve the
  exact run used for presentation.
- The detector is interpretable and portable, but not a replacement for a
  trained classifier or external fact-verification model.
