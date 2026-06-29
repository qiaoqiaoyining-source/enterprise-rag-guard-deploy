# EnterpriseRAG-Guard

EnterpriseRAG-Guard is a course project on prompt-injection defense for
company-specific RAG knowledge agents. The final version treats each enterprise
as an isolated tenant with its own knowledge boundary, then evaluates whether one
shared security layer transfers across different companies, languages, and
attack surfaces.

```text
Company Agent = Universal Security Core + Company Security Profile + Company Knowledge Base
```

For product deployment, the formula extends to:

```text
EnterpriseRAG-Guard Platform =
Connector Layer + Tenant Isolation + Universal Guard + Company Adapter + Evaluation + Monitoring
```

## What This Project Demonstrates

- A final transferable RAG defense framework, not several disconnected RAG demos.
- Seven company knowledge bases: Made Tech, GitLab, 37signals/Basecamp, Valve,
  Tencent, BYD, and Huawei.
- Chinese company coverage with 200 chunks each for Tencent, BYD, and Huawei.
- A bilingual security console where an employee can ask normal questions, or a
  red-team user can try prompt-injection attacks and watch the defense trace.
- A product-style onboarding path where a new enterprise can connect real
  pasted knowledge text or public URLs, run secure ingestion, generate a tenant
  security profile, and immediately query the new tenant Agent.
- A B0-B7 ablation experiment showing how provenance checks, quarantine,
  instruction/evidence isolation, extraction, verification, and repair/refusal
  change attack success.

Historical baseline scripts, old outputs, and the previous coursework track are
kept under `legacy/` for reproducibility. The project root now presents the final
EnterpriseRAG-Guard version.

## Final Corpus

The final clean corpus is:

```text
data/enterprise_corpus/company_chunks.csv
```

Current generated corpus:

| Company | Language | Chunks |
| --- | --- | ---: |
| Made Tech | English | 134 |
| GitLab | English | 159 |
| 37signals/Basecamp | English | 111 |
| Valve | English | 80 |
| Tencent | Chinese | 200 |
| BYD | Chinese | 200 |
| Huawei | Chinese | 200 |
| **Total** |  | **1084** |

Corpus origin:

| Origin | Chunks |
| --- | ---: |
| Local clean Made Tech handbook chunks | 134 |
| Fetched public HTML handbook pages | 270 |
| Fetched public PDF reports/handbooks | 680 |

Synthetic poisoned documents are not counted as clean company corpus. They are
created only for evaluation and interactive red-team demonstrations.

## Product Architecture

The project is no longer only a preloaded seven-company prototype. It now models
how a customer would buy and deploy the system:

```text
Enterprise data sources
  -> Connector layer
  -> Secure ingestion
  -> Tenant knowledge store
  -> EnterpriseRAG-Guard data plane
  -> Employee knowledge assistant
```

Supported product modules:

- **Connect**: normalize uploaded files, websites, SharePoint/Confluence-style
  sources, internal APIs, databases, and existing vector stores behind one
  connector contract.
- **Protect**: query scanning, chunk scanning, secure reranking, evidence
  isolation, citation verification, and repair/refusal.
- **Evaluate**: red-team prompt-injection tests and security regression checks.
- **Observe**: risk logs, quarantined documents, high-risk sources, suspicious
  users, and policy-version changes.

`enterprise_onboarding.py` contains the productized onboarding primitives:

- `KnowledgeConnector`
- `DocumentRecord`
- `TenantProfile`
- `SecureIngestionPipeline`
- `IngestionReport`

The web server implements `/api/onboard` as a real ingestion endpoint for the
course prototype. It accepts administrator-provided text and public URLs,
fetches/normalizes the content, scans the documents, chunks accepted documents,
writes a tenant-isolated runtime index under `data/tenant_agents/`, generates a
tenant profile, reloads the guard, and makes the new company immediately
available in the employee query page.

SharePoint, Confluence, existing vector database, and internal API connectors are
represented as connector contracts and product choices, but they require real
enterprise credentials/OAuth setup before they can be enabled in production. The
project does not pretend those private systems are connected without credentials.

## Defense Design

EnterpriseRAG-Guard combines:

1. Provenance-aware retrieval using company, source domain, trust level, content
   hash, document version, and instruction-risk metadata.
2. Query and document risk detection for English and Chinese attacks.
3. Tenant/company security profiles for allowed sources, sensitive fields,
   citation rules, deployment mode, isolation level, and risk thresholds.
4. Instruction/evidence isolation, treating retrieved documents as untrusted
   evidence rather than executable instructions.
5. Extractor-generator isolation, where raw documents are converted into
   evidence claims before answer generation.
6. Citation and policy verification for missing, fabricated, poisoned, or
   cross-company citations.
7. Repair/refusal behavior when a response cannot be safely grounded.

The implementation is deterministic and inspectable so the defense trace can be
shown in the website and explained in the report.

## Rebuild And Run

Use Python with `pypdf` available. Without `pypdf`, PDF sources are skipped and
the Chinese company corpus will be incomplete.

Install the minimal dependency:

```bash
python3 -m pip install -r requirements.txt
```

Build the final corpus:

```bash
python3 build_enterprise_corpus.py --china-target 200 --timeout 35
```

