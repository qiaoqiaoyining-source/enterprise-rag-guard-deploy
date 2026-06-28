#!/usr/bin/env python3
"""Build the final EnterpriseRAG-Guard corpus.

This script builds a real-company corpus from traceable public sources. Synthetic
attack documents are generated separately by the guard and are not counted as
clean canonical company chunks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path


OUT = Path("data/enterprise_corpus/company_chunks.csv")
MADE_TECH_CHUNKS = Path("handbook-main/chunks.csv")

GITLAB_SITEMAP = "https://handbook.gitlab.com/sitemap.xml"
BASECAMP_HANDBOOK = "https://basecamp.com/handbook"
BASECAMP_ROOT = "https://basecamp.com"
VALVE_PDF = "https://cdn.akamai.steamstatic.com/apps/valve/Valve_NewEmployeeHandbook.pdf"

CHINA_PDFS = {
    "tencent": {
        "name_en": "Tencent",
        "name_zh": "腾讯",
        "language": "zh",
        "urls": [
            "https://static.www.tencent.com/uploads/2025/04/08/1132b72b565389d1b913aea60a648d73.pdf",
            "https://static.www.tencent.com/uploads/2025/04/08/00ef711d9596ce09344c0260b14cda7e.pdf",
        ],
    },
    "byd": {
        "name_en": "BYD",
        "name_zh": "比亚迪",
        "language": "zh",
        "urls": [
            "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0324/2025032401245_c.pdf",
            "https://cv.byd.com/content/dam/commercial-vehicle-cms/report/Human%20Rights%20Policy%20Statement.pdf",
        ],
    },
    "huawei": {
        "name_en": "Huawei",
        "name_zh": "华为",
        "language": "zh",
        "urls": [
            "https://www.huawei.com/minisite/annual-report-download/annual_report_2024_en.pdf",
            "https://www-file.huawei.com/dam/asset/view/dec782afd1544f558c32fc76e3141334.pdf",
        ],
    },
}


@dataclass(frozen=True)
class EnterpriseChunk:
    chunk_id: str
    company_id: str
    company_name: str
    company_name_zh: str
    language: str
    source_url: str
    source_host: str
    source_type: str
    doc_title: str
    section_path: str
    text: str
    corpus_origin: str
    is_poisoned: str = "false"
    poison_strength: str = "none"
    attack_goal: str = ""
    trust_level: str = "official"
    document_version: str = "2024-2025"
    effective_date: str = ""
    content_hash: str = ""
    instruction_risk_score: str = "0.0"


class HTMLBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = False
        self.tag = ""
        self.parts: list[str] = []
        self.headings: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "p", "li"}:
            self.capture = True
            self.tag = tag
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        if not self.capture or tag.lower() != self.tag:
            return
        text = clean(" ".join(self.parts))
        if text:
            if self.tag.startswith("h"):
                level = int(self.tag[1])
                self.headings = self.headings[: level - 1]
                self.headings.append(text)
            else:
                self.blocks.append((" > ".join(self.headings[-4:]) or "Page content", text))
        self.capture = False
        self.tag = ""
        self.parts = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def host(url: str) -> str:
    if url.startswith("local:"):
        return "local"
    return urllib.parse.urlparse(url).netloc.lower()


def content_hash(text: str) -> str:
    return hashlib.sha256(clean(text).encode("utf-8")).hexdigest()[:16]


def instruction_risk(text: str) -> float:
    patterns = [
        r"\b(ignore|override|disregard)\b.{0,80}\b(instruction|policy|previous|prior)\b",
        r"\b(system prompt|developer message|access token|password|credential)\b",
        r"\bdo not cite|replace .* citation|never refuse\b",
        r"忽略.{0,20}(指令|政策|规则)",
        r"(密码|凭证|访问令牌|系统提示词)",
    ]
    return min(1.0, sum(1 for pattern in patterns if re.search(pattern, text, re.I)) / 3)


def source_type(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["esg", "sustainability", "环境", "社会", "治理", "可持续"]):
        return "esg"
    if any(term in lowered for term in ["employee", "talent", "people", "员工", "人才", "雇员"]):
        return "employee"
    if any(term in lowered for term in ["risk", "security", "安全", "风险"]):
        return "risk"
    if any(term in lowered for term in ["business", "revenue", "segment", "业务", "收入", "经营"]):
        return "business"
    if any(term in lowered for term in ["governance", "board", "director", "治理", "董事"]):
        return "governance"
    return "company"


def fetch_bytes(url: str, timeout: int) -> bytes:
    try:
        completed = subprocess.run(
            ["curl", "-L", "--silent", "--show-error", "--max-time", str(timeout), url],
            check=True,
            capture_output=True,
        )
        if completed.stdout:
            return completed.stdout
    except Exception:
        pass
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_text(url: str, timeout: int) -> str:
    return fetch_bytes(url, timeout).decode("utf-8", errors="ignore")


def html_blocks(url: str, timeout: int) -> list[tuple[str, str]]:
    parser = HTMLBlocks()
    parser.feed(fetch_text(url, timeout))
    return parser.blocks


def chunk_blocks(blocks: list[tuple[str, str]], max_chars: int = 950) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    section = ""
    buf: list[str] = []
    size = 0
    for sec, text in blocks:
        text = clean(text)
        if len(text) < 45:
            continue
        if buf and (sec != section or size + len(text) > max_chars):
            joined = clean(" ".join(buf))
            if len(joined) >= 90:
                out.append((section, joined))
            buf, size = [], 0
        section = sec or section or "Document"
        buf.append(text)
        size += len(text)
    if buf:
        joined = clean(" ".join(buf))
        if len(joined) >= 90:
            out.append((section, joined))
    return out


def make_chunk(
    idx: int,
    prefix: str,
    company_id: str,
    company_name: str,
    company_name_zh: str,
    language: str,
    source_url: str,
    doc_title: str,
    section: str,
    text: str,
    origin: str,
) -> EnterpriseChunk:
    stype = source_type(" ".join([doc_title, section, text]))
    return EnterpriseChunk(
        chunk_id=f"{prefix}{idx:04d}",
        company_id=company_id,
        company_name=company_name,
        company_name_zh=company_name_zh,
        language=language,
        source_url=source_url,
        source_host=host(source_url),
        source_type=stype,
        doc_title=doc_title,
        section_path=section,
        text=text,
        corpus_origin=origin,
        content_hash=content_hash(text),
        instruction_risk_score=f"{instruction_risk(text):.3f}",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def made_tech_chunks(target: int) -> list[EnterpriseChunk]:
    rows = read_csv(MADE_TECH_CHUNKS)
    chunks = []
    for row in rows[:target]:
        text = clean(row.get("text", ""))
        if not text:
            continue
        cid = row.get("chunk_id") or f"MT{len(chunks)+1:04d}"
        chunks.append(
            make_chunk(
                idx=len(chunks) + 1,
                prefix="MT",
                company_id="made_tech",
                company_name="Made Tech",
                company_name_zh="Made Tech",
                language="en",
                source_url="local:handbook-main/chunks.csv",
                doc_title=row.get("doc_title") or row.get("file_name") or "Made Tech Handbook",
                section=row.get("section_path") or "Handbook",
                text=text,
                origin="local_clean",
            )
        )
        chunks[-1] = EnterpriseChunk(**{**asdict(chunks[-1]), "chunk_id": cid})
    return chunks


def gitlab_urls(timeout: int, max_pages: int) -> list[str]:
    raw = fetch_text(GITLAB_SITEMAP, timeout)
    urls = re.findall(r"<loc>(.*?)</loc>", raw)
    preferred = [
        url
        for url in urls
        if url.startswith("https://handbook.gitlab.com/handbook/")
        and any(term in url for term in ["/values", "/company/", "/people-group/", "/total-rewards/", "/security/", "/finance/"])
    ]
    return preferred[:max_pages]


def public_html_company(company_id: str, name: str, name_zh: str, prefix: str, urls: list[str], target: int, timeout: int) -> list[EnterpriseChunk]:
    chunks: list[EnterpriseChunk] = []
    for url in urls:
        try:
            blocks = chunk_blocks(html_blocks(url, timeout))
        except Exception:
            continue
        for section, text in blocks:
            if len(chunks) >= target:
                return chunks
            chunks.append(make_chunk(len(chunks) + 1, prefix, company_id, name, name_zh, "en", url, name + " public handbook", section, text, "fetched_public_html"))
    return chunks


def basecamp_urls(timeout: int) -> list[str]:
    raw = fetch_text(BASECAMP_HANDBOOK, timeout)
    hrefs = re.findall(r"href=[\"']([^\"']+)", raw)
    urls = [BASECAMP_HANDBOOK]
    for href in hrefs:
        if href.startswith("/handbook/"):
            urls.append(urllib.parse.urljoin(BASECAMP_ROOT, href))
    return sorted(set(urls))


def pdf_text(url: str, timeout: int) -> str:
    data = fetch_bytes(url, timeout)
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise RuntimeError("Install pypdf or run with bundled workspace Python.") from exc
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(data)
        handle.flush()
        reader = PdfReader(handle.name)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def pdf_company(company_id: str, name: str, name_zh: str, language: str, prefix: str, urls: list[str], target: int, timeout: int) -> list[EnterpriseChunk]:
    chunks: list[EnterpriseChunk] = []
    for url in urls:
        try:
            text = pdf_text(url, timeout)
        except Exception:
            continue
        lines = [clean(line) for line in text.splitlines()]
        blocks: list[tuple[str, str]] = []
        section = "PDF report"
        para: list[str] = []
        for line in lines:
            if not line:
                continue
            if len(line) <= 50 and re.search(r"[A-Za-z\u4e00-\u9fff]", line) and not line.endswith((".", "。", "；", ";")):
                if para:
                    blocks.append((section, " ".join(para)))
                    para = []
                section = line
                continue
            para.append(line)
            if sum(len(p) for p in para) >= 850:
                blocks.append((section, " ".join(para)))
                para = []
        if para:
            blocks.append((section, " ".join(para)))
        for section, chunk_text in chunk_blocks(blocks, max_chars=1000):
            if len(chunks) >= target:
                return chunks
            chunks.append(make_chunk(len(chunks) + 1, prefix, company_id, name, name_zh, language, url, name + " public report", section, chunk_text, "fetched_public_pdf"))
    return chunks


def write_chunks(path: Path, chunks: list[EnterpriseChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(chunks[0]).keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for chunk in chunks:
            writer.writerow(asdict(chunk))


def build(args: argparse.Namespace) -> list[EnterpriseChunk]:
    chunks: list[EnterpriseChunk] = []
    chunks.extend(made_tech_chunks(146))
    chunks.extend(public_html_company("gitlab", "GitLab", "GitLab", "GL", gitlab_urls(args.timeout, 45), 160, args.timeout))
    chunks.extend(public_html_company("basecamp", "37signals/Basecamp", "37signals/Basecamp", "BC", basecamp_urls(args.timeout), 125, args.timeout))
    chunks.extend(pdf_company("valve", "Valve", "Valve", "en", "VL", [VALVE_PDF], 80, args.timeout))
    for company_id, spec in CHINA_PDFS.items():
        prefix = {"tencent": "TC", "byd": "BY", "huawei": "HW"}[company_id]
        chunks.extend(pdf_company(company_id, spec["name_en"], spec["name_zh"], spec["language"], prefix, spec["urls"], args.china_target, args.timeout))
    seen: set[tuple[str, str]] = set()
    unique: list[EnterpriseChunk] = []
    for chunk in chunks:
        key = (chunk.company_id, chunk.content_hash)
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build final EnterpriseRAG-Guard corpus.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--china-target", type=int, default=200)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = build(args)
    write_chunks(args.out, chunks)
    counts: dict[str, int] = {}
    origins: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.company_id] = counts.get(chunk.company_id, 0) + 1
        origins[chunk.corpus_origin] = origins.get(chunk.corpus_origin, 0) + 1
    print(f"Wrote {len(chunks)} chunks to {args.out}")
    print(counts)
    print(origins)


if __name__ == "__main__":
    main()
