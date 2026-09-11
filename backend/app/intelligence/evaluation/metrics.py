"""AI Evaluation Metrics Engine

Calculates precision, recall, F1, accuracy, and hallucination scores
comparing structured AI extractions against ground truth benchmarks.
"""

from typing import Any


def normalize_token(token: str) -> str:
    """Normalize string token for comparison (lowercase, stripped, remove special chars)."""
    return "".join(c for c in token.lower() if c.isalnum())


def set_precision_recall_f1(predicted: list[str], ground_truth: list[str]) -> dict[str, float]:
    """Calculate token overlap metrics using normalized tokens."""
    pred_norm = {normalize_token(p) for p in predicted if p and normalize_token(p)}
    truth_norm = {normalize_token(g) for g in ground_truth if g and normalize_token(g)}

    if not truth_norm and not pred_norm:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "overlap_count": 0}

    if not pred_norm:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "overlap_count": 0}

    if not truth_norm:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "overlap_count": 0}

    intersection = pred_norm.intersection(truth_norm)
    precision = len(intersection) / len(pred_norm)
    recall = len(intersection) / len(truth_norm)
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "overlap_count": len(intersection),
    }


def evaluate_candidate_profile_extraction(predicted: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Evaluate candidate profile extraction against ground truth."""
    pred_skills = (
        predicted.get("programming_languages", [])
        + predicted.get("frameworks", [])
        + predicted.get("databases", [])
        + predicted.get("cloud", [])
        + predicted.get("tools", [])
        + predicted.get("skills", [])
    )
    truth_skills = (
        ground_truth.get("programming_languages", [])
        + ground_truth.get("frameworks", [])
        + ground_truth.get("databases", [])
        + ground_truth.get("cloud", [])
        + ground_truth.get("tools", [])
        + ground_truth.get("skills", [])
    )

    skill_metrics = set_precision_recall_f1(pred_skills, truth_skills)

    pred_exp_level = (predicted.get("experience_level") or "").upper()
    truth_exp_level = (ground_truth.get("experience_level") or "").upper()
    exp_level_match = 1.0 if pred_exp_level == truth_exp_level else 0.0

    pred_exp_years = int(predicted.get("experience_years") or 0)
    truth_exp_years = int(ground_truth.get("experience_years") or 0)
    exp_year_diff = abs(pred_exp_years - truth_exp_years)

    return {
        "skill_precision": skill_metrics["precision"],
        "skill_recall": skill_metrics["recall"],
        "skill_f1": skill_metrics["f1"],
        "experience_level_match": exp_level_match,
        "experience_years_diff": exp_year_diff,
        "predicted_count": len(pred_skills),
        "truth_count": len(truth_skills),
    }


def evaluate_job_enrichment_extraction(predicted: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Evaluate job enrichment & skill extraction against ground truth."""
    req_metrics = set_precision_recall_f1(
        predicted.get("required_skills", []),
        ground_truth.get("required_skills", []),
    )
    pref_metrics = set_precision_recall_f1(
        predicted.get("preferred_skills", []),
        ground_truth.get("preferred_skills", []),
    )
    tech_stack_metrics = set_precision_recall_f1(
        predicted.get("tech_stack", []),
        ground_truth.get("tech_stack", []),
    )

    pred_seniority = (predicted.get("seniority") or "").upper()
    truth_seniority = (ground_truth.get("seniority") or "").upper()
    seniority_match = 1.0 if pred_seniority == truth_seniority else 0.0

    return {
        "required_skills_f1": req_metrics["f1"],
        "required_skills_precision": req_metrics["precision"],
        "required_skills_recall": req_metrics["recall"],
        "preferred_skills_f1": pref_metrics["f1"],
        "tech_stack_f1": tech_stack_metrics["f1"],
        "seniority_match": seniority_match,
    }