Run the full B0-B7 transfer experiment:

```bash
python3 run_guard_transfer_experiment.py --skip-build-corpus
```

Start the visual security console:

```bash
python3 guard_demo_server.py
```

Then open:

```text
http://127.0.0.1:8765
```

`127.0.0.1` is a local address. It is only available on the machine running the
demo. For a temporary classroom demo, a tunnel can expose the local service, but
tunnel URLs are not stable enough for a public product demo. For a stable
everyone-can-open URL, deploy the project to a cloud web service and set the
model keys as environment variables.

By default, the product console uses the local verified-evidence generator so
the benchmark is deterministic and can run without paid model calls. For the
full product demo, copy `.env.example` to `.env` and set local keys only on your
machine:

```bash
cp .env.example .env
python3 guard_demo_server.py
```

The optional model-backed stack is:

- DeepSeek chat for grounded answer generation;
- DeepSeek query rewriting for Chinese-to-English retrieval expansion;
- Alibaba Cloud Bailian/DashScope `text-embedding-v4` for semantic reranking;
- EnterpriseRAG-Guard for provenance filtering, quarantine, evidence isolation,
  citation verification, and repair/refusal.

Do not commit API keys. `.env` is ignored by Git. The page badge shows the
active stack, for example `Guard + DeepSeek + 双语改写 + 百炼Embedding`.

## Public Deployment

The repository includes production deployment files:

```text
Dockerfile      # container entrypoint for cloud hosting
render.yaml     # one-click Render-style web service definition
docker-compose.yml
deploy/Caddyfile
.dockerignore   # excludes local secrets and caches from the image
```

Recommended cloud environment variables:

```text
DEEPSEEK_API_KEY=...
DASHSCOPE_API_KEY=...
GUARD_HOST=0.0.0.0
GUARD_USE_LLM=1
GUARD_USE_TRANSLATION=1
GUARD_USE_EMBEDDING=1
GUARD_FAST_MODE=1
GUARD_EMBEDDING_SHORTLIST=20
```

Cloud platforms usually inject a `PORT` variable automatically. The server reads
both `GUARD_PORT` and `PORT`, so the same code works locally and on hosted web
services. Never place API keys in GitHub files; configure them only in the cloud
provider's private environment-variable settings.

Two stable public deployment paths are supported:

1. Render Blueprint:
   connect this GitHub repository, let Render read `render.yaml`, and set the two
   secret keys in Render's environment-variable UI. The blueprint uses a starter
   web service plus a 1 GB persistent disk mounted at `/app/data/tenant_agents`
   so newly onboarded enterprise tenants do not disappear after restart.

2. Cloud server with a domain:
   point a domain to an Aliyun/Tencent Cloud/VPS server, install Docker, create a
   server-side `.env` with `DOMAIN`, `DEEPSEEK_API_KEY`, and
   `DASHSCOPE_API_KEY`, then start `docker compose up -d`. Caddy terminates HTTPS
   and proxies traffic to the Python RAG service.

The project cannot deploy itself to a public cloud without the owner's cloud
account authorization. Temporary tunnel URLs are only for short demos and are not
equivalent to a stable public product URL.

## Current Experiment Results

The latest run uses 224 evaluation cases across seven companies:

| Metric | B0 Plain RAG | B7 Full Guard |
| --- | ---: | ---: |
| Normal task success | 67.86% | 100.00% |
| Attack success rate | 89.29% | 25.00% |
| Attack resistance rate | 10.71% | 75.00% |
| Citation error rate | 58.48% | 0.00% |
| Poison survival rate | 100.00% | 0.00% |

Main outputs:

```text
outputs/enterprise_rag_guard/results.csv
outputs/enterprise_rag_guard/summary/ablation_summary.csv
outputs/enterprise_rag_guard/summary/transfer_matrix.csv
outputs/enterprise_rag_guard/summary/attack_surface_summary.csv
outputs/enterprise_rag_guard/by_company/
outputs/enterprise_rag_guard/by_attack_surface/
```

These metrics are deterministic proxy metrics, not human grading. They are useful
for controlled comparison and presentation, but should not be presented as proof
that prompt injection is solved.

## Security Console Features

The website is designed as a customer-facing enterprise knowledge assistant, not
as a raw experiment dashboard. It supports:

- a Chinese-first employee knowledge search experience;
- English switching for foreign-company questions;
- customer-facing product introduction;
- employee query mode;
- red-team challenge mode with B0 control vs B7 secure answers;
- defense trace, safe evidence, and quarantine panels;
- a "Create Your Company Agent" onboarding wizard;
- secure ingestion report and generated tenant profile;
- runtime tenant indexing for admin-pasted text and public URLs.

## Key Files

```text
build_enterprise_corpus.py                 # builds the final real-company corpus
enterprise_rag_guard.py                    # guard core and defense pipeline
enterprise_onboarding.py                   # tenant onboarding and secure ingestion
run_guard_transfer_experiment.py           # B0-B7 transfer/ablation runner
guard_demo_server.py                       # product-style web demo and APIs
data/company_profiles.json                 # company security profiles
data/enterprise_corpus/company_chunks.csv  # final clean corpus
docs/enterprise_rag_guard.md               # detailed technical explanation
```
