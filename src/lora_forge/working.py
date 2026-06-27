from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig
from .exif import strip_exif
from .renamer import caption_filename_for, next_working_index, working_filename
from .state import get_images_by_stage_status, record_error, update_stage_status, utc_now
from .utils import DryRunContext


@dataclass
class WorkingResult:
    created: int = 0
    skipped: int = 0
    failed: int = 0


def build_working(
    project_dir: Path,
    conn,
    config: ProjectConfig,
    dry_run: DryRunContext | None = None,
) -> WorkingResult:
    dry_run = dry_run or DryRunContext(False)
    result = WorkingResult()
    images = get_images_by_stage_status(conn, "acceptance", "ACCEPTED")
    index = next_working_index(conn)
    for image in images:
        if image.working_status == "WORKING_CREATED":
            result.skipped += 1
            continue
        source_name = image.source_filename or image.original_filename
        source_path = project_dir / "source" / source_name
        filename = working_filename(config, index, image.file_extension)
        output_path = project_dir / "working" / filename
        caption_name = caption_filename_for(filename)
        if dry_run.enabled:
            dry_run.echo(f"Would create working image {output_path} from {source_path}")
            result.created += 1
            index += 1
            continue
        try:
            exif_result = strip_exif(source_path, output_path)
            if not exif_result.success:
                raise RuntimeError(exif_result.error or "EXIF stripping failed")
            update_stage_status(
                conn,
                image.id,
                "working",
                "WORKING_CREATED",
                working_filename=filename,
                working_index=index,
                caption_filename=caption_name,
                working_exif_stripped=True,
                working_exif_strip_timestamp=utc_now(),
                working_created_at=utc_now(),
                lifecycle_state="WORKING_CREATED",
            )
            result.created += 1
            index += 1
        except Exception as exc:
            record_error(conn, image.id, "working", str(exc))
            result.failed += 1
    return result

