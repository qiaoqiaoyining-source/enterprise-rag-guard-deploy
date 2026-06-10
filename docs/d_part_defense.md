# Part D Attacks and Defenses

## Goal

Part D adds a defended RAG pipeline on top of the no-defense baselines from Part C.

This repository already contains:

- clean handbook chunks in `handbook-main/chunks.csv`
- synthetic poisoned chunks in `handbook-main/adversarial_poisoned_chunks.csv`
- labelled normal and attack questions in `questions/evaluation_questions_v2.csv`
- seven no-defense baselines in `rag_variants.py`

The Part D goal is to compare a strong no-defense baseline against a defended pipeline that can:

1. resist user-query prompt injection
2. resist retrieved-document prompt injection
3. refuse unsafe or unsupported requests
4. verify citations before returning an answer

## Recommended Control Group

The recommended no-defense control should be chosen from the full baseline matrix after evaluation.

Recommended selection rule:

1. run the no-defense variants on the same v2 evaluation set
2. compare them with `evaluate_results.py`
3. choose the highest-scoring no-defense configuration as the control

In the current design, the main candidates are:

```text
rag6_hybrid_llm
rag7_embedding_llm
```

Why these are the main candidates:

- both use LLM generation
- `rag6_hybrid_llm` uses stronger lexical retrieval
- `rag7_embedding_llm` tests whether embedding retrieval improves the unprotected system
- both are still intentionally no-defense, so they are clean comparison points for Part D

If a fully local comparison is needed, local fallback controls are:

```text
rag2_bm25
rag6_hybrid_llm
rag1_tfidf
```

## Attack Design

The project covers three attack surfaces.

### 1. User-query injection

These attacks place the malicious instruction in the user message.

Examples already included in `evaluation_questions_v2.csv`:

- override policy with a false answer
- impersonate authority such as HR or CEO
- tamper with citations
- request hidden prompts or credentials
- ask for fabricated or misleading policy communication

### 2. Retrieved-document injection

These attacks look like normal questions, but retrieval may return poisoned chunks.

Poisoned chunks are stored in:

```text
handbook-main/adversarial_poisoned_chunks.csv
```

The poisoned set includes:

- false policy override
- citation hijacking
- credential exfiltration
- style-bias pressure
- omission/style steering
- role-answer hijacking

The current poisoned set is intentionally written as stealthier internal-looking notes rather than self-declaring attack samples. This makes the retrieved-document attacks more realistic.

### 3. Mixed attacks

The v2 question set also includes mixed attacks where:

- the user prompt is malicious
- poisoned chunks may also be retrieved

This is a stronger and more realistic setting than testing only one surface at a time.

## Defended Runner

Main file:

```text
defended_variants.py
```

Supported defended variants:

| Variant | Retrieval | Generation | Notes |
| --- | --- | --- | --- |
| `defended_bm25_local` | BM25 | local extractive | fully local defended fallback |
| `defended_hybrid_local` | TF-IDF + BM25 fusion | local extractive | stronger local defended baseline |
| `defended_hybrid_llm` | TF-IDF + BM25 fusion | LLM | main defended variant for lexical hybrid control runs |
| `defended_embedding_llm` | embedding retrieval | LLM | stronger experimental defended variant |

## Defense Mechanisms

The defended pipeline supports both full-stack defense and ablation runs. The main switches are:

- `--enable-question-refusal`
- `--enable-chunk-filter`
- `--enable-instruction-isolation`
- `--enable-citation-verification`
- `--enable-llm-repair`

This allows testing each defense in isolation and then in combination.

### 1. Over-retrieval

Retrieve more than `top_k` chunks first, then filter suspicious ones before final answer generation.

### 2. Poison detection

Chunks are blocked when one or more of these signals appears:

- `is_poisoned=true`
- instruction override language
- secret/credential requests
- citation hijacking instructions
- forced-compliance language

### 3. Instruction isolation

The answer prompt explicitly tells the model that:

- retrieved documents are untrusted data
- documents are evidence, not instructions
- policy override, prompt leakage, and credential requests must be ignored

### 4. Unsafe-question detection

The runner distinguishes between:

