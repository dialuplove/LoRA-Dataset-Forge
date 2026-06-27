from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


STAGE_STATUS_COLUMNS = {
    "scan": "scan_status",
    "import": "import_status",
    "validation": "validation_status",
    "dedupe": "dedupe_status",
    "quality": "quality_status",
    "acceptance": "acceptance_status",
    "working": "working_status",
    "caption": "caption_status",
}

SUCCESS_STATUSES = {
    "scan": {"DISCOVERED"},
    "import": {"IMPORTED"},
    "validation": {"VALIDATED"},
    "dedupe": {"NO_DUPLICATE", "DUPLICATE_CANDIDATE"},
    "quality": {"PASS", "QUALITY_WARNING"},
    "acceptance": {"ACCEPTED", "REJECTED"},
    "working": {"WORKING_CREATED"},
    "caption": {"CAPTIONED"},
}


@dataclass
class ImageRecord:
    id: int
    original_filename: str
    original_path: str
    file_extension: str
    file_size: int
    scan_status: str = "DISCOVERED"
    import_status: str | None = None
    validation_status: str | None = None
    dedupe_status: str | None = None
    quality_status: str | None = None
    acceptance_status: str | None = None
    working_status: str | None = None
    caption_status: str | None = None
    lifecycle_state: str = "DISCOVERED"
    file_hash: str | None = None
    perceptual_hash: str | None = None
    source_filename: str | None = None
    working_filename: str | None = None
    working_index: int | None = None
    caption_filename: str | None = None
    quality_flags: str | None = None
    duplicate_of_id: int | None = None
    duplicate_type: str | None = None
    hamming_distance: int | None = None
    current_caption_id: int | None = None
    last_error: str | None = None
    retry_count: int = 0
    last_attempted_at: str | None = None
    failed_stage: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ImageRecord":
        data = dict(row)
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: data.get(key) for key in allowed})

    def stage_status(self, stage: str) -> str | None:
        return getattr(self, STAGE_STATUS_COLUMNS[stage])


SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    file_extension TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash TEXT,
    perceptual_hash TEXT,
    width INTEGER,
    height INTEGER,
    scan_status TEXT NOT NULL DEFAULT 'DISCOVERED',
    import_status TEXT,
    validation_status TEXT,
    dedupe_status TEXT,
    quality_status TEXT,
    acceptance_status TEXT,
    working_status TEXT,
    caption_status TEXT,
    lifecycle_state TEXT NOT NULL DEFAULT 'DISCOVERED',
    source_filename TEXT,
    working_filename TEXT,
    working_index INTEGER,
    caption_filename TEXT,
    quality_flags TEXT,
    duplicate_of_id INTEGER,
    duplicate_type TEXT,
    hamming_distance INTEGER,
    working_exif_stripped BOOLEAN DEFAULT FALSE,
    working_exif_strip_timestamp TEXT,
    last_error TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempted_at TEXT,
    failed_stage TEXT,
    acceptance_decision TEXT,
    acceptance_timestamp TEXT,
    discovered_at TEXT NOT NULL,
    imported_at TEXT,
    validated_at TEXT,
    accepted_at TEXT,
    working_created_at TEXT,
    captioned_at TEXT,
    current_caption_id INTEGER,
    UNIQUE(original_path),
    FOREIGN KEY(duplicate_of_id) REFERENCES images(id),
    FOREIGN KEY(current_caption_id) REFERENCES captions(id)
);

CREATE TABLE IF NOT EXISTS captions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    caption_text TEXT NOT NULL,
    caption_source TEXT NOT NULL,
    model_name TEXT,
    prompt_version TEXT,
    generated_at TEXT NOT NULL,
    generation_status TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    token_count INTEGER,
    FOREIGN KEY(image_id) REFERENCES images(id)
);

CREATE TABLE IF NOT EXISTS export_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    export_profile TEXT NOT NULL,
    target_path TEXT NOT NULL,
    repeats INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    completeness_status TEXT NOT NULL,
    allow_missing_captions BOOLEAN DEFAULT FALSE,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS export_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    export_run_id INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    export_profile TEXT NOT NULL,
    export_path TEXT NOT NULL,
    exported_at TEXT NOT NULL,
    exif_stripped BOOLEAN DEFAULT TRUE,
    format_converted BOOLEAN DEFAULT FALSE,
    converted_from TEXT,
    converted_to TEXT,
    FOREIGN KEY(export_run_id) REFERENCES export_runs(id),
    FOREIGN KEY(image_id) REFERENCES images(id)
);

CREATE TABLE IF NOT EXISTS conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    original_format TEXT NOT NULL,
    converted_format TEXT NOT NULL,
    conversion_timestamp TEXT NOT NULL,
    conversion_settings TEXT,
    FOREIGN KEY(image_id) REFERENCES images(id)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_images_scan_status ON images(scan_status);
