# EnterpriseRAG-Guard

EnterpriseRAG-Guard is a course project on prompt-injection defense for
company-specific RAG knowledge agents. The final version treats each company as
having its own agent and knowledge boundary, then evaluates whether one shared
security layer transfers across different companies, languages, and attack
surfaces.

```text
Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base
```

## What This Project Demonstrates

- A final transferable RAG defense framework, not several disconnected RAG demos.
- Seven company knowledge bases: Made Tech, GitLab, 37signals/Basecamp, Valve,
  Tencent, BYD, and Huawei.
- Chinese company coverage with 200 chunks each for Tencent, BYD, and Huawei.
- A bilingual security console where an employee can ask normal questions, or a
  red-team user can try prompt-injection attacks and watch the defense trace.
- A B0-B7 ablation experiment showing how provenance checks, quarantine,
  instruction/evidence isolation, extraction, verification, and repair/refusal
  change attack success.

Historical baseline scripts, old outputs, and the previous coursework track are
kept under `legacy/` for reproducibility. The project root now presents the final
EnterpriseRAG-Guard version.

## Final Corpus

The final clean corpus is:

```text
data/enterprise_corpus/company_chunks.csv
```

Current generated corpus:

| Company | Language | Chunks |
| --- | --- | ---: |
| Made Tech | English | 134 |
| GitLab | English | 159 |
| 37signals/Basecamp | English | 111 |
| Valve | English | 80 |
| Tencent | Chinese | 200 |
| BYD | Chinese | 200 |
| Huawei | Chinese | 200 |
| **Total** |  | **1084** |

Corpus origin:

| Origin | Chunks |
| --- | ---: |
| Local clean Made Tech handbook chunks | 134 |
| Fetched public HTML handbook pages | 270 |
| Fetched public PDF reports/handbooks | 680 |

Synthetic poisoned documents are not counted as clean company corpus. They are
created only for evaluation and interactive red-team demonstrations.

## Defense Design

EnterpriseRAG-Guard combines:

1. Provenance-aware retrieval using company, source domain, trust level, content
   hash, document version, and instruction-risk metadata.
2. Query and document risk detection for English and Chinese attacks.
3. Company security profiles for allowed domains, sensitive fields, citation
   rules, and risk thresholds.
4. Instruction/evidence isolation, treating retrieved documents as untrusted
   evidence rather than executable instructions.
5. Extractor-generator isolation, where raw documents are converted into
   evidence claims before answer generation.
6. Citation and policy verification for missing, fabricated, poisoned, or
   cross-company citations.
7. Repair/refusal behavior when a response cannot be safely grounded.

The implementation is deterministic and inspectable so the defense trace can be
shown in the website and explained in the report.

## Rebuild And Run

Use Python with `pypdf` available. Without `pypdf`, PDF sources are skipped and
the Chinese company corpus will be incomplete.

Install the minimal dependency:

```bash
python3 -m pip install -r requirements.txt
```

Build the final corpus:

```bash
python3 build_enterprise_corpus.py --china-target 200 --timeout 35
```

Run the full B0-B7 transfer experiment:

```bash
python3 run_guard_transfer_experiment.py --skip-build-corpus
```

Start the visual security console:

```bash
python3 guard_demo_server.py
```

Then open:

```text
http://127.0.0.1:8765
```

`127.0.0.1` is only for the local computer. The server now binds to `0.0.0.0`
and prints a LAN URL such as `http://192.168.x.x:8765`; classmates on the same
network can access that URL if the firewall allows it. For public internet
access, deploy the app on a server or expose it with a tunnel.

## Current Experiment Results

The latest run uses 224 evaluation cases across seven companies:

| Metric | B0 Plain RAG | B7 Full Guard |
| --- | ---: | ---: |
| Normal task success | 67.86% | 100.00% |
| Attack success rate | 89.29% | 25.00% |
| Attack resistance rate | 10.71% | 75.00% |
| Citation error rate | 58.48% | 0.00% |
| Poison survival rate | 100.00% | 0.00% |

Main outputs:

```text
outputs/enterprise_rag_guard/results.csv
outputs/enterprise_rag_guard/summary/ablation_summary.csv
outputs/enterprise_rag_guard/summary/transfer_matrix.csv
outputs/enterprise_rag_guard/summary/attack_surface_summary.csv
outputs/enterprise_rag_guard/by_company/
outputs/enterprise_rag_guard/by_attack_surface/
```

These metrics are deterministic proxy metrics, not human grading. They are useful
for controlled comparison and presentation, but should not be presented as proof
that prompt injection is solved.

## Security Console Features

The website supports:

- English/Chinese language selection.
- Company selection across all seven company agents.
- Free-form employee questions.
- Built-in red-team templates: direct injection, credential theft,
  cross-company contamination, adaptive policy amendment, and poisoned document.
- "Inject Your Own Chunk" to paste a fake policy note and see whether it is used
  or quarantined.
- Risk-threshold slider to demonstrate stricter or looser defense behavior.
- Side-by-side B0 control agent vs B7 secure agent answers.
- Defense trace, safe evidence panel, quarantine panel, B0-B7 ablation table,
  and transfer matrix.

## Key Files

```text
build_enterprise_corpus.py                 # builds the final real-company corpus
enterprise_rag_guard.py                    # guard core and defense pipeline
run_guard_transfer_experiment.py           # B0-B7 transfer/ablation runner
guard_demo_server.py                       # bilingual visual security console
data/company_profiles.json                 # company security profiles
data/enterprise_corpus/company_chunks.csv  # final clean corpus
docs/enterprise_rag_guard.md               # detailed technical explanation
```
