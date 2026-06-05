# Part C Baseline RAG

## Goal

This part builds the no-defense RAG baseline for the employee handbook dataset. It reads the cleaned chunk table, retrieves relevant chunks for each question, concatenates the retrieved chunks into context, generates an answer, and records baseline results for later comparison with defended systems.

## Input Data

Main input:

```text
handbook-main/chunks.csv
```

The baseline uses these fields:

| Field | Usage |
| --- | --- |
| `chunk_id` | Citation and retrieval identifier |
| `doc_id` | Original document identifier |
| `file_name` | Source markdown file |
| `source_type` | Data category: roles, benefits, company |
| `section_path` | Heading path for source traceability |
| `text` | Chunk content used for retrieval and answering |

The current parsed dataset contains 146 chunks:

| Category | Chunks |
| --- | ---: |
| roles | 74 |
| benefits | 63 |
| company | 9 |

## Baseline Method

The baseline intentionally applies no prompt-injection defense. It does not filter malicious instructions, isolate system and document instructions, verify citations, or run second-pass validation.

Pipeline:

1. Load `chunks.csv`.
2. Build a TF-IDF vector index over `source_type`, `section_path`, and `text`.
3. For each question, compute cosine similarity and retrieve the top 8 chunks by default.
4. Concatenate retrieved chunks into a context block with chunk metadata.
5. Generate a deterministic extractive answer by selecting the most question-relevant sentences from retrieved chunks. The sentence scorer also uses section headings and a small fixed query expansion for common policy terms such as limit, insurance, holiday, and request.
6. Record answer, retrieved chunks, similarity scores, and full prompt context.

The extractive generator is used so the baseline can run locally without API keys or network access. If an LLM API is available later, the generation step can be replaced while keeping the same retrieval and logging format.

## How To Run

Run with the included sample questions:

```bash
python3 baseline_rag.py --questions questions/sample_questions.csv
```

Run with custom questions:

```bash
python3 baseline_rag.py --questions path/to/questions.csv
```

The custom CSV needs a `question` column. A plain text file with one question per line also works.

Useful options:

```bash
python3 baseline_rag.py \
  --chunks handbook-main/chunks.csv \
  --questions questions/sample_questions.csv \
  --outdir outputs/baseline_rag \
  --top-k 8 \
  --max-context-chars 6000
```

## Output Files

Default output directory:

```text
outputs/baseline_rag
```

Files:

| File | Content |
| --- | --- |
| `baseline_results.csv` | One row per question, including answer, top chunk IDs, scores, and context length |
| `baseline_retrievals.csv` | One row per retrieved chunk, including rank, score, source metadata, and text |
| `baseline_prompts.jsonl` | Full prompt-like context for each question |
| `baseline_summary.json` | Dataset size, question count, top-k setting, and baseline notes |

## Report Wording

For the project report, this part can be described as:

> We implemented a no-defense RAG baseline over the cleaned handbook chunks. The system builds a TF-IDF retrieval index over chunk text and metadata, retrieves the top 8 most similar chunks for each query using cosine similarity, concatenates retrieved chunks as context, and generates an extractive answer with chunk citations. This baseline intentionally does not include prompt-injection filtering, instruction separation, citation verification, or secondary validation, so it provides the comparison point for later defense mechanisms.
