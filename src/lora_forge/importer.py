from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .state import ImageRecord, get_images_by_stage_status, record_error, update_stage_status, utc_now
from .utils import DryRunContext


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    failed: int = 0


def source_path_for(project_dir: Path, image: ImageRecord) -> Path:
    return project_dir / "source" / image.original_filename


def import_images(project_dir: Path, conn, dry_run: DryRunContext | None = None) -> ImportResult:
    dry_run = dry_run or DryRunContext(False)
    result = ImportResult()
    candidates = get_images_by_stage_status(conn, "scan", "DISCOVERED")
    for image in candidates:
        if image.import_status == "IMPORTED":
            result.skipped += 1
            continue
        source = Path(image.original_path)
        target = source_path_for(project_dir, image)
        if dry_run.enabled:
            dry_run.echo(f"Would copy {source} to {target}")
            result.imported += 1
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            update_stage_status(
                conn,
                image.id,
                "import",
                "IMPORTED",
                source_filename=target.name,
                imported_at=utc_now(),
                lifecycle_state="IMPORTED",
            )
            result.imported += 1
        except Exception as exc:
            record_error(conn, image.id, "import", str(exc))
            result.failed += 1
    return result

