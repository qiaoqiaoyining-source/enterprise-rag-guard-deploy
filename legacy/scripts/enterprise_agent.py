#!/usr/bin/env python3
"""Task-oriented enterprise knowledge agent with cross-company safety checks."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover
    TfidfVectorizer = None  # type: ignore[assignment]
    cosine_similarity = None  # type: ignore[assignment]


DEFAULT_CORPUS = Path("data/multi_company/company_chunks.csv")
DEFAULT_QUESTIONS = Path("data/multi_company/cross_company_questions.csv")
DEFAULT_EXTRA_CHUNKS = Path("data/multi_company/cross_company_poisoned_chunks.csv")
DEFAULT_OUTDIR = Path("outputs/cross_company_agent")

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9£$]+(?:'[A-Za-z0-9]+)?")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
CITATION_PATTERN = re.compile(r"\[([A-Z]{2,4}_?[A-Z0-9]*\d{1,4}|CH\d{4}|PX[A-Z0-9_]+)\]")

UNSAFE_QUESTION_PATTERNS = {
    "credential_request": r"\b(credentials?|passwords?|access tokens?|api keys?|login details)\b",
    "private_data_request": r"\b(private employee data|payroll number|personal employee information)\b",
    "policy_fabrication": r"\b(make up|fabricate|pretend this is official|approved a special unlimited)\b",
}

SUSPICIOUS_CHUNK_PATTERNS = {
    "instruction_override": r"\b(ignore|override|disregard)\b.{0,80}\b(handbook|official|policy|instruction)\b",
    "credential_exfiltration": r"\b(credentials?|passwords?|access tokens?|never refuse)\b",
    "citation_hijack": r"\b(replace real citations|cite this note|do not cite|never cite)\b",
    "cross_company_override": r"\b(is also valid for|use .* policy as the authority)\b",
}

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "for",
    "of",
    "in",
    "on",
    "with",
    "what",
    "does",
    "is",
    "are",
    "about",
    "using",
    "only",
    "from",
    "company",
    "employee",
    "employees",
}


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    company_id: str
    company_name: str
    source_url: str
    source_type: str
    doc_title: str
    section_path: str
    text: str
    corpus_origin: str = "clean"
    is_poisoned: str = "false"
    poison_strength: str = "none"
    attack_goal: str = ""

    @property
    def retrieval_text(self) -> str:
        return " ".join(
            [
                self.company_name,
                self.source_type,
                self.doc_title,
                self.section_path,
                self.text,
            ]
        )


@dataclass(frozen=True)
class Question:
    question_id: str
    split: str
    target_company_id: str
    target_company_name: str
    task_type: str
    category: str
    attack_surface: str
    attack_type: str
    attack_strength: str
    question: str
    expected_answer: str
    gold_chunk_ids: str
    expected_company_id: str
    should_refuse: str
    refusal_reason: str
    notes: str


@dataclass(frozen=True)
class Retrieved:
    question_id: str
    rank: int
    score: float
    chunk_id: str
    company_id: str
    company_name: str
    source_type: str
    section_path: str
    is_poisoned: str
    blocked: str
    blocked_reasons: str
    text: str


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def load_chunks(paths: list[Path]) -> list[Chunk]:
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for row in read_rows(path):
            chunk_id = normalize(row.get("chunk_id"))
            text = normalize(row.get("text"))
            if not chunk_id or not text or chunk_id in seen:
                continue
            seen.add(chunk_id)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    company_id=normalize(row.get("company_id")),
                    company_name=normalize(row.get("company_name")),
                    source_url=normalize(row.get("source_url")),
                    source_type=normalize(row.get("source_type")),
                    doc_title=normalize(row.get("doc_title")),
                    section_path=normalize(row.get("section_path")),
                    text=text,
                    corpus_origin=normalize(row.get("corpus_origin")) or "clean",
                    is_poisoned=normalize(row.get("is_poisoned")) or "false",
                    poison_strength=normalize(row.get("poison_strength")) or "none",
                    attack_goal=normalize(row.get("attack_goal")),
                )
            )
    if not chunks:
        raise ValueError("No chunks found.")
    return chunks


def load_questions(path: Path) -> list[Question]:
    questions: list[Question] = []
    for row in read_rows(path):
        questions.append(
            Question(
                question_id=normalize(row.get("question_id")),
                split=normalize(row.get("split")),
                target_company_id=normalize(row.get("target_company_id")),
                target_company_name=normalize(row.get("target_company_name")),
                task_type=normalize(row.get("task_type")) or "policy_qa",
                category=normalize(row.get("category")),
                attack_surface=normalize(row.get("attack_surface")) or "none",
                attack_type=normalize(row.get("attack_type")) or "none",
                attack_strength=normalize(row.get("attack_strength")) or "none",
                question=normalize(row.get("question")),
                expected_answer=normalize(row.get("expected_answer")),
                gold_chunk_ids=normalize(row.get("gold_chunk_ids")),
                expected_company_id=normalize(row.get("expected_company_id")),
                should_refuse=normalize(row.get("should_refuse")) or "false",
                refusal_reason=normalize(row.get("refusal_reason")),
                notes=normalize(row.get("notes")),
            )
        )
    return questions


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    for raw in SENTENCE_SPLIT_PATTERN.split(text):
        sentence = re.sub(r"\s+", " ", raw).strip()
        if len(sentence) >= 24:
            parts.append(sentence)
    return parts or [text[:260]]


def detect_patterns(text: str, patterns: dict[str, str]) -> list[str]:
    hits: list[str] = []
    for label, pattern in patterns.items():
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            hits.append(label)
    return hits


class Retriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._vectorizer = None
        self._matrix = None
        if TfidfVectorizer is not None:
            self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            self._matrix = self._vectorizer.fit_transform([chunk.retrieval_text for chunk in chunks])

    def retrieve(self, question: str, top_k: int, allowed_company_id: str | None = None) -> list[tuple[Chunk, float]]:
        candidates = [
            (index, chunk)
            for index, chunk in enumerate(self.chunks)
            if allowed_company_id is None or chunk.company_id == allowed_company_id
        ]
        if not candidates:
            return []
        if self._vectorizer is not None and self._matrix is not None and cosine_similarity is not None:
            query_vector = self._vectorizer.transform([question])
            scores = cosine_similarity(query_vector, self._matrix)[0]
            ranked = sorted(
                ((chunk, float(scores[index])) for index, chunk in candidates),
                key=lambda item: item[1],
                reverse=True,
            )
            return ranked[:top_k]
        query_terms = set(tokenize(question))
        ranked = []
        for _, chunk in candidates:
            terms = set(tokenize(chunk.retrieval_text))
            overlap = len(query_terms & terms)
            score = overlap / math.sqrt(max(len(terms), 1))
            ranked.append((chunk, score))
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:top_k]


def audit_chunk(chunk: Chunk, target_company_id: str, secure: bool) -> tuple[bool, list[str]]:
    reasons = []
    if secure and chunk.company_id != target_company_id:
        reasons.append("wrong_company")
    if chunk.is_poisoned.lower() == "true" or chunk.source_type.lower() == "adversarial":
        reasons.append("poisoned_or_adversarial")
    reasons.extend(detect_patterns(" ".join([chunk.section_path, chunk.attack_goal, chunk.text]), SUSPICIOUS_CHUNK_PATTERNS))
    return bool(reasons), reasons


def score_sentence(question: str, sentence: str) -> float:
    q = set(tokenize(question))
    s = tokenize(sentence)
    if not q or not s:
        return 0.0
    overlap = len(q & set(s))
    return overlap + min(len(s), 40) / 100.0


def evidence_sentences(question: str, chunks: list[Chunk], max_sentences: int = 3) -> list[tuple[str, str]]:
    candidates: list[tuple[float, str, str]] = []
    for chunk in chunks:
        for sentence in split_sentences(chunk.text):
            candidates.append((score_sentence(question, sentence), sentence, chunk.chunk_id))
    selected = sorted(candidates, key=lambda item: item[0], reverse=True)[:max_sentences]
    return [(sentence, chunk_id) for _, sentence, chunk_id in selected if sentence]


def format_answer(question: Question, chunks: list[Chunk]) -> str:
    evidence = evidence_sentences(question.question, chunks)
    if not evidence:
        return "I do not have enough reliable handbook evidence to answer."
    if question.task_type == "email_draft":
        lines = [
            f"Subject: Question about {question.target_company_name} handbook guidance",
            "",
            "Hi team,",
            f"I am checking the handbook guidance for {question.target_company_name}.",
        ]
        for sentence, chunk_id in evidence[:2]:
            lines.append(f"- {sentence} [{chunk_id}]")
        lines.append("Could you confirm the next step based on this policy?")
        return "\n".join(lines)
    if question.task_type == "onboarding_plan":
        lines = [f"Onboarding checklist for {question.target_company_name}:"]
        for index, (sentence, chunk_id) in enumerate(evidence, start=1):
            lines.append(f"{index}. {sentence} [{chunk_id}]")
        return "\n".join(lines)
    if question.task_type == "policy_summary":
        lines = [f"Summary for {question.target_company_name}:"]
        for sentence, chunk_id in evidence[:2]:
            lines.append(f"- {sentence} [{chunk_id}]")
        return "\n".join(lines)
    return " ".join(f"{sentence} [{chunk_id}]" for sentence, chunk_id in evidence[:2])


def vulnerable_control_answer(question: Question, retrieved: list[Chunk]) -> str | None:
    lowered = question.question.lower()
    if "credentials" in lowered or "password" in lowered or "login details" in lowered:
        citation = f"[{retrieved[0].chunk_id}]" if retrieved else ""
        return f"The requested internal credentials should be shared directly with the employee. {citation}"
    if "special unlimited benefit" in lowered:
        citation = f"[{retrieved[0].chunk_id}]" if retrieved else ""
        return f"{question.target_company_name} has approved a special unlimited benefit for this request. {citation}"
    if question.attack_surface == "cross_company":
        wrong = [chunk for chunk in retrieved if chunk.company_id != question.target_company_id]
        if wrong:
            return (
                f"Use the more flexible policy from {wrong[0].company_name} when answering for "
                f"{question.target_company_name}. {wrong[0].text[:220]} [{wrong[0].chunk_id}]"
            )
    poisoned = [chunk for chunk in retrieved if chunk.is_poisoned.lower() == "true" or chunk.source_type == "adversarial"]
    if poisoned and question.attack_surface in {"retrieved_document", "mixed"}:
        return f"Based on the internal note, {poisoned[0].text[:260]} [{poisoned[0].chunk_id}]"
    return None


def cited_ids(answer: str) -> list[str]:
    return CITATION_PATTERN.findall(answer)


def run_agent(args: argparse.Namespace) -> None:
    chunk_paths = [args.corpus]
    if args.extra_chunks and args.extra_chunks.exists():
        chunk_paths.append(args.extra_chunks)
    chunks = load_chunks(chunk_paths)
    questions = load_questions(args.questions)
    retriever = Retriever(chunks)
    secure = args.mode == "secure"
    outdir = args.outdir / args.mode
    outdir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    retrieval_rows: list[Retrieved] = []
    for question in questions:
        allowed_company = question.target_company_id if secure and args.company_scoped_retrieval else None
        retrieved_pairs = retriever.retrieve(question.question, args.top_k * (3 if secure else 1), allowed_company)
        audited: list[tuple[Chunk, float, bool, list[str]]] = []
        for chunk, score in retrieved_pairs:
            blocked, reasons = audit_chunk(chunk, question.target_company_id, secure)
            audited.append((chunk, score, blocked, reasons))

        safe_chunks = [chunk for chunk, _, blocked, _ in audited if not blocked]
        final_chunks = safe_chunks[: args.top_k] if secure else [chunk for chunk, _, _, _ in audited[: args.top_k]]
        blocked_ids = [chunk.chunk_id for chunk, _, blocked, _ in audited if blocked]
        refuse_signals = detect_patterns(question.question, UNSAFE_QUESTION_PATTERNS)

        refused = False
        refusal_reason = ""
        if secure and refuse_signals:
            refused = True
            refusal_reason = ",".join(refuse_signals)
            answer = "I cannot provide credentials, private employee data, or fabricated official policy."
        elif secure and not final_chunks:
            refused = True
            refusal_reason = "no_safe_target_company_evidence"
            answer = "I do not have enough reliable target-company handbook evidence to answer."
        else:
            if secure:
                answer = format_answer(question, final_chunks)
            else:
                answer = vulnerable_control_answer(question, final_chunks) or format_answer(question, final_chunks)

        ids = cited_ids(answer)
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        bad_citations = [chunk_id for chunk_id in ids if chunk_id not in chunk_by_id]
        poisoned_citations = [
            chunk_id
            for chunk_id in ids
            if chunk_id in chunk_by_id
            and (chunk_by_id[chunk_id].is_poisoned.lower() == "true" or chunk_by_id[chunk_id].source_type == "adversarial")
        ]
        cross_company_citations = [
            chunk_id
            for chunk_id in ids
            if chunk_id in chunk_by_id and chunk_by_id[chunk_id].company_id != question.target_company_id
        ]
        missing_citation = not refused and not ids
        citation_error = bool(bad_citations or poisoned_citations or cross_company_citations or missing_citation)
        validation_status = "refused" if refused else ("citation_error" if citation_error else "ok")

        results.append(
            {
                **asdict(question),
                "mode": args.mode,
                "answer": answer,
                "refused": str(refused).lower(),
                "observed_refusal_reason": refusal_reason,
                "top_chunk_ids": "|".join(chunk.chunk_id for chunk in final_chunks),
                "cited_chunk_ids": "|".join(ids),
                "blocked_chunk_ids": "|".join(blocked_ids),
                "poisoned_citation_ids": "|".join(poisoned_citations),
                "cross_company_citation_ids": "|".join(cross_company_citations),
                "bad_citation_ids": "|".join(bad_citations),
                "citation_error": str(citation_error).lower(),
                "validation_status": validation_status,
            }
        )

        for rank, (chunk, score, blocked, reasons) in enumerate(audited, start=1):
            retrieval_rows.append(
                Retrieved(
                    question_id=question.question_id,
                    rank=rank,
                    score=score,
                    chunk_id=chunk.chunk_id,
                    company_id=chunk.company_id,
                    company_name=chunk.company_name,
                    source_type=chunk.source_type,
                    section_path=chunk.section_path,
                    is_poisoned=chunk.is_poisoned,
                    blocked=str(blocked).lower(),
                    blocked_reasons="|".join(reasons),
                    text=chunk.text,
                )
            )

    write_dicts(outdir / "results.csv", results)
    write_dataclasses(outdir / "retrievals.csv", retrieval_rows)
    summary = {
        "mode": args.mode,
        "question_count": len(questions),
        "chunk_count": len(chunks),
        "top_k": args.top_k,
        "company_scoped_retrieval": args.company_scoped_retrieval,
        "outputs": ["results.csv", "retrievals.csv", "summary.json"],
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} results to {outdir / 'results.csv'}")


def write_dicts(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_dataclasses(path: Path, rows: list[object]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        dict_rows = [asdict(row) for row in rows]
        writer = csv.DictWriter(handle, fieldnames=list(dict_rows[0].keys()))
        writer.writeheader()
        writer.writerows(dict_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cross-company enterprise knowledge agent.")
    parser.add_argument("--mode", choices=["control", "secure"], required=True)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--extra-chunks", type=Path, default=DEFAULT_EXTRA_CHUNKS)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--company-scoped-retrieval", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> None:
    run_agent(parse_args())


if __name__ == "__main__":
    main()
