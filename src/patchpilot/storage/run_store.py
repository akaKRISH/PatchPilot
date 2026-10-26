"""RunStore managing structured reports, unified diffs, and append-only event logs."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchpilot.schemas import RunReport


class RunStore:
    """Persists run reports and JSONL operational logs beneath PatchPilot data directory."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.resolve()
        self.runs_dir = self.data_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.events_log = self.data_dir / "events.jsonl"

    def record_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Append an event to the local append-only events.jsonl file."""
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "type": event_type,
            "payload": payload,
        }
        with open(self.events_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def save_run(self, report: RunReport) -> Path:
        """Save structured JSON run report and standalone patch file."""
        report_file = self.runs_dir / f"{report.run_id}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        # Save patch file separately for convenient review
        if report.patch and report.patch.unified_diff:
            patch_file = self.runs_dir / f"{report.run_id}.patch"
            patch_file.write_text(report.patch.unified_diff, encoding="utf-8")

        self.record_event(
            run_id=report.run_id,
            event_type="RUN_COMPLETED",
            payload={
                "status": report.status.value,
                "duration_seconds": report.duration_seconds,
                "attempts": report.attempts_made,
            },
        )
        return report_file

    def get_run(self, run_id: str) -> RunReport | None:
        """Load a saved run report by its ID."""
        report_file = self.runs_dir / f"{run_id}.json"
        if not report_file.is_file():
            return None
        try:
            with open(report_file, encoding="utf-8") as f:
                data = json.load(f)
            return RunReport.model_validate(data)
        except Exception:
            return None

    def list_runs(self) -> list[dict[str, Any]]:
        """List summary metadata for all saved runs, sorted most recent first."""
        summaries: list[dict[str, Any]] = []
        for file in self.runs_dir.glob("*.json"):
            try:
                with open(file, encoding="utf-8") as f:
                    data = json.load(f)
                summaries.append(
                    {
                        "run_id": data.get("run_id", file.stem),
                        "status": data.get("status", "UNKNOWN"),
                        "start_time": data.get("start_time", ""),
                        "duration_seconds": data.get("duration_seconds", 0.0),
                        "attempts": data.get("attempts_made", 0),
                        "task": data.get("task", {}).get("task_description", "")[:60],
                    }
                )
            except Exception:
                continue

        summaries.sort(key=lambda s: s.get("start_time", ""), reverse=True)
        return summaries
