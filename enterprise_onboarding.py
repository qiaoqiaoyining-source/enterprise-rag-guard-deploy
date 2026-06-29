#!/usr/bin/env python3
"""Tenant onboarding and secure ingestion for EnterpriseRAG-Guard.

This module implements the product path for a new enterprise customer: create a
tenant, ingest administrator-provided documents or public URLs, scan them before
indexing, write a tenant-isolated knowledge store, and generate a tenant profile
without rewriting the guard core.
"""

from __future__ import annotations

import hashlib
import csv
import json
import re
import time
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib import request as urlrequest
from urllib.parse import urlparse

from enterprise_rag_guard import (
    CHUNK_RISK_PATTERNS,
    TENANT_CHUNKS_PATH,
    TENANT_PROFILES_PATH,
    UNSAFE_QUERY_PATTERNS,
    detect,
    host,
    stable_hash,
)


SENSITIVE_PATTERNS = {
    "api_key": r"\b(api[_ -]?key|secret key|access token)\b|访问令牌|密钥",
    "password": r"\b(password|passwd|credential)\b|密码|凭证",
    "payroll": r"\b(payroll|salary|compensation)\b|薪资|工资",
    "personal_id": r"\b(ssn|passport|national id)\b|身份证|护照",
}


@dataclass(frozen=True)
class TenantProfile:
    tenant_id: str
    company_name: str
    language: str
    industry: str
    isolation_level: str
    deployment_mode: str
    allowed_sources: tuple[str, ...]
    sensitive_fields: tuple[str, ...]
    query_risk_threshold: float = 0.65
    chunk_risk_threshold: float = 0.55
    require_citation: bool = True
    allow_cross_department_retrieval: bool = False
    maximum_repair_attempts: int = 1
    retention_days: int = 30


@dataclass(frozen=True)
class DocumentRecord:
    tenant_id: str
    document_id: str
    title: str
    content: str
    source_type: str
    source_uri: str
    department: str = "General"
    access_groups: tuple[str, ...] = ("employees",)
    effective_date: str = ""
    version: str = "1.0"
    security_label: str = "internal"

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class IngestionFinding:
    severity: str
    category: str
    message: str
    action: str


@dataclass(frozen=True)
class IngestionReport:
    tenant_profile: TenantProfile
    documents_seen: int
    documents_accepted: int
    documents_quarantined: int
    duplicate_documents: int
    findings: tuple[IngestionFinding, ...]
    accepted_documents: tuple[DocumentRecord, ...] = ()
    quarantined_documents: tuple[DocumentRecord, ...] = ()
    indexed_chunks: int = 0
    tenant_query_ready: bool = False
    chunk_store: str = ""
    profile_store: str = ""
    recommended_profile: dict[str, object] = field(default_factory=dict)
    pipeline_steps: tuple[str, ...] = (
        "file_type_validation",
        "text_extraction",
        "instruction_risk_scan",
        "pii_credential_detection",
        "source_version_verification",
        "human_approval_or_quarantine",
        "chunking_and_indexing",
    )

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["tenant_profile"] = asdict(self.tenant_profile)
        data["findings"] = [asdict(finding) for finding in self.findings]
        data["accepted_documents"] = [document_summary(doc) for doc in self.accepted_documents]
        data["quarantined_documents"] = [document_summary(doc) for doc in self.quarantined_documents]
        return data


class KnowledgeConnector:
    """Common connector contract for productized enterprise onboarding."""

    source_type = "generic"

    def authenticate(self) -> bool:
        return True

    def list_documents(self) -> list[str]:
        raise NotImplementedError

    def fetch_document(self, document_id: str) -> DocumentRecord:
        raise NotImplementedError

    def detect_changes(self) -> list[str]:
        return []


