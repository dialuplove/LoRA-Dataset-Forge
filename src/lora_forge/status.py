from __future__ import annotations

from pathlib import Path

from .config import load_project_config


def project_status(project_dir: Path, conn) -> dict[str, object]:
    config = load_project_config(project_dir)
    one = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "project_name": config.project_name,
        "source_folder": config.source_folder,
        "scanned": one("SELECT COUNT(*) FROM images WHERE scan_status = 'DISCOVERED'"),
        "imported": one("SELECT COUNT(*) FROM images WHERE import_status = 'IMPORTED'"),
        "accepted": one("SELECT COUNT(*) FROM images WHERE acceptance_status = 'ACCEPTED'"),
        "rejected": one("SELECT COUNT(*) FROM images WHERE acceptance_status = 'REJECTED'"),
        "working": one("SELECT COUNT(*) FROM images WHERE working_status = 'WORKING_CREATED'"),
        "duplicate_candidates": one("SELECT COUNT(*) FROM images WHERE dedupe_status = 'DUPLICATE_CANDIDATE'"),
        "quality_warnings": one("SELECT COUNT(*) FROM images WHERE quality_status = 'QUALITY_WARNING'"),
        "captioned": one("SELECT COUNT(*) FROM images WHERE caption_status = 'CAPTIONED'"),
        "missing_captions": one(
            "SELECT COUNT(*) FROM images WHERE working_status = 'WORKING_CREATED' AND caption_status IS NOT 'CAPTIONED'"
        ),
        "successful_exports": one("SELECT COUNT(*) FROM export_runs WHERE status = 'success'"),
    }

