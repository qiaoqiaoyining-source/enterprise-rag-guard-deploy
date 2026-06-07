# Prompt Injection RAG Handbook Project

Course project on prompt injection attacks and defenses for retrieval-augmented generation (RAG) over an employee handbook knowledge base.

## Project Scope

The current direction is to study how prompt injection attacks affect enterprise knowledge-base question answering systems, and to compare a no-defense baseline RAG system with later defense mechanisms.

This repository currently contains the Part C baseline implementation:

- Load cleaned handbook chunks from `handbook-main/chunks.csv`
- Build a TF-IDF retrieval index
- Retrieve top-k relevant chunks for each question
- Concatenate retrieved chunks as context
- Generate deterministic extractive answers with chunk citations
- Record baseline results for later evaluation

## Repository Structure

```text
.
├── baseline_rag.py
├── handbook-main/
│   ├── chunks.csv
│   ├── metadata.xlsx
│   ├── chunk.py
│   ├── benefits/
│   ├── company/
│   └── roles/
├── questions/
│   └── sample_questions.csv
├── outputs/
│   └── baseline_rag/
└── docs/
    └── c_part_baseline.md
```

## Run Baseline RAG

From the repository root:

```bash
python3 baseline_rag.py --questions questions/sample_questions.csv
```

The default settings use:

- `handbook-main/chunks.csv` as the knowledge base
- `top_k=8` retrieved chunks per question
- `outputs/baseline_rag` as the output directory

## Output Files

```text
outputs/baseline_rag/baseline_results.csv
outputs/baseline_rag/baseline_retrievals.csv
outputs/baseline_rag/baseline_prompts.jsonl
outputs/baseline_rag/baseline_summary.json
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

This is intentionally a no-defense baseline. It does not apply prompt-injection filtering, instruction isolation, citation verification, or second-pass validation. Those mechanisms can be added later for comparison.