class AdminTextConnector(KnowledgeConnector):
    """Connector for documents supplied directly by an enterprise admin."""

    source_type = "uploaded_text"

    def __init__(
        self,
        tenant_id: str,
        company_name: str,
        documents: list[dict[str, str]],
    ) -> None:
        self.tenant_id = tenant_id
        self.company_name = company_name
        self.documents = documents

    def list_documents(self) -> list[str]:
        return [f"DOC{i + 1:03d}" for i in range(len(self.documents))]

    def fetch_document(self, document_id: str) -> DocumentRecord:
        index = max(0, int(document_id.replace("DOC", "")) - 1)
        row = self.documents[index]
        title = row.get("title") or f"{self.company_name} knowledge document"
        content = row.get("content") or ""
        source_uri = row.get("source_uri") or f"tenant://{self.tenant_id}/uploaded-text"
        department = row.get("department") or "General"
        return DocumentRecord(
            tenant_id=self.tenant_id,
            document_id=document_id,
            title=title,
            content=content,
            source_type=self.source_type,
            source_uri=source_uri,
            department=department,
        )


class SecureIngestionPipeline:
    """Scan connected documents before they become retrievable knowledge."""

    def __init__(self, tenant_profile: TenantProfile) -> None:
        self.tenant_profile = tenant_profile

    def scan(self, connector: KnowledgeConnector) -> IngestionReport:
        if not connector.authenticate():
            raise RuntimeError("Connector authentication failed.")

        findings: list[IngestionFinding] = []
        seen_hashes: set[str] = set()
        accepted = 0
        quarantined = 0
        duplicates = 0
        accepted_docs: list[DocumentRecord] = []
        quarantined_docs: list[DocumentRecord] = []
        document_ids = connector.list_documents()

        for document_id in document_ids:
            doc = connector.fetch_document(document_id)
            doc_findings = self._scan_document(doc)
            is_duplicate = doc.content_hash in seen_hashes
            if is_duplicate:
                duplicates += 1
                doc_findings.append(
                    IngestionFinding(
                        "medium",
                        "duplicate_document",
                        f"{doc.title} duplicates existing content hash {doc.content_hash}.",
                        "deduplicate",
                    )
                )
            seen_hashes.add(doc.content_hash)
            findings.extend(doc_findings)
            if any(finding.action == "quarantine" for finding in doc_findings):
                quarantined += 1
                quarantined_docs.append(doc)
            else:
                accepted += 1
                accepted_docs.append(doc)

        recommended = {
            "tenant_id": self.tenant_profile.tenant_id,
            "allowed_sources": list(self.tenant_profile.allowed_sources),
            "sensitive_fields": list(self.tenant_profile.sensitive_fields),
            "query_risk_threshold": self.tenant_profile.query_risk_threshold,
            "chunk_risk_threshold": self.tenant_profile.chunk_risk_threshold,
            "require_citation": self.tenant_profile.require_citation,
            "isolation_level": self.tenant_profile.isolation_level,
        }
        return IngestionReport(
            tenant_profile=self.tenant_profile,
            documents_seen=len(document_ids),
            documents_accepted=accepted,
            documents_quarantined=quarantined,
            duplicate_documents=duplicates,
            findings=tuple(findings),
            accepted_documents=tuple(accepted_docs),
            quarantined_documents=tuple(quarantined_docs),
            recommended_profile=recommended,
        )

    def _scan_document(self, doc: DocumentRecord) -> list[IngestionFinding]:
        findings: list[IngestionFinding] = []
        if len(doc.content.strip()) < 60:
            findings.append(
                IngestionFinding(
                    "low",
                    "insufficient_text",
                    f"{doc.title} contains too little text for reliable indexing.",
                    "review",
                )
            )

        risk_labels = detect(doc.content, CHUNK_RISK_PATTERNS)
        query_like_labels = detect(doc.content, UNSAFE_QUERY_PATTERNS)
        if risk_labels or query_like_labels:
            findings.append(
                IngestionFinding(
                    "high",
                    "embedded_instruction",
                    f"{doc.title} contains possible prompt-injection text: {', '.join(risk_labels + query_like_labels)}.",
                    "quarantine",
                )
            )

        sensitive = [
            label
            for label, pattern in SENSITIVE_PATTERNS.items()
            if re.search(pattern, doc.content, flags=re.IGNORECASE)
        ]
        if sensitive:
            findings.append(
                IngestionFinding(
                    "high",
                    "sensitive_data",
                    f"{doc.title} may contain sensitive fields: {', '.join(sensitive)}.",
                    "review",
                )
            )

        source_host = host(doc.source_uri)
        allowed = any(source in doc.source_uri or source == source_host for source in self.tenant_profile.allowed_sources)
        if self.tenant_profile.allowed_sources and not allowed and not doc.source_uri.startswith("tenant://"):
            findings.append(
                IngestionFinding(
                    "medium",
                    "unverified_source",
                    f"{doc.title} comes from an unapproved source URI.",
                    "review",
                )
            )
        return findings


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"\s+", " ", data).strip()
        if cleaned:
            self.parts.append(cleaned)

    def text(self) -> str:
        return "\n".join(self.parts)


