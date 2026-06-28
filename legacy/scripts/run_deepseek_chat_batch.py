#!/usr/bin/env python3
"""Run the full DeepSeek + DashScope evaluation batch.

The chat-generation variants use a DeepSeek OpenAI-compatible chat endpoint.
The embedding variant uses a separate OpenAI-compatible embedding endpoint,
such as Alibaba Cloud DashScope compatible mode.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from evaluate_results import evaluate


PROJECT_ROOT = Path(__file__).resolve().parent
QUESTIONS = PROJECT_ROOT / "questions" / "evaluation_questions_v2.csv"
POISON = PROJECT_ROOT / "handbook-main" / "adversarial_poisoned_chunks.csv"
OUT_ROOT = PROJECT_ROOT / "outputs" / "deepseek_batch"
BASELINE_OUT = OUT_ROOT / "baselines"
DEFENSE_OUT = OUT_ROOT / "defenses"
SUMMARY_DIR = OUT_ROOT / "summary"

CHAT_BASELINES = [
    "rag1_tfidf",
    "rag2_bm25",
    "rag3_llm_only",
    "rag4_tfidf_llm",
    "rag5_bm25_llm",
    "rag6_hybrid_llm",
]
EMBEDDING_BASELINE = "rag7_embedding_llm"

DEFENSE_RUNS = [
    ("question_refusal_only", ["--no-enable-chunk-filter", "--no-enable-instruction-isolation", "--no-enable-citation-verification"]),
    ("chunk_filter_only", ["--no-enable-question-refusal", "--no-enable-instruction-isolation", "--no-enable-citation-verification"]),
    ("instruction_isolation_only", ["--no-enable-question-refusal", "--no-enable-chunk-filter", "--no-enable-citation-verification"]),
    ("citation_verification_only", ["--no-enable-question-refusal", "--no-enable-chunk-filter", "--no-enable-instruction-isolation"]),
    ("chunk_plus_isolation", ["--no-enable-question-refusal", "--enable-chunk-filter", "--enable-instruction-isolation", "--no-enable-citation-verification"]),
    ("full_stack", []),
    ("full_stack_repair", ["--enable-llm-repair"]),
]


def run_command(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT, env=os.environ.copy())


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def add_embedding_args(cmd: list[str], args: argparse.Namespace) -> None:
    cmd.extend(
        [
            "--embedding-base-url",
            args.embedding_base_url,
            "--embedding-model",
            args.embedding_model,
            "--embedding-api-key-env",
            args.embedding_api_key_env,
            "--embedding-timeout",
            str(args.embedding_timeout),
            "--embedding-retries",
            str(args.embedding_retries),
        ]
    )


def baseline_command(variant: str, args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        "rag_variants.py",
        "--variant",
        variant,
        "--questions",
        str(QUESTIONS),
        "--extra-chunks",
        str(POISON),
        "--outdir",
        str(BASELINE_OUT),
        "--base-url",
        args.base_url,
        "--api-key-env",
        args.api_key_env,
        "--llm-protocol",
        "openai",
        "--model",
        args.chat_model,
        "--llm-timeout",
        str(args.llm_timeout),
        "--llm-retries",
        str(args.llm_retries),
        "--max-tokens",
        str(args.max_tokens),
    ]
    if variant == EMBEDDING_BASELINE:
        add_embedding_args(cmd, args)
    return cmd


def defense_command(variant: str, run_name: str, extra_flags: list[str], args: argparse.Namespace) -> list[str]:
    effective_run_name = f"{variant}__{run_name}"
    cmd = [
        sys.executable,
        "defended_variants.py",
        "--variant",
        variant,
        "--control-recommendation",
        args.control_variant,
        "--run-name",
        effective_run_name,
        "--questions",
        str(QUESTIONS),
        "--extra-chunks",
        str(POISON),
        "--outdir",
        str(DEFENSE_OUT),
        "--base-url",
        args.base_url,
        "--api-key-env",
        args.api_key_env,
        "--llm-protocol",
        "openai",
        "--model",
        args.chat_model,
        "--llm-timeout",
        str(args.llm_timeout),
        "--llm-retries",
        str(args.llm_retries),
        "--max-tokens",
        str(args.max_tokens),
    ]
    if variant == "defended_embedding_llm":
        add_embedding_args(cmd, args)
    cmd.extend(extra_flags)
    return cmd


def score_baseline(variant: str, args: argparse.Namespace) -> dict[str, object]:
    result_path = BASELINE_OUT / variant / "results.csv"
    if not (args.reuse_existing and result_path.exists()):
        run_command(baseline_command(variant, args))
    metrics = evaluate(result_path)
    metrics["variant"] = variant
    metrics["retrieval_family"] = "embedding" if variant == EMBEDDING_BASELINE else "lexical_or_hybrid"
    metrics["chat_model"] = args.chat_model
    metrics["embedding_model"] = args.embedding_model if variant == EMBEDDING_BASELINE else ""
    return metrics


def score_defense(variant: str, run_name: str, extra_flags: list[str], args: argparse.Namespace) -> dict[str, object]:
    effective_run_name = f"{variant}__{run_name}"
    result_path = DEFENSE_OUT / effective_run_name / "results.csv"
    if not (args.reuse_existing and result_path.exists()):
        run_command(defense_command(variant, run_name, extra_flags, args))
    metrics = evaluate(result_path)
    metrics["variant"] = variant
    metrics["run_name"] = effective_run_name
    metrics["defense_profile"] = run_name
    metrics["retrieval_family"] = "embedding" if variant == "defended_embedding_llm" else "hybrid"
    metrics["chat_model"] = args.chat_model
    metrics["embedding_model"] = args.embedding_model if variant == "defended_embedding_llm" else ""
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeepSeek chat plus DashScope embedding experiments.")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1"))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--chat-model", default=os.getenv("CHAT_MODEL", "deepseek-chat"))
    parser.add_argument("--control-variant", default="rag6_hybrid_llm")
    parser.add_argument("--llm-timeout", type=int, default=120)
    parser.add_argument("--llm-retries", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=500)

    parser.add_argument(
        "--embedding-base-url",
        default=os.getenv("EMBEDDING_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )
    parser.add_argument("--embedding-api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"))
    parser.add_argument("--embedding-timeout", type=int, default=120)
    parser.add_argument("--embedding-retries", type=int, default=2)

    parser.add_argument("--skip-defenses", action="store_true")
    parser.add_argument("--skip-embedding", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true", help="Reuse existing result CSVs instead of re-running model calls.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    baselines = list(CHAT_BASELINES)
    if not args.skip_embedding:
        baselines.append(EMBEDDING_BASELINE)

    baseline_rows = [score_baseline(variant, args) for variant in baselines]
    baseline_rows.sort(key=lambda row: row["overall_proxy"], reverse=True)
    write_csv(SUMMARY_DIR / "baseline_scores_all.csv", baseline_rows)
    (SUMMARY_DIR / "baseline_scores_all.json").write_text(json.dumps(baseline_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(SUMMARY_DIR / "baseline_scores.csv", baseline_rows)
    (SUMMARY_DIR / "baseline_scores.json").write_text(json.dumps(baseline_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    defense_rows: list[dict[str, object]] = []
    if not args.skip_defenses:
        defense_variants = ["defended_hybrid_llm"]
        if not args.skip_embedding:
            defense_variants.append("defended_embedding_llm")
        for variant in defense_variants:
            for run_name, extra_flags in DEFENSE_RUNS:
                defense_rows.append(score_defense(variant, run_name, extra_flags, args))
        defense_rows.sort(key=lambda row: row["overall_proxy"], reverse=True)
        write_csv(SUMMARY_DIR / "defense_scores_all.csv", defense_rows)
        (SUMMARY_DIR / "defense_scores_all.json").write_text(json.dumps(defense_rows, indent=2, ensure_ascii=False), encoding="utf-8")
        write_csv(SUMMARY_DIR / "defense_scores.csv", defense_rows)
        (SUMMARY_DIR / "defense_scores.json").write_text(json.dumps(defense_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    final_summary = {
        "chat_model": args.chat_model,
        "embedding_model": "" if args.skip_embedding else args.embedding_model,
        "embedding_base": "" if args.skip_embedding else args.embedding_base_url,
        "baseline_count": len(baseline_rows),
        "defense_run_count": len(defense_rows),
        "best_baseline": baseline_rows[0] if baseline_rows else None,
        "best_defense": defense_rows[0] if defense_rows else None,
    }
    (SUMMARY_DIR / "final_summary_all.json").write_text(json.dumps(final_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (SUMMARY_DIR / "final_summary.json").write_text(json.dumps(final_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(final_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