CREATE INDEX IF NOT EXISTS idx_images_import_status ON images(import_status);
CREATE INDEX IF NOT EXISTS idx_images_validation_status ON images(validation_status);
CREATE INDEX IF NOT EXISTS idx_images_dedupe_status ON images(dedupe_status);
CREATE INDEX IF NOT EXISTS idx_images_quality_status ON images(quality_status);
CREATE INDEX IF NOT EXISTS idx_images_acceptance_status ON images(acceptance_status);
CREATE INDEX IF NOT EXISTS idx_images_working_status ON images(working_status);
CREATE INDEX IF NOT EXISTS idx_images_caption_status ON images(caption_status);
CREATE INDEX IF NOT EXISTS idx_images_file_hash ON images(file_hash);
CREATE INDEX IF NOT EXISTS idx_images_perceptual_hash ON images(perceptual_hash);
CREATE INDEX IF NOT EXISTS idx_captions_image_id ON captions(image_id);
CREATE INDEX IF NOT EXISTS idx_export_runs_profile ON export_runs(export_profile);
CREATE INDEX IF NOT EXISTS idx_export_runs_status ON export_runs(status);
CREATE INDEX IF NOT EXISTS idx_export_items_run_id ON export_items(export_run_id);
CREATE INDEX IF NOT EXISTS idx_export_items_image_id ON export_items(image_id);
CREATE INDEX IF NOT EXISTS idx_export_items_profile ON export_items(export_profile);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        if existing == 0:
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (1, utc_now()),
            )


def get_images_by_stage_status(
    conn: sqlite3.Connection, stage: str, statuses: str | list[str] | tuple[str, ...]
) -> list[ImageRecord]:
    column = STAGE_STATUS_COLUMNS[stage]
    values = [statuses] if isinstance(statuses, str) else list(statuses)
    placeholders = ", ".join("?" for _ in values)
    rows = conn.execute(
        f"SELECT * FROM images WHERE {column} IN ({placeholders}) ORDER BY id",
        values,
    ).fetchall()
    return [ImageRecord.from_row(row) for row in rows]


def get_image_by_original_path(conn: sqlite3.Connection, original_path: str) -> ImageRecord | None:
    row = conn.execute(
        "SELECT * FROM images WHERE original_path = ?",
        (original_path,),
    ).fetchone()
    return ImageRecord.from_row(row) if row else None


def insert_discovered_image(
    conn: sqlite3.Connection,
    *,
    original_filename: str,
    original_path: str,
    file_extension: str,
    file_size: int,
    file_hash: str | None,
    perceptual_hash: str | None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO images (
            original_filename,
            original_path,
            file_extension,
            file_size,
            file_hash,
            perceptual_hash,
            scan_status,
            lifecycle_state,
            discovered_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'DISCOVERED', 'DISCOVERED', ?)
        """,
        (
            original_filename,
            original_path,
            file_extension,
            file_size,
            file_hash,
            perceptual_hash,
            utc_now(),
        ),
    )
    return int(cursor.lastrowid)


def update_stage_status(
    conn: sqlite3.Connection,
    image_id: int,
    stage: str,
    status: str,
    **fields: Any,
) -> None:
    column = STAGE_STATUS_COLUMNS[stage]
    assignments = [f"{column} = ?", "last_error = NULL", "failed_stage = NULL"]
    values: list[Any] = [status]
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        values.append(value)
    values.append(image_id)
    conn.execute(
        f"UPDATE images SET {', '.join(assignments)} WHERE id = ?",
        values,
    )


def record_error(conn: sqlite3.Connection, image_id: int, stage: str, error: str) -> None:
    column = STAGE_STATUS_COLUMNS[stage]
    conn.execute(
        f"""
        UPDATE images SET
            {column} = 'FAILED',
            failed_stage = ?,
            last_error = ?,
            retry_count = retry_count + 1,
            last_attempted_at = ?
        WHERE id = ?
        """,
        (stage, error, utc_now(), image_id),
    )


def should_process(image: ImageRecord, stage: str, force: bool = False) -> bool:
    if force:
        return True
    status = image.stage_status(stage)
    if status in SUCCESS_STATUSES[stage]:
        return False
    if status == "FAILED" and image.failed_stage == stage:
        return True
    return prerequisites_met(image, stage)


def prerequisites_met(image: ImageRecord, stage: str) -> bool:
    if stage == "scan":
        return True
    if stage == "import":
        return image.scan_status == "DISCOVERED"
    if stage == "validation":
        return image.import_status == "IMPORTED"
    if stage == "quality":
        return image.validation_status == "VALIDATED"
    if stage == "dedupe":
        return image.validation_status == "VALIDATED"
    if stage == "acceptance":
        return image.validation_status == "VALIDATED"
    if stage == "working":
        return image.acceptance_status == "ACCEPTED"
    if stage == "caption":
        return image.acceptance_status == "ACCEPTED" and image.working_status == "WORKING_CREATED"
    return False
