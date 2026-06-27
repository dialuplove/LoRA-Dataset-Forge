from __future__ import annotations

import sqlite3

from PIL import Image

from lora_forge.config import ProjectConfig
from lora_forge.importer import import_images
from lora_forge.quality import validate_and_check_quality
from lora_forge.scanner import scan
from lora_forge.state import init_db, update_stage_status
from lora_forge.working import build_working


def create_image(path, color=(10, 20, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 640), color=color).save(path)


def make_config(input_dir):
    config = ProjectConfig(
        project_name="demo",
        trigger_token="dawivre",
        class_token="woman",
        source_folder=str(input_dir),
    )
    config.quality.blur_threshold = -1.0
    return config


def setup_project(tmp_path):
    input_dir = tmp_path / "input"
    create_image(input_dir / "a.jpg")
    project_dir = tmp_path / "project"
    (project_dir / "source").mkdir(parents=True)
    (project_dir / "working").mkdir()
    db_path = project_dir / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    config = make_config(input_dir)
    scan(input_dir, conn)
    import_images(project_dir, conn)
    validate_and_check_quality(project_dir, conn, config)
    image_id = conn.execute("SELECT id FROM images").fetchone()["id"]
    update_stage_status(conn, image_id, "dedupe", "NO_DUPLICATE")
    update_stage_status(conn, image_id, "acceptance", "ACCEPTED", acceptance_decision="ACCEPTED")
    return project_dir, conn, config


def test_build_working_creates_stable_mapping_and_preserves_source(tmp_path):
    project_dir, conn, config = setup_project(tmp_path)
    source_bytes_before = (project_dir / "source" / "a.jpg").read_bytes()
    try:
        result = build_working(project_dir, conn, config)
        row = conn.execute(
            "SELECT working_status, working_filename, caption_filename, working_index FROM images"
        ).fetchone()
        second = build_working(project_dir, conn, config)
    finally:
        conn.close()

    assert result.created == 1
    assert second.skipped == 1
    assert row["working_status"] == "WORKING_CREATED"
    assert row["working_filename"] == "dawivre_0001.jpg"
    assert row["caption_filename"] == "dawivre_0001.txt"
    assert row["working_index"] == 1
    assert (project_dir / "working" / "dawivre_0001.jpg").exists()
    assert (project_dir / "source" / "a.jpg").read_bytes() == source_bytes_before

