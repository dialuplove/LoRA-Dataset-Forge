from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .state import utc_now
from .utils import DryRunContext


@dataclass
class ReportResult:
    markdown_path: Path
    json_path: Path


def generate_report(project_dir: Path, conn, dry_run: DryRunContext | None = None) -> ReportResult:
    dry_run = dry_run or DryRunContext(False)
    data = collect_report_data(conn)
    data["generated_at"] = utc_now()
    report_dir = project_dir / "reports"
    markdown_path = report_dir / "report.md"
    json_path = report_dir / "report.json"
    if dry_run.enabled:
        dry_run.echo(f"Would write {markdown_path}")
        dry_run.echo(f"Would write {json_path}")
        return ReportResult(markdown_path, json_path)
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(data), encoding="utf-8")
    json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return ReportResult(markdown_path, json_path)


def collect_report_data(conn) -> dict:
    one = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "files_scanned": one("SELECT COUNT(*) FROM images WHERE scan_status = 'DISCOVERED'"),
        "images_imported": one("SELECT COUNT(*) FROM images WHERE import_status = 'IMPORTED'"),
        "working_created": one("SELECT COUNT(*) FROM images WHERE working_status = 'WORKING_CREATED'"),
        "accepted": one("SELECT COUNT(*) FROM images WHERE acceptance_status = 'ACCEPTED'"),
        "rejected": one("SELECT COUNT(*) FROM images WHERE acceptance_status = 'REJECTED'"),
        "captions_generated": one("SELECT COUNT(*) FROM captions WHERE caption_source = 'openai'"),
        "captions_reused": one("SELECT COUNT(*) FROM captions WHERE caption_source = 'existing_file'"),
        "export_runs": one("SELECT COUNT(*) FROM export_runs WHERE status = 'success'"),
    }


def render_markdown(data: dict) -> str:
    lines = ["# LoRA Dataset Forge Report", ""]
    for key, value in data.items():
        lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
    return "\n".join(lines) + "\n"

