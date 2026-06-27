from __future__ import annotations

import sqlite3

from PIL import Image

from lora_forge.acceptance import decide_acceptance
from lora_forge.config import ProjectConfig
from lora_forge.importer import import_images
from lora_forge.quality import validate_and_check_quality
from lora_forge.scanner import scan
from lora_forge.state import init_db


def create_image(path, size=(640, 640), color=(128, 128, 128)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=color).save(path)


def config(tmp_path):
    return ProjectConfig(
        project_name="demo",
        trigger_token="dawivre",
        class_token="woman",
        source_folder=str(tmp_path / "input"),
    )


def setup_imported_project(tmp_path, image_size=(640, 640)):
    input_dir = tmp_path / "input"
    create_image(input_dir / "a.jpg", size=image_size)
    project_dir = tmp_path / "project"
    (project_dir / "source").mkdir(parents=True)
    (project_dir / "rejected").mkdir()
    db_path = project_dir / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    scan(input_dir, conn)
    import_images(project_dir, conn)
    return project_dir, conn


def test_quality_validates_and_flags_low_resolution(tmp_path):
    project_dir, conn = setup_imported_project(tmp_path, image_size=(64, 64))
    try:
        result = validate_and_check_quality(project_dir, conn, config(tmp_path))
        row = conn.execute("SELECT validation_status, quality_status, quality_flags FROM images").fetchone()
    finally:
        conn.close()
    assert result.validated == 1
    assert row["validation_status"] == "VALIDATED"
    assert row["quality_status"] == "QUALITY_WARNING"
    assert "WARN_LOW_RESOLUTION" in row["quality_flags"]


def test_acceptance_accepts_clean_and_rejects_warning(tmp_path):
    project_dir, conn = setup_imported_project(tmp_path, image_size=(64, 64))
    try:
        validate_and_check_quality(project_dir, conn, config(tmp_path))
        result = decide_acceptance(project_dir, conn)
        row = conn.execute("SELECT acceptance_status FROM images").fetchone()
    finally:
        conn.close()
    assert result.rejected == 1
    assert row["acceptance_status"] == "REJECTED"

