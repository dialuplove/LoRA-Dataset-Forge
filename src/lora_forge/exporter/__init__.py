from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lora_forge.config import ProjectConfig
from lora_forge.state import ImageRecord, get_images_by_stage_status, utc_now
from lora_forge.utils import DryRunContext

from .base import ExportAdapter
from .kohya import KohyaExporter
from .onetrainer import OneTrainerExporter


ADAPTERS: dict[str, type[ExportAdapter]] = {
    "onetrainer": OneTrainerExporter,
    "kohya": KohyaExporter,
}


@dataclass
class ExportSummary:
    targets: list[str] = field(default_factory=list)
    exported_items: int = 0
    errors: list[str] = field(default_factory=list)


def get_adapter(target: str) -> ExportAdapter:
    if target not in ADAPTERS:
        raise ValueError(f"Unknown export target: {target}")
    return ADAPTERS[target]()


def export_dataset(
    project_dir: Path,
    conn,
    config: ProjectConfig,
    *,
    target: str = "onetrainer",
    repeats: int | None = None,
    allow_missing_captions: bool = False,
    dry_run: DryRunContext | None = None,
) -> ExportSummary:
    dry_run = dry_run or DryRunContext(False)
    repeats = repeats or config.export.default_repeats
    targets = list(ADAPTERS) if target == "all" else [target]
    images = _exportable_images(conn)
    summary = ExportSummary(targets=targets)
    for target_name in targets:
        adapter = get_adapter(target_name)
        errors = adapter.validate_pre_export(images, project_dir / "working", allow_missing_captions)
        if errors:
            summary.errors.extend(errors)
            continue
        target_dir = adapter.target_dir(project_dir / "exports", config, repeats)
        if dry_run.enabled:
            dry_run.echo(f"Would export {len(images)} images to {target_dir}")
            continue
        run_id = _start_export_run(conn, adapter.name, target_dir.relative_to(project_dir), repeats, allow_missing_captions)
        exported = adapter.export(project_dir / "working", project_dir / "exports", images, config, repeats)
        for image, path in exported:
            conn.execute(
                """
                INSERT INTO export_items (
                    export_run_id, image_id, export_profile, export_path, exported_at, exif_stripped
                ) VALUES (?, ?, ?, ?, ?, TRUE)
                """,
                (run_id, image.id, adapter.name, str(path.relative_to(project_dir)), utc_now()),
            )
            summary.exported_items += 1
        conn.execute(
            "UPDATE export_runs SET status = 'success', completed_at = ?, completeness_status = 'complete' WHERE id = ?",
            (utc_now(), run_id),
        )
    return summary


def _exportable_images(conn) -> list[ImageRecord]:
    return [
        image
        for image in get_images_by_stage_status(conn, "working", "WORKING_CREATED")
        if image.caption_status == "CAPTIONED"
    ]


def _start_export_run(conn, profile: str, target_path: Path, repeats: int, allow_missing: bool) -> int:
    cursor = conn.execute(
        """
        INSERT INTO export_runs (
            export_profile, target_path, repeats, started_at, status,
            completeness_status, allow_missing_captions
        ) VALUES (?, ?, ?, ?, 'running', 'incomplete', ?)
        """,
        (profile, str(target_path), repeats, utc_now(), allow_missing),
    )
    return int(cursor.lastrowid)

