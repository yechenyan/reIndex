from __future__ import annotations

from pdf_extractor_pdf.artifacts import artifact_hash, read_json, write_json
from pdf_extractor_pdf.agents import verify_role_separation
from pdf_extractor_pdf.job import Job
from pdf_extractor_pdf.workflow import require_phase, update_phase


def finalize(job: Job) -> dict:
    require_phase(job.evidence_dir, "reviewed")
    review_path = job.evidence_dir / "review.json"
    review = read_json(review_path)
    if not review.get("passed") or review.get("issues"):
        raise ValueError("review has unresolved issues")
    threshold = float(job.policy.get("merge_candidate_threshold", 0.85))
    blocking = [item for item in review.get("merge_candidates", []) if item["confidence"] >= threshold and not item.get("resolved")]
    if blocking:
        raise ValueError("high-confidence merge candidates must be resolved")
    current = {
        "inventory_sha256": artifact_hash(job.inventory),
        "reference_sha256": artifact_hash(job.reference),
        "extractor_sha256": artifact_hash(job.main),
    }
    decisions = job.evidence_dir / "merge-decisions.json"
    if decisions.is_file():
        current["merge_decisions_sha256"] = artifact_hash(decisions)
    for key, value in current.items():
        if review.get(key) != value:
            raise ValueError(f"verified input changed: {key}")
    for name, expected in review.get("output_hashes", {}).items():
        path = job.output_dir / name
        if not path.is_file() or artifact_hash(path) != expected:
            raise ValueError(f"verified output changed: {name}")
    role_report = None
    if job.policy.get("require_independent_agents", False):
        role_report = verify_role_separation(job)
    final = {
        "spec": "pdf-extractor-pdf/final@1.0",
        "status": "machine_complete_not_human_approved",
        "review_sha256": artifact_hash(review_path),
        **current,
        "output_hashes": review["output_hashes"],
        "role_separation": role_report,
    }
    write_json(job.evidence_dir / "final.json", final)
    update_phase(job.evidence_dir, "complete", "hard_gate_2_passed", {"review_sha256": final["review_sha256"]})
    return final
