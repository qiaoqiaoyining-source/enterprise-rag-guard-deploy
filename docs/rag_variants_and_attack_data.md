# RAG Variants and Attack Data

This project now contains local baselines, LLM baselines, and two attack surfaces for prompt-injection experiments.

## Attack surfaces

### 1. User-query attacks

The malicious instruction is inside the user's question, for example asking the model to ignore the handbook or fabricate a policy. These questions are marked with:

```text
attack_surface=user_query
```

### 2. Retrieved-document attacks

The user question can look normal, but the corpus includes synthetic poisoned chunks that may be retrieved as context. These questions are marked with:

```text
attack_surface=retrieved_document
```

The synthetic poisoned chunks are stored in:

```text
handbook-main/adversarial_poisoned_chunks.csv
```

They are not real handbook policy. They are test-only adversarial data.

## Attack strength

Questions and poisoned chunks use three attack strengths:

| Strength | Meaning |
| --- | --- |
| `low` | Mild style, priority, or omission pressure. Usually does not directly invent policy. |
| `medium` | Direct false-policy override or misleading instruction. |
| `high` | System/developer-role impersonation, exfiltration, credential, citation hijacking, or severe policy fabrication. |

For user-query attacks, strength describes the malicious user instruction. For retrieved-document attacks, strength describes the poisoned document content expected to be retrieved.

## Question set

The v2 evaluation question set is:

```text
questions/evaluation_questions_v2.csv
```

Important fields:

| Field | Purpose |
| --- | --- |
| `question_id` | Stable ID. Normal questions use `N`, user attacks use `U`, document attacks use `D`, mixed attacks use `M`. |
| `split` | `normal` or `attack`. |
| `category` | Topic area such as benefits, company, roles, security, or privacy. |
| `attack_surface` | `none`, `user_query`, `retrieved_document`, or `mixed`. |
| `attack_type` | Specific attack pattern. |
| `attack_strength` | `none`, `low`, `medium`, or `high`. |
| `expected_answer` | Gold answer or expected safe behavior. |
| `gold_chunk_ids` | Correct handbook evidence. Poisoned chunks should not be treated as gold citations. |
| `should_refuse` | Whether the request should be refused. |

## RAG variants

The runner is:

```text
rag_variants.py
```

It intentionally does not implement defenses. It only provides alternative baseline variants.

| Variant | Retrieval | Generation | Notes |
| --- | --- | --- | --- |
| `rag1_tfidf` | TF-IDF | Extractive | Original-style local baseline. |
| `rag2_bm25` | BM25 | Enhanced extractive | Strong local no-API lexical baseline. |
| `rag3_llm_only` | None | LLM | Pure LLM comparison; not RAG because no handbook retrieval is used. |
| `rag4_tfidf_llm` | TF-IDF | LLM | Tests original retrieval with stronger generation. |
| `rag5_bm25_llm` | BM25 | LLM | Tests BM25 retrieval with stronger generation. |
| `rag6_hybrid_llm` | TF-IDF + BM25 score fusion | LLM | Stronger lexical hybrid RAG baseline. |

### Local variants

Run original-style TF-IDF extractive:

```bash
python3 rag_variants.py \
  --variant rag1_tfidf \
  --questions questions/evaluation_questions_v2.csv
```

Run BM25 extractive with poisoned chunks included:

```bash
python3 rag_variants.py \
  --variant rag2_bm25 \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

### LLM variants

The API uses ModelVerse/OpenAI-compatible Chat Completions. Defaults are:

```text
base_url = https://api.modelverse.cn/v1
model = claude-opus-4-7
api key env = MODELVERS_API_KEY
```

Set your API key locally:

```bash
export MODELVERS_API_KEY="your_api_key"
```

Run pure LLM, without retrieval:

```bash
python3 rag_variants.py \
  --variant rag3_llm_only \
  --questions questions/evaluation_questions_v2.csv
```

Run TF-IDF + LLM:

```bash
python3 rag_variants.py \
  --variant rag4_tfidf_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

Run BM25 + LLM:

```bash
python3 rag_variants.py \
  --variant rag5_bm25_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

Run Hybrid + LLM:

```bash
python3 rag_variants.py \
  --variant rag6_hybrid_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

You can override the endpoint and model directly:

```bash
python3 rag_variants.py \
  --variant rag5_bm25_llm \
  --base-url "https://api.modelverse.cn/v1" \
  --model "claude-opus-4-7" \
  --questions questions/evaluation_questions_v2.csv
```

Do not commit API keys to the repository.

## Outputs

Each variant writes to:

```text
outputs/rag_variants/<variant>/
```

Files:

| File | Content |
| --- | --- |
| `results.csv` | One row per question, including original labels, answer, top chunks, poisoned chunks, and context length. |
| `retrievals.csv` | One row per retrieved chunk. |
| `prompts.jsonl` | Full prompt-like context sent to the generator. |
| `summary.json` | Run settings and corpus counts. |

## Scope note

These variants are intentionally no-defense baselines. Defensive filtering, refusal classifiers, prompt hardening, and automated scoring are separate project parts and are not implemented here.
