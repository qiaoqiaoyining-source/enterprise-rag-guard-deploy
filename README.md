# Prompt Injection RAG Handbook Project

Course project on prompt injection attacks and defenses for retrieval-augmented generation (RAG) over an employee handbook knowledge base.

## Project Scope

This project explores how prompt injection can affect retrieval-augmented generation systems that answer questions over an employee handbook. It includes clean handbook chunks, synthetic poisoned chunks for attack testing, a family of no-defense baselines, labelled question sets for smoke tests and evaluation, and both lexical and LLM-backed variants.

Current version summary:

- `baseline_rag.py` is the historical single baseline entry point.
- `rag_variants.py` is the main runner for the six no-defense baseline configurations.
- `outputs/baselines/` is the main results directory for the six baseline runs.
- `outputs/baseline_rag/` is kept as historical output from the original baseline script.

## Repository Structure

```text
.
├── baseline_rag.py
├── rag_variants.py
├── rag_demo_server.py
├── handbook-main/
│   ├── chunks.csv
│   ├── adversarial_poisoned_chunks.csv
│   ├── metadata.xlsx
│   ├── chunk.py
│   ├── benefits/
│   ├── company/
│   └── roles/
├── questions/
│   ├── sample_questions.csv
│   ├── evaluation_questions.csv
│   ├── evaluation_questions_v2.csv
│   └── README.md
├── outputs/
│   ├── baseline_rag/          # historical output from baseline_rag.py
│   └── baselines/             # current output root for the six baseline configurations
└── docs/
    ├── c_part_baseline.md
    └── rag_variants_and_attack_data.md
```

## Data

Main clean corpus:

```text
handbook-main/chunks.csv
```

Synthetic poisoned corpus for retrieved-document prompt injection tests:

```text
handbook-main/adversarial_poisoned_chunks.csv
```

The poisoned chunks are not real handbook policy. They are test-only attack data with `is_poisoned`, `poison_strength`, and `attack_goal` fields.

## Question Sets

Quick smoke-test questions:

```text
questions/sample_questions.csv
```

Labelled v2 evaluation questions:

```text
questions/evaluation_questions_v2.csv
```

The v2 question set includes normal questions, user-query attacks, retrieved-document attacks, mixed attacks, gold answers, gold chunk IDs, refusal labels, attack surfaces, and attack strengths.

## Original Baseline RAG

The original Part C baseline remains available:

```bash
python3 baseline_rag.py --questions questions/sample_questions.csv
```

It uses TF-IDF retrieval and deterministic extractive answer generation.

## RAG Variants

The newer runner provides three no-defense variants:

| Variant | Retrieval | Generation | Purpose |
| --- | --- | --- | --- |
| `rag1_tfidf` | TF-IDF | Extractive | Preserves the original local baseline idea. |
| `rag2_bm25` | BM25 | Enhanced extractive | Stronger no-API local baseline. |
| `rag3_llm_only` | None | LLM | Pure LLM comparison without retrieval; not a RAG system. |
| `rag4_tfidf_llm` | TF-IDF | LLM | Tests whether TF-IDF retrieval plus LLM generation is stronger than extractive TF-IDF. |
| `rag5_bm25_llm` | BM25 | LLM | BM25 retrieval plus LLM generation. |
| `rag6_hybrid_llm` | TF-IDF + BM25 score fusion | LLM | Stronger lexical hybrid RAG baseline. |

Run the original-style variant on the v2 question set:

```bash
python3 rag_variants.py \
  --variant rag1_tfidf \
  --questions questions/evaluation_questions_v2.csv
```

Run the BM25 variant with clean handbook chunks only:

```bash
python3 rag_variants.py \
  --variant rag2_bm25 \
  --questions questions/evaluation_questions_v2.csv
```

Run the BM25 variant with poisoned chunks included:

```bash
python3 rag_variants.py \
  --variant rag2_bm25 \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

## LLM Setup

The LLM variants use an OpenAI-compatible Chat Completions API. By default this project now connects directly to DeepSeek instead of ModelVerse.

Recommended environment variables:

```bash
export OPENAI_API_KEY="your_deepseek_api_key"
export OPENAI_API_BASE="https://api.deepseek.com/v1"
export CHAT_MODEL="deepseek/deepseek-v4-pro"
export CHAT_STREAM="False"
export CHAT_TEMPERATURE="1"
export SYSTEM_PROMPT_ROLE="user"
export MAX_RETRY="1"
export RETRY_WAIT_SECONDS="5"
export TIMEOUT_FAIL_LIMIT="100"
```

Default settings in `rag_variants.py` are now aligned with that direct DeepSeek setup:

```text
base_url = https://api.deepseek.com/v1
model = deepseek/deepseek-v4-pro
api key env = OPENAI_API_KEY
```

If you want to override them for a specific run, you can still pass flags such as `--base-url`, `--model`, or `--api-key-env`.

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

Run Hybrid TF-IDF + BM25 + LLM:

```bash
python3 rag_variants.py \
  --variant rag6_hybrid_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

Do not commit API keys to the repository.

## Output Files

The original baseline writes to:

```text
outputs/baseline_rag/
```

The six current baseline configurations write to:

```text
outputs/baselines/<variant>/
```

So the current recommended layout is:

```text
outputs/baselines/rag1_tfidf/
outputs/baselines/rag2_bm25/
outputs/baselines/rag3_llm_only/
outputs/baselines/rag4_tfidf_llm/
outputs/baselines/rag5_bm25_llm/
outputs/baselines/rag6_hybrid_llm/
```

Each new variant produces:

```text
results.csv
retrievals.csv
prompts.jsonl
summary.json
```

## Run Local Web Demo

Start the local demo server:

```bash
python3 rag_demo_server.py
```

Then open:

```text
http://127.0.0.1:8000
```

The page lets you enter a question, run the no-defense baseline RAG pipeline, and inspect the answer, retrieved chunks, similarity scores, context, and prompt.

## Notes

All current RAG configurations are intentionally no-defense baselines. They do not apply prompt-injection filtering, instruction isolation, citation verification, or second-pass validation. Those mechanisms are separate project parts.

For GitHub, keep API keys and personal credentials out of the repository. Use your local shell environment or a private `.env` file that is excluded from version control.

## How to upload to the team GitHub repository

If your teammate created the repository and added you as a collaborator, the usual workflow is:

1. Clone the repository locally if you have not already.

```bash
git clone <repo-url>
cd <repo-folder>
```

2. Create a new branch for your work.

```bash
git checkout -b feature/your-change-name
```

3. Make your changes, test them locally, then stage and commit.

```bash
git add .
git commit -m "describe your change"
```

4. Push the branch to the shared GitHub repository.

```bash
git push -u origin feature/your-change-name
```

5. Open a pull request on GitHub from your branch into the main branch.

If you do not have write access, you will need your teammate to grant it or you may need to fork the repository and open a PR from your fork. If you want, I can also help you write the exact git commands for your current branch and explain how to make the PR.
