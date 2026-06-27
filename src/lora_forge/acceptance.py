from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .state import get_images_by_stage_status, update_stage_status, utc_now
from .utils import DryRunContext


@dataclass
class AcceptanceResult:
    accepted: int = 0
    rejected: int = 0
    skipped: int = 0


def decide_acceptance(project_dir: Path, conn, dry_run: DryRunContext | None = None) -> AcceptanceResult:
    dry_run = dry_run or DryRunContext(False)
    result = AcceptanceResult()
    images = get_images_by_stage_status(conn, "validation", "VALIDATED")
    for image in images:
        if image.acceptance_status in {"ACCEPTED", "REJECTED"}:
            result.skipped += 1
            continue
        reject = image.dedupe_status == "DUPLICATE_CANDIDATE" or image.quality_status == "QUALITY_WARNING"
        status = "REJECTED" if reject else "ACCEPTED"
        if dry_run.enabled:
            dry_run.echo(f"Would mark {image.original_filename} as {status}")
        else:
            update_stage_status(
                conn,
                image.id,
                "acceptance",
                status,
                acceptance_decision=status,
                acceptance_timestamp=utc_now(),
                accepted_at=utc_now() if status == "ACCEPTED" else None,
                lifecycle_state=status,
            )
            if status == "REJECTED":
                _copy_rejected(project_dir, image.source_filename)
        if status == "ACCEPTED":
            result.accepted += 1
        else:
            result.rejected += 1
    return result


def _copy_rejected(project_dir: Path, source_filename: str | None) -> None:
    if not source_filename:
        return
    source = project_dir / "source" / source_filename
    target = project_dir / "rejected" / source_filename
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