def document_summary(doc: DocumentRecord) -> dict[str, object]:
    return {
        "document_id": doc.document_id,
        "title": doc.title,
        "source_type": doc.source_type,
        "source_uri": doc.source_uri,
        "department": doc.department,
        "security_label": doc.security_label,
        "content_hash": doc.content_hash,
        "characters": len(doc.content),
    }


def tenant_id(company_name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", company_name.lower()).strip("-") or "tenant"
    suffix = hashlib.sha1(f"{company_name}-{time.time()}".encode("utf-8")).hexdigest()[:6]
    return f"{base}-{suffix}"


def fetch_public_url(url: str, timeout: int = 15) -> dict[str, str]:
    req = urlrequest.Request(
        url,
        headers={"User-Agent": "EnterpriseRAG-Guard-Onboarding/1.0"},
        method="GET",
    )
    with urlrequest.urlopen(req, timeout=timeout) as response:
        raw = response.read(2_000_000)
        content_type = response.headers.get("Content-Type", "")
    text = raw.decode("utf-8", errors="ignore")
    if "html" in content_type or "<html" in text[:500].lower():
        parser = HTMLTextExtractor()
        parser.feed(text)
        text = parser.text()
    title = urlparse(url).netloc or url
    return {"title": title, "content": text, "source_uri": url, "department": "Public Web"}


def split_document(text: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text or "").strip()
    paragraphs = [part.strip() for part in re.split(r"\n{2,}|(?<=[。！？.!?])\s+", normalized) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= max_chars:
            current = f"{current}\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
            continue
        for start in range(0, len(paragraph), max_chars - overlap):
            piece = paragraph[start : start + max_chars].strip()
            if piece:
                chunks.append(piece)
        current = ""
    if current:
        chunks.append(current)
    return chunks


def write_tenant_profile(profile: TenantProfile) -> None:
    TENANT_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TENANT_PROFILES_PATH.exists():
        data = json.loads(TENANT_PROFILES_PATH.read_text(encoding="utf-8"))
    else:
        data = {}
    data[profile.tenant_id] = {
        "company_id": profile.tenant_id,
        "company_name": profile.company_name,
        "allowed_domains": list(profile.allowed_sources),
        "sensitive_fields": list(profile.sensitive_fields),
        "allowed_tasks": ["policy_qa", "policy_summary", "email_draft", "onboarding_checklist", "risk_review"],
        "require_company_match": True,
        "require_citation": True,
        "minimum_evidence_count": 1,
        "max_repair_attempts": profile.maximum_repair_attempts,
        "risk_threshold": profile.chunk_risk_threshold,
    }
    TENANT_PROFILES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_tenant_chunks(profile: TenantProfile, documents: tuple[DocumentRecord, ...]) -> int:
    TENANT_CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "chunk_id",
        "company_id",
        "company_name",
        "source_url",
        "source_type",
        "doc_title",
        "section_path",
        "text",
        "corpus_origin",
        "is_poisoned",
        "poison_strength",
        "attack_goal",
        "trust_level",
        "document_version",
        "effective_date",
        "content_hash",
        "instruction_risk_score",
        "source_host",
    ]
    existing: set[str] = set()
    if TENANT_CHUNKS_PATH.exists():
        with TENANT_CHUNKS_PATH.open(newline="", encoding="utf-8-sig") as handle:
            existing = {row.get("chunk_id", "") for row in csv.DictReader(handle)}
    file_exists = TENANT_CHUNKS_PATH.exists()
    written = 0
    with TENANT_CHUNKS_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for doc in documents:
            for index, chunk_text in enumerate(split_document(doc.content), start=1):
                chunk_id = f"{profile.tenant_id.upper().replace('-', '_')}_{doc.document_id}_{index:03d}"
                if chunk_id in existing:
                    continue
                source_host = host(doc.source_uri) or profile.tenant_id
                risk_labels = detect(chunk_text, CHUNK_RISK_PATTERNS)
                writer.writerow(
                    {
                        "chunk_id": chunk_id,
                        "company_id": profile.tenant_id,
                        "company_name": profile.company_name,
                        "source_url": doc.source_uri,
                        "source_type": doc.source_type,
                        "doc_title": doc.title,
                        "section_path": doc.department,
                        "text": chunk_text,
                        "corpus_origin": "tenant_ingested",
                        "is_poisoned": "false",
                        "poison_strength": "none",
                        "attack_goal": "",
                        "trust_level": "official",
                        "document_version": doc.version,
                        "effective_date": doc.effective_date,
                        "content_hash": stable_hash(chunk_text),
                        "instruction_risk_score": str(min(1.0, len(risk_labels) * 0.18)),
                        "source_host": source_host,
                    }
                )
                existing.add(chunk_id)
                written += 1
    return written


def create_tenant_agent(
    company_name: str,
    language: str,
    industry: str,
    deployment_mode: str,
    source_kinds: list[str],
    allowed_sources: list[str],
    sample_text: str,
    source_urls: list[str] | None = None,
) -> IngestionReport:
    tid = tenant_id(company_name)
    documents: list[dict[str, str]] = []
    if sample_text.strip():
        documents.append(
            {
                "title": f"{company_name} uploaded knowledge document",
                "content": sample_text,
                "source_uri": f"tenant://{tid}/uploaded-text",
                "department": "Admin Upload",
            }
        )
    fetch_findings: list[IngestionFinding] = []
    for url in source_urls or []:
        if not url.strip():
            continue
        try:
            documents.append(fetch_public_url(url.strip()))
        except Exception as exc:
            fetch_findings.append(
                IngestionFinding(
                    "medium",
                    "source_fetch_failed",
                    f"Could not fetch {url.strip()}: {exc}",
                    "review",
                )
            )
    source_hosts = [host(doc.get("source_uri", "")) for doc in documents if doc.get("source_uri")]
    merged_allowed = [source.strip() for source in allowed_sources if source.strip()]
    merged_allowed.extend(item for item in source_hosts if item)
    merged_allowed.append(tid)
    merged_allowed = list(dict.fromkeys(merged_allowed))
    profile = TenantProfile(
        tenant_id=tid,
        company_name=company_name,
        language=language,
        industry=industry,
        isolation_level="index-per-tenant",
        deployment_mode=deployment_mode,
        allowed_sources=tuple(merged_allowed),
        sensitive_fields=("password", "credential", "api_key", "payroll", "personal_id", "个人信息", "密码"),
    )
    connector = AdminTextConnector(tid, company_name, documents)
    report = SecureIngestionPipeline(profile).scan(connector)
    indexed_chunks = 0
    if report.accepted_documents:
        indexed_chunks = append_tenant_chunks(profile, report.accepted_documents)
        write_tenant_profile(profile)
    active_sources = []
    if sample_text.strip():
        active_sources.append("Uploaded Text")
    if source_urls:
        active_sources.append("Public URL")
    return IngestionReport(
        tenant_profile=report.tenant_profile,
        documents_seen=report.documents_seen,
        documents_accepted=report.documents_accepted,
        documents_quarantined=report.documents_quarantined,
        duplicate_documents=report.duplicate_documents,
        findings=tuple(list(report.findings) + fetch_findings),
        accepted_documents=report.accepted_documents,
        quarantined_documents=report.quarantined_documents,
        indexed_chunks=indexed_chunks,
        tenant_query_ready=indexed_chunks > 0,
        chunk_store=str(TENANT_CHUNKS_PATH),
        profile_store=str(TENANT_PROFILES_PATH),
        recommended_profile={
            **report.recommended_profile,
            "source_kinds_requested": source_kinds,
            "source_kinds_active": active_sources,
            "query_ready": indexed_chunks > 0,
            "indexed_chunks": indexed_chunks,
        },
    )
