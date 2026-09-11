"""CLI Entry Point for AI Evaluation Runner

Usage:
    python -m app.intelligence.evaluation.cli --category all
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.intelligence.evaluation.runner import EvaluationRunner
from app.intelligence.service import AIService


async def main():
    parser = argparse.ArgumentParser(description="AI Pipeline Evaluation Framework CLI")
    parser.add_argument("--category", choices=["all", "resumes", "jobs"], default="all")
    parser.add_argument("--out", type=str, default=None, help="Path to save evaluation report JSON")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"       AI EVALUATION FRAMEWORK - BENCHMARK RUNNER      ")
    print(f"=======================================================")
    print(f"Category: {args.category}")

    runner = EvaluationRunner()
    fixtures = runner.load_fixtures(args.category)
    print(f"Loaded {len(fixtures)} fixtures from {runner.fixtures_dir}")

    if not fixtures:
        print("No fixtures found to evaluate.")
        sys.exit(1)

    print("Running evaluations...\n")
    report = await runner.run_evaluation(args.category)

    out_file = runner.save_report(report, Path(args.out) if args.out else None)

    print(f"Evaluation Complete!")
    print(f"Schema Validity Rate: {report['schema_valid_rate'] * 100:.1f}%")
    print(f"Average Latency:      {report['avg_latency_ms']} ms")
    print(f"Resume Skill Avg F1:  {report['summary']['avg_resume_skill_f1']}")
    print(f"Job Req Skill Avg F1: {report['summary']['avg_job_required_skill_f1']}")
    print(f"\nDetailed report saved to: {out_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
