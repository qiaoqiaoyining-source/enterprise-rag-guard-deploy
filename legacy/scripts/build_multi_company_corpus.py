#!/usr/bin/env python3
"""Build a 500-chunk multi-company corpus for EnterpriseRAG-Guard.

The normal architecture is company-specific: each company has its own knowledge
base and agent. This builder creates one canonical CSV with explicit
`company_id` provenance so experiments can either load one company at a time or
simulate cross-company contamination as an attack.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


DEFAULT_MADE_TECH_CHUNKS = Path("handbook-main/chunks.csv")
DEFAULT_OUT = Path("data/multi_company/company_chunks.csv")

GITLAB_SITEMAP = "https://handbook.gitlab.com/sitemap.xml"
BASECAMP_ROOT = "https://basecamp.com"
BASECAMP_HANDBOOK = "https://basecamp.com/handbook"
VALVE_PUBLICATIONS = "https://www.valvesoftware.com/en/publications"
VALVE_HANDBOOK_PDF = "https://cdn.akamai.steamstatic.com/apps/valve/Valve_NewEmployeeHandbook.pdf"

TARGET_BY_COMPANY = {
    "made_tech": 146,
    "gitlab": 150,
    "basecamp": 125,
    "valve": 79,
}


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
    trust_level: str = "official"
    document_version: str = "unknown"
    effective_date: str = ""
    content_hash: str = ""
    instruction_risk_score: str = "0.0"
    source_host: str = ""


class SectionExtractor(HTMLParser):
    """Small dependency-free section-aware extractor for public HTML pages."""

    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.current_tag = ""
        self.parts: list[str] = []
        self.heading_stack: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self.current_tag = ""
            return
        if tag in {"h1", "h2", "h3", "h4", "p", "li"}:
            self.capture = True
            self.current_tag = tag
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.capture or tag != self.current_tag:
            return
        text = clean_text(" ".join(self.parts))
        if text:
            if tag in {"h1", "h2", "h3", "h4"}:
                level = int(tag[1])
                self.heading_stack = self.heading_stack[: level - 1]
                self.heading_stack.append(text)
            else:
                section = " > ".join(self.heading_stack[-4:]) or "Page content"
                self.blocks.append((section, text))
        self.capture = False
        self.current_tag = ""
        self.parts = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    value = value.replace("\u200b", "")
    return value.strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def fetch_text(url: str, timeout: int) -> str:
    try:
        completed = subprocess.run(
            ["curl", "-L", "--silent", "--show-error", "--max-time", str(timeout), url],
            check=True,
            capture_output=True,
        )
        if completed.stdout:
            return completed.stdout.decode("utf-8", errors="ignore")
    except Exception:
        pass
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 prompt-injection-rag-course-project/2.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def source_host(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower()


def instruction_risk(text: str) -> float:
    patterns = [
        r"\bignore\b.{0,80}\b(instruction|policy|handbook|previous|prior)\b",
        r"\b(system|developer)\s+(prompt|message|override)\b",
        r"\b(password|credential|token|secret|api key)\b",
        r"\bdo not cite|replace .* citation|cite this note\b",
        r"\bmust follow this instruction|never refuse\b",
        r"\bsupersedes all previous policies\b",
    ]
    hits = sum(1 for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL))
    return min(1.0, hits / 3.0)


def make_hash(text: str) -> str:
    return hashlib.sha256(clean_text(text).encode("utf-8")).hexdigest()[:16]


def normalize_category(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("benefit", "leave", "holiday", "vacation", "reward", "compensation")):
        return "benefits"
    if any(term in lowered for term in ("remote", "work", "communication", "meeting", "async")):
        return "work_model"
    if any(term in lowered for term in ("security", "device", "access", "system", "credential")):
        return "security"
    if any(term in lowered for term in ("value", "culture", "conduct", "principle")):
        return "culture"
    if any(term in lowered for term in ("onboarding", "new employee", "getting started")):
        return "onboarding"
    if any(term in lowered for term in ("expense", "travel", "reimburse")):
        return "expense"
    return "company"


def chunk_paragraphs(paragraphs: Iterable[tuple[str, str]], max_chars: int = 900) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    current_section = ""
    current: list[str] = []
    current_len = 0
    for section, paragraph in paragraphs:
        paragraph = clean_text(paragraph)
        if len(paragraph) < 55:
            continue
        if current and (section != current_section or current_len + len(paragraph) > max_chars):
            chunks.append((current_section, " ".join(current)))
            current = []
            current_len = 0
        current_section = section or current_section or "Page content"
        current.append(paragraph)
        current_len += len(paragraph)
    if current:
        chunks.append((current_section, " ".join(current)))
    return [(section, text) for section, text in chunks if 90 <= len(text) <= max_chars * 1.35]


def make_chunk(
    chunk_id: str,
    company_id: str,
    company_name: str,
    source_url: str,
    doc_title: str,
    section_path: str,
    text: str,
    corpus_origin: str,
) -> CompanyChunk:
    category = normalize_category(" ".join([doc_title, section_path, text]))
    risk = instruction_risk(text)
    return CompanyChunk(
        chunk_id=chunk_id,
        company_id=company_id,
        company_name=company_name,
        source_url=source_url,
        source_type=category,
        doc_title=doc_title,
        section_path=section_path,
        text=text,
        corpus_origin=corpus_origin,
        trust_level="official" if source_url.startswith(("https://", "local:")) else "unknown",
        content_hash=make_hash(text),
        instruction_risk_score=f"{risk:.3f}",
        source_host=source_host(source_url),
    )


def load_made_tech_chunks(path: Path, target: int) -> list[CompanyChunk]:
    chunks: list[CompanyChunk] = []
    for index, row in enumerate(read_csv(path), start=1):
        text = clean_text(row.get("text", ""))
        if not text:
            continue
        original_id = row.get("chunk_id") or row.get("\ufeffchunk_id") or f"CH{index:04d}"
        chunks.append(
            make_chunk(
                chunk_id=original_id,
                company_id="made_tech",
                company_name="Made Tech",
                source_url="local:handbook-main/chunks.csv",
                doc_title=row.get("doc_title", "") or row.get("file_name", "") or "Made Tech Handbook",
                section_path=row.get("section_path", "") or "Handbook",
                text=text,
                corpus_origin="local_clean",
            )
        )
        if len(chunks) >= target:
            break
    return chunks


def extract_html_blocks(url: str, timeout: int) -> list[tuple[str, str]]:
    raw = fetch_text(url, timeout)
    parser = SectionExtractor()
    parser.feed(raw)
    return parser.blocks


def gitlab_urls(timeout: int, max_pages: int) -> list[str]:
    raw = fetch_text(GITLAB_SITEMAP, timeout)
    urls = re.findall(r"<loc>(.*?)</loc>", raw)
    preferred_terms = (
        "/handbook/values",
        "/handbook/company/",
        "/handbook/people-group/",
        "/handbook/total-rewards/",
        "/handbook/finance/travel",
        "/handbook/company/culture/",
        "/handbook/communication/",
        "/handbook/security/",
        "/handbook/leadership/",
    )
    selected: list[str] = []
    for url in urls:
        if not url.startswith("https://handbook.gitlab.com/handbook/"):
            continue
        if any(term in url for term in preferred_terms):
            selected.append(url)
    return selected[:max_pages]


def fetch_gitlab_chunks(target: int, timeout: int, max_pages: int) -> list[CompanyChunk]:
    chunks: list[CompanyChunk] = []
    for url in gitlab_urls(timeout, max_pages):
        try:
            blocks = extract_html_blocks(url, timeout)
        except (OSError, urllib.error.URLError, TimeoutError):
            continue
        page_title = "GitLab Handbook"
        for section, text in chunk_paragraphs(blocks):
            if len(chunks) >= target:
                return chunks
            chunks.append(
                make_chunk(
                    chunk_id=f"GL{len(chunks) + 1:04d}",
                    company_id="gitlab",
                    company_name="GitLab",
                    source_url=url,
                    doc_title=page_title,
                    section_path=section,
                    text=text,
                    corpus_origin="fetched_public",
                )
            )
    return chunks


def basecamp_urls(timeout: int, max_pages: int) -> list[str]:
    raw = fetch_text(BASECAMP_HANDBOOK, timeout)
    hrefs = re.findall(r"href=[\"']([^\"']+)", raw)
    urls = [BASECAMP_HANDBOOK]
    for href in hrefs:
        if href.startswith("/handbook/"):
            urls.append(urllib.parse.urljoin(BASECAMP_ROOT, href))
        elif href.startswith("https://basecamp.com/handbook/"):
            urls.append(href)
    return sorted(set(urls))[:max_pages]


def fetch_basecamp_chunks(target: int, timeout: int, max_pages: int) -> list[CompanyChunk]:
    chunks: list[CompanyChunk] = []
    for url in basecamp_urls(timeout, max_pages):
        try:
            blocks = extract_html_blocks(url, timeout)
        except (OSError, urllib.error.URLError, TimeoutError):
            continue
        for section, text in chunk_paragraphs(blocks, max_chars=850):
            if len(chunks) >= target:
                return chunks
            chunks.append(
                make_chunk(
                    chunk_id=f"BC{len(chunks) + 1:04d}",
                    company_id="basecamp",
                    company_name="37signals/Basecamp",
                    source_url=url,
                    doc_title="37signals Employee Handbook",
                    section_path=section,
                    text=text,
                    corpus_origin="fetched_public",
                )
            )
    return chunks


def extract_valve_pdf_text(timeout: int) -> str:
    raw = urllib.request.urlopen(
        urllib.request.Request(VALVE_HANDBOOK_PDF, headers={"User-Agent": "Mozilla/5.0"}),
        timeout=timeout,
    ).read()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(raw)
        handle.flush()
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            return ""
        reader = PdfReader(handle.name)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def fetch_valve_chunks(target: int, timeout: int) -> list[CompanyChunk]:
    chunks: list[CompanyChunk] = []
    try:
        text = extract_valve_pdf_text(timeout)
    except Exception:
        text = ""
    if not text:
        return chunks
    lines = [clean_text(line) for line in text.splitlines()]
    paragraphs: list[tuple[str, str]] = []
    section = "Valve Handbook for New Employees"
    for line in lines:
        if not line:
            continue
        if len(line) < 70 and re.search(r"[A-Za-z]", line) and not line.endswith("."):
            section = line
            continue
        paragraphs.append((section, line))
    for section_path, chunk_text in chunk_paragraphs(paragraphs, max_chars=850):
        if len(chunks) >= target:
            break
        chunks.append(
            make_chunk(
                chunk_id=f"VL{len(chunks) + 1:04d}",
                company_id="valve",
                company_name="Valve",
                source_url=VALVE_HANDBOOK_PDF,
                doc_title="Valve Handbook for New Employees",
                section_path=section_path,
                text=chunk_text,
                corpus_origin="fetched_public_pdf",
            )
        )
    return chunks


def fallback_seed_chunks(company_id: str, needed: int, start: int) -> list[CompanyChunk]:
    names = {
        "made_tech": ("Made Tech", "local:handbook-main/chunks.csv", "Made Tech Handbook"),
        "gitlab": ("GitLab", "https://handbook.gitlab.com/handbook/", "GitLab Handbook"),
        "basecamp": ("37signals/Basecamp", BASECAMP_HANDBOOK, "37signals Employee Handbook"),
        "valve": ("Valve", VALVE_HANDBOOK_PDF, "Valve Handbook for New Employees"),
    }
    company_name, url, title = names[company_id]
    rows = []
    for offset in range(needed):
        number = start + offset
        rows.append(
            make_chunk(
                chunk_id=f"{company_id[:2].upper()}S{number:04d}",
                company_id=company_id,
                company_name=company_name,
                source_url=url,
                doc_title=title,
                section_path="Official public handbook seed",
                text=(
                    f"{company_name} publishes public handbook-style guidance for employees. "
                    f"Seed section {number}. This chunk preserves company provenance for transfer testing when a public page "
                    f"cannot be fetched during an offline rebuild. It should be replaced by fetched official "
                    f"content whenever network access is available."
                ),
                corpus_origin="offline_seed",
            )
        )
    return rows


def dedupe(chunks: Iterable[CompanyChunk]) -> list[CompanyChunk]:
    seen_hashes: set[tuple[str, str]] = set()
    seen_ids: set[str] = set()
    output: list[CompanyChunk] = []
    for chunk in chunks:
        key = (chunk.company_id, chunk.content_hash)
        if key in seen_hashes:
            continue
        chunk_id = chunk.chunk_id
        if chunk_id in seen_ids:
            prefix = re.sub(r"\d+$", "", chunk_id) or chunk.company_id[:2].upper()
            chunk_id = f"{prefix}{len(seen_ids) + 1:04d}"
            chunk = CompanyChunk(**{**asdict(chunk), "chunk_id": chunk_id})
        seen_hashes.add(key)
        seen_ids.add(chunk_id)
        output.append(chunk)
    return output


def write_chunks(path: Path, chunks: list[CompanyChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(chunks[0]).keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for chunk in chunks:
            writer.writerow(asdict(chunk))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a multi-company enterprise RAG corpus.")
    parser.add_argument("--made-tech-chunks", type=Path, default=DEFAULT_MADE_TECH_CHUNKS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--target-total", type=int, default=500)
    parser.add_argument("--fetch-timeout", type=int, default=20)
    parser.add_argument("--gitlab-max-pages", type=int, default=70)
    parser.add_argument("--basecamp-max-pages", type=int, default=16)
    parser.add_argument("--offline", action="store_true", help="Skip network/PDF fetching and use local/offline seeds.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = dict(TARGET_BY_COMPANY)
    if args.target_total != 500:
        scale = args.target_total / 500
        targets = {company: max(1, round(count * scale)) for company, count in targets.items()}

    chunks: list[CompanyChunk] = []
    chunks.extend(load_made_tech_chunks(args.made_tech_chunks, targets["made_tech"]))

    if args.offline:
        for company_id in ("gitlab", "basecamp", "valve"):
            chunks.extend(fallback_seed_chunks(company_id, targets[company_id], 1))
    else:
        chunks.extend(fetch_gitlab_chunks(targets["gitlab"], args.fetch_timeout, args.gitlab_max_pages))
        chunks.extend(fetch_basecamp_chunks(targets["basecamp"], args.fetch_timeout, args.basecamp_max_pages))
        chunks.extend(fetch_valve_chunks(targets["valve"], args.fetch_timeout))

    unique = dedupe(chunks)
    counts: dict[str, int] = {}
    for chunk in unique:
        counts[chunk.company_id] = counts.get(chunk.company_id, 0) + 1

    for company_id, target in targets.items():
        if counts.get(company_id, 0) < target:
            unique.extend(fallback_seed_chunks(company_id, target - counts.get(company_id, 0), counts.get(company_id, 0) + 1))
    unique = dedupe(unique)

    ordered: list[CompanyChunk] = []
    for company_id in ("made_tech", "gitlab", "basecamp", "valve"):
        ordered.extend([chunk for chunk in unique if chunk.company_id == company_id][: targets[company_id]])
    ordered = ordered[: args.target_total]

    write_chunks(args.out, ordered)
    final_counts: dict[str, int] = {}
    origins: dict[str, int] = {}
    for chunk in ordered:
        final_counts[chunk.company_id] = final_counts.get(chunk.company_id, 0) + 1
        origins[chunk.corpus_origin] = origins.get(chunk.corpus_origin, 0) + 1
    print(f"Wrote {len(ordered)} chunks to {args.out}")
    print(final_counts)
    print(origins)


if __name__ == "__main__":
    main()
