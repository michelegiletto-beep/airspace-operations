"""Record concrete copy observations without modifying application files."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROWS = [
    ("ASO3-COPY-001", "frontend/src/AgentWorkspace.tsx", "One operational context. Bounded specialist work.", "Get help with a task.", "Application heading"),
    ("ASO3-COPY-002", "frontend/src/AgentWorkspace.tsx", "Choose the work. Keep the evidence.", "Choose a task to begin.", "Application empty state"),
    ("ASO3-COPY-003", "frontend/src/AgentWorkspace.tsx", "Bounded objective", "What do you want to achieve?", "Task form"),
    ("ASO3-COPY-004", "frontend/src/AgentWorkspace.tsx", "Prepare scoped workflow", "Create task", "Task action"),
    ("ASO3-COPY-005", "frontend/src/AgentWorkspace.tsx", "Start bounded workflow", "Start task", "Task action"),
    ("ASO3-COPY-006", "frontend/src/MissionDesk.tsx", "01 · Operation", "Mission details", "Decorative form numbering"),
    ("ASO3-COPY-007", "frontend/src/MissionDesk.tsx", "02 · Intended resources", "People and aircraft", "Decorative form numbering"),
    ("ASO3-COPY-008", "frontend/src/MissionDesk.tsx", "Each permission keeps its own boundary", "Permissions and reviews", "Heading phrased as a slogan"),
    ("ASO3-COPY-009", "frontend/src/CoordinationDesk.tsx", "One intended mission, distinct national conditions", "Check each operating country", "Heading phrased as a slogan"),
    ("ASO3-COPY-010", "frontend/src/CoordinationDesk.tsx", "Select actual registration", "Choose registration country", "Repeated factuality adjective"),
    ("ASO3-COPY-011", "frontend/src/CoordinationDesk.tsx", "Select actual recipient", "Choose recipient country", "Repeated factuality adjective"),
    ("ASO3-COPY-012", "frontend/src/CoordinationDesk.tsx", "Actual agreement reference", "Agreement reference", "Repeated factuality adjective"),
    ("ASO3-COPY-013", "frontend/src/CoordinationDesk.tsx", "Allowlisted terms and asset snapshot", "Shared terms and aircraft details", "Implementation language in a user control"),
    ("ASO3-COPY-014", "frontend/src/CoordinationDesk.tsx", "Saved country-pack review", "Country review", "Explain current reviewed country requirements in help text"),
    ("ASO3-COPY-015", "frontend/src/SchedulingDesk.tsx", "Cancel internal proposal / reservation", "Cancel proposal or reservation", "Decorative slash in an action"),
    ("ASO3-COPY-016", "frontend/src/SchedulingDesk.tsx", "Accountable rationale", "Reason for this decision", "Unnecessary formal wording"),
    ("ASO3-COPY-017", "frontend/src/SchedulingDesk.tsx", "Actual independent reviewer accounts", "Choose reviewers", "Repeated factuality adjective"),
    ("ASO3-COPY-018", "frontend/src/SchedulingDesk.tsx", "Actual decision receipt", "Saved decision", "Repeated factuality adjective"),
    ("ASO3-COPY-019", "frontend/src/SchedulingDesk.tsx", "Exact solver input, result and verifier receipt", "Scheduling inputs and check results", "Technical details remain available in the expandable record"),
    ("ASO3-COPY-020", "publication/site-project.html", "Review remains accountable.", "Before operational use", "Published 0.2 heading"),
    ("ASO3-COPY-021", "publication/site-project.html", "01 / The application", "The application", "Published decorative section label"),
    ("ASO3-COPY-022", "publication/site-project.html", "Local LLM orchestration.", "Local model assistance", "Public heading should explain user work"),
    ("ASO3-COPY-023", "publication/github-readme-v2.md", "A generative controller with bounded specialist tools", "Local model assistance", "Technical architecture remains in model administration documentation"),
    ("ASO3-COPY-024", "publication/hf-space/index.html", "Inspect each completed step.", "Workflow results", "Published evidence-viewer heading"),
    ("ASO3-COPY-025", "publication/hf-space/index.html", "Source-linked passages.", "Source passages", "Plain evidence-viewer heading"),
    ("ASO3-COPY-026", "publication/hf-space/index.html", "A limited routing experiment.", "Student evaluation", "Keep experimental status and measured limitations in the explanatory text"),
    ("ASO3-COPY-027", "publication/hf-space/index.html", "Original records and boundaries.", "Records and limitations", "Plain evidence-viewer heading"),
]


def main():
    records = []
    for identifier, source, observed, proposed, reason in ROWS:
        path = ROOT / source
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        position = content.find(observed)
        historical = source.startswith("publication/")
        records.append({"id": identifier, "requirement": "ASO3-001", "source": source,
            "initial_observation": "Observed in initial 0.2 application/publication source inspection",
            "observed_text": observed, "proposed_text": proposed, "reason": reason,
            "current_literal_present": position >= 0,
            "current_line": content.count("\n", 0, position) + 1 if position >= 0 else None,
            "current_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            "state": "Historical 0.2 source retained; replacement prepared in v0.3" if historical else "Requires rendered review" if position < 0 else "Requires ablation or deliberate justification",
            "treatment": "Use the new v0.3 sources; preserve published 0.2 bytes and historical evidence" if historical else "Review the current application text and rendered state",
            "owner": "Frontend" if source.startswith("frontend/") else "Publication",
            "verification_limit": "Literal absence is not evidence that every rendered slogan or inaccessible state has been reviewed"})
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "revision": "0.3.0-rc.1",
        "baseline": "SPECIFICATION_V3_ADDENDUM.md", "records": records,
        "preserve": ["Original source quotations and legal meaning", "Code/API identifiers, URLs and anchors", "Dates, version numbers, units, measured values and real record counts", "Standard Markdown and machine-readable formats", "Necessary permission, review and missing-evidence explanations"],
        "motion_review": ["Companion frame progression during ordinary idle and active use", "Real animated fallback after renderer failure", "Pause and reduced-motion precedence", "Reactive background remains behind readable controls", "No animation is represented as a completed model response or readiness approval"],
        "next_verification": "Review the integrated application in the browser and inspect private task/action journeys; replace preparation claims only with actual evidence"}
    (Path(__file__).parent / "ablation-inventory.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"observations": len(records), "still_present_in_current_source": sum(row["current_literal_present"] for row in records), "publication_performed": False}))


if __name__ == "__main__":
    main()
