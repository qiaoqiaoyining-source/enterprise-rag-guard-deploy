# EnterpriseRAG-Guard Submission Package

This package contains the final course-project deliverables for EnterpriseRAG-Guard.

## Public Demo

Public website:

https://enterprise-rag-guard-deploy.onrender.com

GitHub repository:

https://github.com/qiaoqiaoyining-source/enterprise-rag-guard-deploy

## Package Contents

- `paper/`: final project paper in Word format and editable Markdown content draft.
- `slides/`: final presentation deck. The last slide includes a placeholder for a recorded website demo.
- `code/`: core reproducible project scripts and dependency file.
- `data/`: final clean corpus, evaluation questions, and company security profiles.
- `results/`: B0-B7 experimental outputs, ablation summary, attack-surface analysis, transfer matrix, and per-company results.
- `deployment/`: Docker and Render deployment configuration.
- `docs/`: technical notes for the final EnterpriseRAG-Guard design.

## Reproduction

Install dependencies:

```bash
python3 -m pip install -r code/requirements.txt
```

Rebuild corpus:

```bash
python3 code/build_enterprise_corpus.py --china-target 200 --timeout 35
```

Run evaluation:

```bash
python3 code/run_guard_transfer_experiment.py --skip-build-corpus
```

Start local website:

```bash
python3 code/guard_demo_server.py
```

## Security Note

This package intentionally excludes `.env`, API keys, virtual environments, embedding caches, local browser state, and deployment account screenshots. For model-backed generation, configure `DEEPSEEK_API_KEY` and `DASHSCOPE_API_KEY` as environment variables locally or in the cloud provider.
