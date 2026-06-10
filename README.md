[README.md](https://github.com/user-attachments/files/28787495/README.md)
# Prompt Injection RAG Handbook Project

Course project on prompt injection attacks and defenses for retrieval-augmented generation (RAG) over an employee handbook knowledge base.

## Project Scope

This project explores how prompt injection can affect retrieval-augmented generation systems that answer questions over an employee handbook. It includes clean handbook chunks, synthetic poisoned chunks for attack testing, a family of no-defense baselines, labelled question sets for smoke tests and evaluation, and both lexical and LLM-backed variants.

Current version summary:

- `baseline_rag.py` is the historical single baseline entry point.
- `rag_variants.py` is the main runner for the seven no-defense baseline configurations.
- `defended_variants.py` is the main runner for Part D defended configurations.
- `evaluate_results.py` provides a lightweight proxy evaluator for result CSV files.
- `evaluate_part_e.py` produces final safety/utility metrics, attack breakdowns, and charts.
- `run_experiment_matrix.py` runs the baseline matrix, selects the strongest no-defense control, and runs defense ablations.
- `outputs/baselines/` is the main results directory for direct baseline runs.
- `outputs/defenses/` is the results directory for defended runs.
- `outputs/experiment_matrix/` stores matrix summaries across baselines and defenses.
- `outputs/baseline_rag/` is kept as historical output from the original baseline script.

## Repository Structure

```text
.
├── baseline_rag.py
├── rag_variants.py
├── rag_demo_server.py
├── defended_variants.py
├── evaluate_results.py
├── run_experiment_matrix.py
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
    ├── d_part_defense.md
    ├── final_project_report.md
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

The poisoned chunks are not real handbook policy. They are test-only attack data with `is_poisoned`, `poison_strength`, and `attack_goal` fields. The current version is written as stealthier internal-looking notes so that retrieved-document attacks are less self-revealing and closer to realistic poisoning.

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

The newer runner provides seven no-defense variants:

| Variant | Retrieval | Generation | Purpose |
| --- | --- | --- | --- |
| `rag1_tfidf` | TF-IDF | Extractive | Preserves the original local baseline idea. |
| `rag2_bm25` | BM25 | Enhanced extractive | Stronger no-API local baseline. |
| `rag3_llm_only` | None | LLM | Pure LLM comparison without retrieval; not a RAG system. |
| `rag4_tfidf_llm` | TF-IDF | LLM | Tests whether TF-IDF retrieval plus LLM generation is stronger than extractive TF-IDF. |
| `rag5_bm25_llm` | BM25 | LLM | BM25 retrieval plus LLM generation. |
| `rag6_hybrid_llm` | TF-IDF + BM25 score fusion | LLM | Stronger lexical hybrid RAG baseline. |
| `rag7_embedding_llm` | Embedding retrieval | LLM | Dense retrieval + LLM baseline for comparison against lexical RAG. |

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

The LLM variants use an OpenAI-compatible Chat Completions API. This project can be used with any compatible provider, including SiliconFlow.

Recommended environment variables:

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_API_BASE="https://api.siliconflow.cn/v1"
export CHAT_MODEL="deepseek-ai/DeepSeek-V4-Flash"
export EMBEDDING_MODEL="Qwen/Qwen3-Embedding-4B"
```

The base URL is the API endpoint, not the cloud console URL. For SiliconFlow the correct API base is:

```text
https://api.siliconflow.cn/v1
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

Run Embedding + LLM:

```bash
python3 rag_variants.py \
  --variant rag7_embedding_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv \
  --embedding-model Qwen/Qwen3-Embedding-4B
```

Practical note for long LLM-backed runs: more stable settings are often:

```bash
--llm-timeout 300 --llm-retries 2 --max-tokens 120 --max-context-chars 2200 --top-k 3
```

## Part D Defenses

The recommended no-defense control for Part D should be selected from the evaluated no-defense baselines rather than fixed in advance.

Main candidates:

```text
rag6_hybrid_llm
rag7_embedding_llm
```

Main defended runner:

```text
defended_variants.py
```

Supported defended variants:

| Variant | Retrieval | Generation | Purpose |
| --- | --- | --- | --- |
| `defended_bm25_local` | BM25 | local extractive | fully local defended baseline |
| `defended_hybrid_local` | TF-IDF + BM25 fusion | local extractive | stronger local defended baseline |
| `defended_hybrid_llm` | TF-IDF + BM25 fusion | LLM | main defended comparison against lexical hybrid control runs |
| `defended_embedding_llm` | embedding retrieval | LLM | stronger experimental defended variant |

The defended runner also supports ablation switches:

- `--enable-question-refusal`
- `--enable-chunk-filter`
- `--enable-instruction-isolation`
- `--enable-citation-verification`
- `--enable-llm-repair`

Run the main local defended baseline:

```bash
python3 defended_variants.py \
  --variant defended_hybrid_local \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

Run the main defended LLM baseline:

```bash
python3 defended_variants.py \
  --variant defended_hybrid_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv \
  --enable-llm-repair
```

Run the experimental defended embedding variant:

```bash
python3 defended_variants.py \
  --variant defended_embedding_llm \
  --questions questions/evaluation_questions_v2.csv \
  --extra-chunks handbook-main/adversarial_poisoned_chunks.csv
```

Run the full experiment matrix:

```bash
python3 run_experiment_matrix.py \
  --chat-model "deepseek-ai/DeepSeek-V4-Flash" \
  --embedding-model "Qwen/Qwen3-Embedding-4B"
```

This script:

1. runs all seven no-defense baselines
2. scores them with `evaluate_results.py`
3. selects the strongest no-defense control
4. runs defense ablations and full-stack defense
5. writes summaries to `outputs/experiment_matrix/summary/`

If baseline results already exist, reuse them without spending API credit again:

```bash
python3 run_experiment_matrix.py \
  --reuse-baselines \
  --skip-missing-baselines \
  --skip-defenses
```

Detailed design notes are in:

```text
docs/d_part_defense.md
```

The integrated Part E report is in:

```text
docs/final_project_report.md
```

The final editable presentation is in:

```text
deliverables/prompt-injection-rag-final.pptx
```

Do not commit API keys to the repository.

## Output Files

The original baseline writes to:

```text
outputs/baseline_rag/
```

The direct baseline configurations write to:

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
outputs/baselines/rag7_embedding_llm/
```

Defended configurations write to:

```text
outputs/defenses/<run_name>/
```

The experiment matrix helper writes to:

```text
outputs/experiment_matrix/
```

Key matrix summaries:

- `outputs/experiment_matrix/summary/baseline_scores.csv`
- `outputs/experiment_matrix/summary/defense_scores.csv`
- `outputs/experiment_matrix/summary/recommendation.json`
- `outputs/experiment_matrix/summary/final_summary.json`

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

The `rag*` family is intentionally no-defense. Prompt-injection filtering, instruction isolation, citation verification, question refusal, and second-pass repair are all implemented separately in `defended_variants.py`.

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
