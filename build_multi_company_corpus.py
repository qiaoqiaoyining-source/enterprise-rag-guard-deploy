#!/usr/bin/env python3
"""Build a multi-company handbook corpus for transfer experiments.

The default mode is fully local and reproducible:
- reuse the existing Made Tech handbook chunks;
- add compact public-source seed chunks for GitLab, 37signals/Basecamp, and Valve.

Optional `--fetch-public-sources` mode fetches official public pages and extracts
additional paragraphs without requiring third-party scraping libraries.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_MADE_TECH_CHUNKS = Path("handbook-main/chunks.csv")
DEFAULT_OUT = Path("data/multi_company/company_chunks.csv")


@dataclass(frozen=True)
class CompanyChunk:
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


PUBLIC_SOURCE_SEEDS = [
    CompanyChunk(
        chunk_id="GL0001",
        company_id="gitlab",
        company_name="GitLab",
        source_url="https://handbook.gitlab.com/handbook/",
        source_type="company",
        doc_title="GitLab Handbook",
        section_path="Handbook-first operating model",
        text=(
            "GitLab presents its public handbook as the central reference for how the company works. "
            "The handbook is intended to make practices, decisions, and operating norms transparent."
        ),
    ),
    CompanyChunk(
        chunk_id="GL0002",
        company_id="gitlab",
        company_name="GitLab",
        source_url="https://handbook.gitlab.com/handbook/company/culture/all-remote/",
        source_type="work_model",
        doc_title="GitLab All-Remote",
        section_path="Remote work",
        text=(
            "GitLab is known for an all-remote work model. Remote collaboration relies on written documentation, "
            "asynchronous communication, and explicit processes rather than office-first coordination."
        ),
    ),
    CompanyChunk(
        chunk_id="GL0003",
        company_id="gitlab",
        company_name="GitLab",
        source_url="https://handbook.gitlab.com/handbook/values/",
        source_type="culture",
        doc_title="GitLab Values",
        section_path="Values",
        text=(
            "GitLab's public handbook describes company values as operating principles. The values guide how teams "
            "communicate, make decisions, and evaluate trade-offs."
        ),
    ),
    CompanyChunk(
        chunk_id="BC0001",
        company_id="basecamp",
        company_name="37signals/Basecamp",
        source_url="https://basecamp.com/handbook",
        source_type="company",
        doc_title="37signals Employee Handbook",
        section_path="Employee handbook",
        text=(
            "The 37signals employee handbook explains company policies, working norms, benefits, and expectations "
            "for employees. It is a public example of a compact company handbook."
        ),
    ),
    CompanyChunk(
        chunk_id="BC0002",
        company_id="basecamp",
        company_name="37signals/Basecamp",
        source_url="https://basecamp.com/handbook",
        source_type="work_model",
        doc_title="37signals Employee Handbook",
        section_path="How we work",
        text=(
            "37signals emphasizes calm, focused work and clear written communication. Its handbook-style material "
            "is useful for testing agent answers about work practices and company norms."
        ),
    ),
    CompanyChunk(
        chunk_id="BC0003",
        company_id="basecamp",
        company_name="37signals/Basecamp",
        source_url="https://basecamp.com/handbook",
        source_type="benefits",
        doc_title="37signals Employee Handbook",
        section_path="Benefits and policies",
        text=(
            "The 37signals handbook includes employee-facing policy and benefit information. Answers about 37signals "
            "should cite 37signals sources, not policies from another company handbook."
        ),
    ),
    CompanyChunk(
        chunk_id="VL0001",
        company_id="valve",
        company_name="Valve",
        source_url="https://www.valvesoftware.com/en/publications",
        source_type="company",
        doc_title="Valve Handbook for New Employees",
        section_path="New employee handbook",
        text=(
            "Valve publishes a handbook for new employees through its official publications page. The handbook is "
            "often used as an example of a distinctive company culture and organization model."
        ),
    ),
    CompanyChunk(
        chunk_id="VL0002",
        company_id="valve",
        company_name="Valve",
        source_url="https://www.valvesoftware.com/en/publications",
        source_type="culture",
        doc_title="Valve Handbook for New Employees",
        section_path="Organization and autonomy",
        text=(
            "Valve's public handbook is associated with a high-autonomy operating culture. This makes it useful for "
            "testing whether an agent confuses culture-specific practices across companies."
        ),
    ),
    CompanyChunk(
        chunk_id="VL0003",
        company_id="valve",
        company_name="Valve",
        source_url="https://www.valvesoftware.com/en/publications",
        source_type="onboarding",
        doc_title="Valve Handbook for New Employees",
        section_path="New hire orientation",
        text=(
            "Valve's handbook is framed for new employees. Onboarding questions about Valve should stay grounded in "
            "Valve material and should not import GitLab or 37signals policies."
        ),
    ),
]


PUBLIC_FETCH_SOURCES = [
    {
        "company_id": "gitlab",
        "company_name": "GitLab",
        "url": "https://handbook.gitlab.com/handbook/",
        "doc_title": "GitLab Handbook",
    },
    {
        "company_id": "basecamp",
        "company_name": "37signals/Basecamp",
        "url": "https://basecamp.com/handbook",
        "doc_title": "37signals Employee Handbook",
    },
    {
        "company_id": "valve",
        "company_name": "Valve",
        "url": "https://www.valvesoftware.com/en/publications",
        "doc_title": "Valve Publications",
    },
]


class ParagraphExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"p", "li", "h1", "h2", "h3"}:
            self._capture = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag.lower() in {"p", "li", "h1", "h2", "h3"}:
            text = clean_text(" ".join(self._parts))
            if text:
                self.paragraphs.append(text)
            self._capture = False
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_made_tech_chunks(path: Path, limit: int) -> list[CompanyChunk]:
    rows = read_csv(path)
    chunks: list[CompanyChunk] = []
    for row in rows:
        chunk_id = row.get("chunk_id") or row.get("\ufeffchunk_id") or ""
        text = clean_text(row.get("text", ""))
        if not chunk_id or not text:
            continue
        chunks.append(
            CompanyChunk(
                chunk_id=chunk_id,
                company_id="made_tech",
                company_name="Made Tech",
                source_url="local:handbook-main/chunks.csv",
                source_type=row.get("source_type", ""),
                doc_title=row.get("doc_title", ""),
                section_path=row.get("section_path", ""),
                text=text,
            )
        )
        if limit and len(chunks) >= limit:
            break
    return chunks


def paragraph_score(text: str) -> int:
    keywords = (
        "handbook",
        "policy",
        "benefit",
        "remote",
        "work",
        "employee",
        "onboarding",
        "culture",
        "values",
        "company",
        "communication",
    )
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


def fetch_source_chunks(limit_per_company: int, timeout: int) -> list[CompanyChunk]:
    fetched: list[CompanyChunk] = []
    for source in PUBLIC_FETCH_SOURCES:
        request = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "prompt-injection-rag-course-project/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="ignore")
        except (OSError, urllib.error.URLError):
            continue

        parser = ParagraphExtractor()
        parser.feed(raw)
        candidates = [
            text
            for text in parser.paragraphs
            if 80 <= len(text) <= 900 and paragraph_score(text) > 0
        ]
        candidates = sorted(candidates, key=paragraph_score, reverse=True)[:limit_per_company]
        prefix = source["company_id"][:2].upper()
        for index, text in enumerate(candidates, start=1):
            fetched.append(
                CompanyChunk(
                    chunk_id=f"{prefix}F{index:03d}",
                    company_id=source["company_id"],
                    company_name=source["company_name"],
                    source_url=source["url"],
                    source_type="official_public_page",
                    doc_title=source["doc_title"],
                    section_path="Fetched official public page",
                    text=text,
                    corpus_origin="fetched_public",
                )
            )
    return fetched


def write_chunks(path: Path, chunks: list[CompanyChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(chunks[0]).keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for chunk in chunks:
            writer.writerow(asdict(chunk))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a multi-company handbook corpus.")
    parser.add_argument("--made-tech-chunks", type=Path, default=DEFAULT_MADE_TECH_CHUNKS)
    parser.add_argument("--made-tech-limit", type=int, default=80)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fetch-public-sources", action="store_true")
    parser.add_argument("--fetch-limit-per-company", type=int, default=12)
    parser.add_argument("--fetch-timeout", type=int, default=15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_made_tech_chunks(args.made_tech_chunks, args.made_tech_limit)
    chunks.extend(PUBLIC_SOURCE_SEEDS)
    if args.fetch_public_sources:
        chunks.extend(fetch_source_chunks(args.fetch_limit_per_company, args.fetch_timeout))

    seen: set[str] = set()
    unique_chunks: list[CompanyChunk] = []
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        unique_chunks.append(chunk)

    write_chunks(args.out, unique_chunks)
    counts: dict[str, int] = {}
    for chunk in unique_chunks:
        counts[chunk.company_id] = counts.get(chunk.company_id, 0) + 1
    print(f"Wrote {len(unique_chunks)} chunks to {args.out}")
    print(counts)


if __name__ == "__main__":
    main()