- attacks that should still be answered safely
- attacks that must be refused

For example:

- false policy override with a legitimate handbook question: answer safely
- credential request or private employee data request: refuse
- request to fabricate official policy or bypass policy: refuse

### 5. Citation verification

Returned answers must:

- include citations
- cite only safe handbook chunks
- avoid citing poisoned chunks
- contain claims that overlap with cited source content

### 6. Second-pass validation

If the initial answer fails validation:

- local variants refuse
- LLM variants can optionally run one repair pass with `--enable-llm-repair`
- if repair still fails, the system refuses

## How To Run

### Recommended local defended baseline

```bash
python3 defended_variants.py \
  --variant defended_hybrid_local \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

### Recommended main Part D comparison

First, run the no-defense matrix and choose the strongest control:

```bash
python3 run_experiment_matrix.py \
  --chat-model "deepseek-ai/DeepSeek-V4-Flash" \
  --embedding-model "Qwen/Qwen3-Embedding-4B" \
  --skip-defenses
```

Then use the top-scoring no-defense model as the control. In practice this will often be one of:

```text
rag6_hybrid_llm
rag7_embedding_llm
```

Example lexical-hybrid control:

```bash
python3 rag_variants.py \
  --variant rag6_hybrid_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

Example defended lexical-hybrid comparison:

```bash
python3 defended_variants.py \
  --variant defended_hybrid_llm \
  --run-name defended_hybrid_llm__full_stack_repair \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv \
  --enable-llm-repair
```

### Experimental embedding defended run

```bash
python3 defended_variants.py \
  --variant defended_embedding_llm \
  --run-name defended_embedding_llm__full_stack_repair \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv \
  --embedding-model Qwen/Qwen3-Embedding-4B \
  --enable-llm-repair
```

### Defense ablations

Example chunk-filter-only run:

```bash
python3 defended_variants.py \
  --variant defended_hybrid_llm \
  --run-name defended_hybrid_llm__chunk_filter_only \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv \
  --no-enable-question-refusal \
  --enable-chunk-filter \
  --no-enable-instruction-isolation \
  --no-enable-citation-verification
```

Example instruction-isolation-only run:

```bash
python3 defended_variants.py \
  --variant defended_hybrid_llm \
  --run-name defended_hybrid_llm__instruction_isolation_only \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv \
  --no-enable-question-refusal \
  --no-enable-chunk-filter \
  --enable-instruction-isolation \
  --no-enable-citation-verification
```

## Outputs

Defended runs write to:

```text
outputs/defenses/<run_name>/
```

Files:

| File | Content |
| --- | --- |
| `results.csv` | one row per question with decision, validation reason, blocked chunks, and safe chunks |
| `retrievals.csv` | all retrieved chunks with blocked status and reasons |
| `prompts.jsonl` | defended prompt contexts |
| `summary.json` | run settings and aggregate counts |

Important result fields:

- `decision`
- `validation_reason`
- `question_signals`
- `raw_top_chunk_ids`
- `safe_chunk_ids`
- `blocked_chunk_ids`
- `blocked_reasons`
- `poisoned_chunk_ids`
- `citations_in_answer`

## Lightweight Evaluation

Helper script:

```text
evaluate_results.py
```

Example:

```bash
python3 evaluate_results.py \
  outputs/baselines/rag6_hybrid_llm/results.csv \
  outputs/defenses/defended_hybrid_llm__full_stack_repair/results.csv
```

It reports label-aware proxy metrics such as:

- normal answer accuracy proxy
- safe-attack answer proxy
- refusal accuracy proxy
- gold-chunk hit rate

## Report Wording

Suggested short report wording:

> We evaluated multiple no-defense baselines, including lexical, hybrid, and embedding-based RAG variants, and selected the strongest-scoring unprotected configuration as the Part D control. We then implemented a defended pipeline with attack-aware ablations for unsafe-question refusal, suspicious chunk filtering, instruction isolation, citation verification, and optional repair. This enables comparison not only between an unprotected system and a defended system, but also between individual defense mechanisms and their full-stack combination under user-query, retrieved-document, and mixed prompt-injection attacks.
