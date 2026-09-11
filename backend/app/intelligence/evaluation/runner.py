"""AI Evaluation Suite Runner

Loads fixtures, invokes AIService or LLM provider, evaluates metrics,
and writes structured evaluation results.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from app.intelligence.evaluation.metrics import (
    evaluate_candidate_profile_extraction,
    evaluate_job_enrichment_extraction,
)
from app.intelligence.service import AIService

logger = logging.getLogger("eval_runner")


class EvaluationRunner:
    def __init__(self, service: AIService | None = None, fixtures_dir: Path | None = None):
        self.service = service or AIService()
        self.fixtures_dir = fixtures_dir or (
            Path(__file__).resolve().parent.parent.parent.parent / "tests" / "evaluation" / "fixtures"
        )

    def load_fixtures(self, category: str = "all") -> list[dict[str, Any]]:
        """Load fixture JSON files."""
        fixtures: list[dict[str, Any]] = []
        if not self.fixtures_dir.exists():
            return fixtures

        subdirs = ["resumes", "jobs"] if category == "all" else [category]
        for sub in subdirs:
            p = self.fixtures_dir / sub
            if not p.exists():
                continue
            for f in p.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        data = json.load(file)
                        fixtures.append(data)
                except Exception as e:
                    logger.warning(f"Failed to load fixture {f}: {e}")
        return fixtures

    async def run_evaluation(self, category: str = "all") -> dict[str, Any]:
        """Execute evaluation across loaded fixtures."""
        fixtures = self.load_fixtures(category)
        results: list[dict[str, Any]] = []
        total_start = time.perf_counter()

        for fixture in fixtures:
            fix_id = fixture.get("id", "unknown")
            cat = fixture.get("category")
            ground_truth = fixture.get("ground_truth", {})

            case_start = time.perf_counter()
            schema_valid = True
            error = None
            pred_data: dict[str, Any] = {}

            try:
                if cat == "resume":
                    input_text = fixture.get("input_text", "")
                    profile_out = await self.service.extract_candidate_profile(input_text)
                    pred_data = profile_out.model_dump()
                    metrics = evaluate_candidate_profile_extraction(pred_data, ground_truth)
                elif cat == "job":
                    title = fixture.get("title", "")
                    description = fixture.get("description", "")
                    enrichment_out = await self.service.enrich_job(title, description)
                    pred_data = enrichment_out.model_dump()
                    metrics = evaluate_job_enrichment_extraction(pred_data, ground_truth)
                else:
                    metrics = {}
            except Exception as exc:
                schema_valid = False
                error = str(exc)
                metrics = {}

            latency_ms = round((time.perf_counter() - case_start) * 1000, 2)

            results.append({
                "fixture_id": fix_id,
                "category": cat,
                "schema_valid": schema_valid,
                "latency_ms": latency_ms,
                "error": error,
                "metrics": metrics,
                "predicted": pred_data,
                "ground_truth": ground_truth,
            })

        total_duration_ms = round((time.perf_counter() - total_start) * 1000, 2)

        # Calculate summary aggregate
        valid_count = sum(1 for r in results if r["schema_valid"])
        avg_latency = round(sum(r["latency_ms"] for r in results) / len(results), 2) if results else 0

        # Skill F1 averages
        resume_f1s = [
            r["metrics"]["skill_f1"]
            for r in results
            if r["category"] == "resume" and "skill_f1" in r["metrics"]
        ]
        avg_resume_skill_f1 = round(sum(resume_f1s) / len(resume_f1s), 4) if resume_f1s else 0.0

        job_req_f1s = [
            r["metrics"]["required_skills_f1"]
            for r in results
            if r["category"] == "job" and "required_skills_f1" in r["metrics"]
        ]
        avg_job_req_skill_f1 = round(sum(job_req_f1s) / len(job_req_f1s), 4) if job_req_f1s else 0.0

        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_fixtures": len(results),
            "schema_valid_rate": round(valid_count / len(results), 4) if results else 0.0,
            "avg_latency_ms": avg_latency,
            "total_duration_ms": total_duration_ms,
            "summary": {
                "avg_resume_skill_f1": avg_resume_skill_f1,
                "avg_job_required_skill_f1": avg_job_req_skill_f1,
            },
            "cases": results,
        }

        return report

    def save_report(self, report: dict[str, Any], output_path: Path | None = None) -> Path:
        """Save report as JSON in backend/data/eval_reports/."""
        if output_path is None:
            output_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "eval_reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "latest_eval.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return output_path
