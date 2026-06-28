#!/usr/bin/env python3
"""No-defense baseline RAG over handbook chunks.

This script intentionally does not apply prompt-injection defenses. It reads the
provided chunk table, builds a TF-IDF retrieval index, concatenates retrieved
chunks as context, and produces an extractive answer with source citations.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DEFAULT_QUESTIONS = [
    "What is the Cycle to Work scheme and what is the spending limit?",
    "How can employees request flexible working?",
    "What private medical insurance does the company provide?",
    "What is the holiday allowance policy?",
    "What does an Associate Software Engineer do?",
    "What are the responsibilities of a Lead Data Engineer?",
    "What is the purpose of the welcome pack?",
    "What benefits are available to support hybrid working?",
]


@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    score: float
    chunk_id: str
    doc_id: str
    file_name: str
    source_type: str
    section_path: str
    text: str


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_chunks(path: Path) -> pd.DataFrame:
    chunks = pd.read_csv(path, encoding="utf-8-sig")
    required = {
        "chunk_id",
        "doc_id",
        "file_name",
        "source_type",
        "section_path",
        "text",
    }
    missing = sorted(required - set(chunks.columns))
    if missing:
        raise ValueError(f"chunks.csv is missing required columns: {missing}")

    for column in required:
        chunks[column] = chunks[column].map(normalize_text)

    chunks = chunks[chunks["text"].str.len() > 0].reset_index(drop=True)
    if chunks.empty:
        raise ValueError("No non-empty chunks found.")

    chunks["retrieval_text"] = (
        chunks["source_type"]
        + " | "
        + chunks["section_path"]
        + "\n"
        + chunks["text"]
    )
    return chunks


def load_questions(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_QUESTIONS

    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError(f"No questions found in {path}")
        if "question" not in rows[0]:
            raise ValueError("Question CSV must contain a 'question' column.")
        return [row["question"].strip() for row in rows if row.get("question", "").strip()]

    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def build_vectorizer(corpus: Iterable[str]) -> tuple[TfidfVectorizer, object]:
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(corpus)
    return vectorizer, matrix


def retrieve(
    question: str,
    chunks: pd.DataFrame,
    vectorizer: TfidfVectorizer,
    chunk_matrix: object,
    top_k: int,
) -> list[RetrievedChunk]:
    question_vector = vectorizer.transform([question])
    scores = cosine_similarity(question_vector, chunk_matrix).ravel()
    ranked_indices = scores.argsort()[::-1][:top_k]

    results: list[RetrievedChunk] = []
    for rank, index in enumerate(ranked_indices, start=1):
        row = chunks.iloc[int(index)]
        results.append(
            RetrievedChunk(
                rank=rank,
                score=round(float(scores[index]), 6),
                chunk_id=row["chunk_id"],
                doc_id=row["doc_id"],
                file_name=row["file_name"],
                source_type=row["source_type"],
                section_path=row["section_path"],
                text=row["text"],
            )
        )
    return results


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def generate_extractive_answer(question: str, retrieved: list[RetrievedChunk]) -> str:
    """Generate a simple answer from retrieved context.

    The project baseline needs a deterministic no-defense answer generator. This
    ranks sentences from retrieved chunks by question similarity and returns the
    strongest evidence sentences with chunk citations.
    """

    candidates: list[tuple[int, str, str, str]] = []
    for chunk in retrieved:
        for sentence in split_sentences(chunk.text):
            evidence_text = f"{chunk.section_path} {sentence}"
            candidates.append((chunk.rank, chunk.chunk_id, sentence, evidence_text))

    if not candidates:
        return "No answer could be generated from the retrieved context."

    query = expand_query(question)
    sentence_texts = [candidate[3] for candidate in candidates]
    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([query] + sentence_texts)
    scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()

    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (scores[item[0]], -item[1][0]),
        reverse=True,
    )

    selected = []
    used_sentences = set()
    for index, (_, chunk_id, sentence, _) in ranked:
        normalized = sentence.lower()
        if normalized in used_sentences:
            continue
        selected.append((chunk_id, sentence))
        used_sentences.add(normalized)
        if len(selected) == 3:
            break

    answer_parts = [f"{sentence} [{chunk_id}]" for chunk_id, sentence in selected]
    return " ".join(answer_parts)


def expand_query(question: str) -> str:
    """Small deterministic expansion for common policy-question wording."""

    expansions = {
        "limit": "maximum value allowance amount cap threshold",
        "spending": "cost price value amount maximum",
        "holiday": "leave vacation annual allowance",
        "insurance": "cover coverage medical health life",
        "request": "apply application process ask submit",
        "responsibilities": "role duties accountable accountabilities",
    }
    terms = [question]
    lowered = question.lower()
    for trigger, extra in expansions.items():
        if trigger in lowered:
            terms.append(extra)
    return " ".join(terms)


def build_context(retrieved: list[RetrievedChunk], max_chars: int) -> str:
    blocks = []
    total = 0
    for chunk in retrieved:
        header = (
            f"[{chunk.chunk_id}] source_type={chunk.source_type}; "
            f"file={chunk.file_name}; section={chunk.section_path}; score={chunk.score}"
        )
        block = f"{header}\n{chunk.text}"
        if blocks and total + len(block) > max_chars:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n---\n\n".join(blocks)


def make_prompt(question: str, context: str) -> str:
    return (
        "You are a handbook question-answering assistant. Answer the question "
        "using the retrieved context and cite chunk IDs.\n\n"
        f"Question:\n{question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Answer:"
    )


def run_baseline(args: argparse.Namespace) -> None:
    chunks_path = Path(args.chunks)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    chunks = load_chunks(chunks_path)
    questions = load_questions(Path(args.questions) if args.questions else None)
    vectorizer, chunk_matrix = build_vectorizer(chunks["retrieval_text"])

    result_rows = []
    prompt_rows = []
    retrieval_rows = []

    for question_id, question in enumerate(questions, start=1):
        retrieved = retrieve(question, chunks, vectorizer, chunk_matrix, args.top_k)
        context = build_context(retrieved, args.max_context_chars)
        answer = generate_extractive_answer(question, retrieved)

        qid = f"Q{question_id:03d}"
        result_rows.append(
            {
                "question_id": qid,
                "question": question,
                "answer": answer,
                "top_chunk_ids": ";".join(chunk.chunk_id for chunk in retrieved),
                "top_scores": ";".join(str(chunk.score) for chunk in retrieved),
                "context_chars": len(context),
            }
        )
        prompt_rows.append(
            {
                "question_id": qid,
                "question": question,
                "prompt": make_prompt(question, context),
            }
        )
        for chunk in retrieved:
            retrieval_rows.append(
                {
                    "question_id": qid,
                    "rank": chunk.rank,
                    "score": chunk.score,
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "file_name": chunk.file_name,
                    "source_type": chunk.source_type,
                    "section_path": chunk.section_path,
                    "text": chunk.text,
                }
            )

    pd.DataFrame(result_rows).to_csv(outdir / "baseline_results.csv", index=False)
    pd.DataFrame(prompt_rows).to_json(outdir / "baseline_prompts.jsonl", orient="records", lines=True)
    pd.DataFrame(retrieval_rows).to_csv(outdir / "baseline_retrievals.csv", index=False)

    summary = {
        "chunks_path": str(chunks_path),
        "chunk_count": int(len(chunks)),
        "question_count": len(questions),
        "top_k": args.top_k,
        "max_context_chars": args.max_context_chars,
        "outputs": [
            "baseline_results.csv",
            "baseline_prompts.jsonl",
            "baseline_retrievals.csv",
        ],
        "note": "No prompt-injection filtering, role separation, citation verification, or second-pass validation is applied.",
    }
    (outdir / "baseline_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a no-defense RAG baseline over handbook chunks.")
    parser.add_argument("--chunks", default="handbook-main/chunks.csv", help="Path to chunks.csv.")
    parser.add_argument("--questions", help="CSV with a question column, or a plain text file with one question per line.")
    parser.add_argument("--outdir", default="outputs/baseline_rag", help="Directory for baseline outputs.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of chunks to retrieve per question.")
    parser.add_argument("--max-context-chars", type=int, default=6000, help="Maximum concatenated context length.")
    return parser.parse_args()


if __name__ == "__main__":
    run_baseline(parse_args())
