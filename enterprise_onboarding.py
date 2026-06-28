#!/usr/bin/env python3
"""Tenant onboarding and secure ingestion primitives for EnterpriseRAG-Guard.

The research demo ships with seven public benchmark companies. This module
models the product path for a new enterprise customer: create a tenant, connect
knowledge sources, scan documents before indexing, and generate a tenant profile
without rewriting the guard core.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass, field

from enterprise_rag_guard import CHUNK_RISK_PATTERNS, UNSAFE_QUERY_PATTERNS, detect


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


class DemoTextConnector(KnowledgeConnector):
    """A no-dependency connector used by the web demo onboarding wizard."""

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
        source_uri = row.get("source_uri") or "demo://uploaded-text"
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
            else:
                accepted += 1

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

        allowed = any(source in doc.source_uri for source in self.tenant_profile.allowed_sources)
        if self.tenant_profile.allowed_sources and not allowed and not doc.source_uri.startswith("demo://"):
            findings.append(
                IngestionFinding(
                    "medium",
                    "unverified_source",
                    f"{doc.title} comes from an unapproved source URI.",
                    "review",
                )
            )
        return findings


def tenant_id(company_name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", company_name.lower()).strip("-") or "tenant"
    suffix = hashlib.sha1(f"{company_name}-{time.time()}".encode("utf-8")).hexdigest()[:6]
    return f"{base}-{suffix}"


def create_demo_tenant(
    company_name: str,
    language: str,
    industry: str,
    deployment_mode: str,
    source_kinds: list[str],
    allowed_sources: list[str],
    sample_text: str,
) -> IngestionReport:
    tid = tenant_id(company_name)
    profile = TenantProfile(
        tenant_id=tid,
        company_name=company_name,
        language=language,
        industry=industry,
        isolation_level="index-per-tenant",
        deployment_mode=deployment_mode,
        allowed_sources=tuple(source.strip() for source in allowed_sources if source.strip()),
        sensitive_fields=("password", "credential", "api_key", "payroll", "personal_id", "个人信息", "密码"),
    )
    documents = [
        {
            "title": f"{company_name} onboarding sample",
            "content": sample_text
            or f"{company_name} employees can ask HR, IT, compliance, and policy questions through the secure knowledge assistant.",
            "source_uri": "demo://uploaded-text",
            "department": "HR",
        }
    ]
    connector = DemoTextConnector(tid, company_name, documents)
    report = SecureIngestionPipeline(profile).scan(connector)
    data = report.to_dict()
    data["source_kinds"] = source_kinds
    return IngestionReport(
        tenant_profile=report.tenant_profile,
        documents_seen=report.documents_seen,
        documents_accepted=report.documents_accepted,
        documents_quarantined=report.documents_quarantined,
        duplicate_documents=report.duplicate_documents,
        findings=report.findings,
        recommended_profile={**report.recommended_profile, "source_kinds": source_kinds},
    )
