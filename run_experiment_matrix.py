#!/usr/bin/env python3
"""Run the handbook experiment matrix end-to-end.

Runs:
1. All no-defense baselines, including embedding+llm
2. Chooses the best no-defense baseline by overall proxy score
3. Runs defended ablations and full-stack defense
4. Writes summary files under outputs/experiment_matrix
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
BASELINE_OUT = PROJECT_ROOT / "outputs" / "experiment_matrix" / "baselines"
DEFENSE_OUT = PROJECT_ROOT / "outputs" / "experiment_matrix" / "defenses"
SUMMARY_DIR = PROJECT_ROOT / "outputs" / "experiment_matrix" / "summary"


BASELINE_VARIANTS = [
    "rag1_tfidf",
    "rag2_bm25",
    "rag3_llm_only",
    "rag4_tfidf_llm",
    "rag5_bm25_llm",
    "rag6_hybrid_llm",
    "rag7_embedding_llm",
]


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
        "--embedding-base-url",
        args.base_url,
        "--embedding-api-key-env",
        args.api_key_env,
        "--embedding-model",
        args.embedding_model,
    ]
    return cmd


def defended_variant_for_baseline(best_variant: str) -> str:
    if best_variant == "rag7_embedding_llm":
        return "defended_embedding_llm"
    return "defended_hybrid_llm"


def defense_command(
    defended_variant: str,
    control_variant: str,
    run_name: str,
    extra_flags: list[str],
    args: argparse.Namespace,
) -> list[str]:
    cmd = [
        sys.executable,
        "defended_variants.py",
        "--variant",
        defended_variant,
        "--control-recommendation",
        control_variant,
        "--run-name",
        run_name,
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
        "--embedding-base-url",
        args.base_url,
        "--embedding-api-key-env",
        args.api_key_env,
        "--embedding-model",
        args.embedding_model,
    ]
    cmd.extend(extra_flags)
    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run baseline and defended experiment matrix.")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--chat-model", default=os.getenv("CHAT_MODEL", "Qwen/Qwen2.5-72B-Instruct"))
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"))
    parser.add_argument("--skip-defenses", action="store_true")
    parser.add_argument(
        "--reuse-baselines",
        action="store_true",
        help="Score existing baseline results instead of rerunning variants whose results.csv already exists.",
    )
    parser.add_argument(
        "--skip-missing-baselines",
        action="store_true",
        help="When reusing baselines, skip variants without an existing results.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    baseline_rows: list[dict[str, object]] = []
    for variant in BASELINE_VARIANTS:
        result_path = BASELINE_OUT / variant / "results.csv"
        if not (args.reuse_baselines and result_path.exists()):
            if args.reuse_baselines and args.skip_missing_baselines:
                print(f"Skipping missing baseline result: {result_path}")
                continue
            run_command(baseline_command(variant, args))
        metrics = evaluate(result_path)
        metrics["variant"] = variant
        baseline_rows.append(metrics)

    baseline_rows.sort(key=lambda row: row["overall_proxy"], reverse=True)
    write_csv(SUMMARY_DIR / "baseline_scores.csv", baseline_rows)
    (SUMMARY_DIR / "baseline_scores.json").write_text(json.dumps(baseline_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    best_variant = str(baseline_rows[0]["variant"])
    best_defended_variant = defended_variant_for_baseline(best_variant)
    recommendation = {
        "best_no_defense_variant": best_variant,
        "best_no_defense_overall_proxy": baseline_rows[0]["overall_proxy"],
        "recommended_defended_variant": best_defended_variant,
    }
    (SUMMARY_DIR / "recommendation.json").write_text(json.dumps(recommendation, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.skip_defenses:
        print(json.dumps(recommendation, indent=2, ensure_ascii=False))
        return

    defense_rows: list[dict[str, object]] = []
    for run_name, extra_flags in DEFENSE_RUNS:
        effective_run_name = f"{best_defended_variant}__{run_name}"
        run_command(
            defense_command(
                best_defended_variant,
                best_variant,
                effective_run_name,
                extra_flags,
                args,
            )
        )
        metrics = evaluate(DEFENSE_OUT / effective_run_name / "results.csv")
        metrics["variant"] = best_defended_variant
        metrics["run_name"] = effective_run_name
        metrics["defense_profile"] = run_name
        defense_rows.append(metrics)

    defense_rows.sort(key=lambda row: row["overall_proxy"], reverse=True)
    write_csv(SUMMARY_DIR / "defense_scores.csv", defense_rows)
    (SUMMARY_DIR / "defense_scores.json").write_text(json.dumps(defense_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    final_summary = {
        "recommendation": recommendation,
        "baseline_count": len(baseline_rows),
        "defense_run_count": len(defense_rows),
        "best_defense_run": defense_rows[0] if defense_rows else None,
    }
    (SUMMARY_DIR / "final_summary.json").write_text(json.dumps(final_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(final_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
