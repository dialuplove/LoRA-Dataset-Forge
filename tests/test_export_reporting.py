from __future__ import annotations

import sqlite3

from PIL import Image

from lora_forge.captioning import caption_images
from lora_forge.captioning.openai_captioner import CaptionResult
from lora_forge.config import ProjectConfig
from lora_forge.exporter import export_dataset
from lora_forge.importer import import_images
from lora_forge.quality import validate_and_check_quality
from lora_forge.reporting import generate_report
from lora_forge.scanner import scan
from lora_forge.state import init_db, update_stage_status
from lora_forge.working import build_working


class FakeCaptioner:
    def generate_caption(self, image_path, prompt):
        return CaptionResult(True, text="dawivre woman, smiling, studio lighting", model_name="fake")


def create_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 640), color=(80, 80, 80)).save(path)


def setup_captioned_project(tmp_path):
    input_dir = tmp_path / "input"
    create_image(input_dir / "a.jpg")
    project_dir = tmp_path / "project"
    for dirname in ["source", "working", "exports", "reports"]:
        (project_dir / dirname).mkdir(parents=True, exist_ok=True)
    db_path = project_dir / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    config = ProjectConfig(
        project_name="demo",
        trigger_token="dawivre",
        class_token="woman",
        source_folder=str(input_dir),
    )
    config.quality.blur_threshold = -1.0
    scan(input_dir, conn)
    import_images(project_dir, conn)
    validate_and_check_quality(project_dir, conn, config)
    image_id = conn.execute("SELECT id FROM images").fetchone()["id"]
    update_stage_status(conn, image_id, "dedupe", "NO_DUPLICATE")
    update_stage_status(conn, image_id, "acceptance", "ACCEPTED", acceptance_decision="ACCEPTED")
    build_working(project_dir, conn, config)
    caption_images(project_dir, conn, config, captioner=FakeCaptioner())
    return project_dir, conn, config


def test_onetrainer_export_records_run_and_items(tmp_path):
    project_dir, conn, config = setup_captioned_project(tmp_path)
    try:
        result = export_dataset(project_dir, conn, config, target="onetrainer")
        run_count = conn.execute("SELECT COUNT(*) FROM export_runs").fetchone()[0]
        item_count = conn.execute("SELECT COUNT(*) FROM export_items").fetchone()[0]
    finally:
        conn.close()
    assert result.exported_items == 1
    assert run_count == 1
    assert item_count == 1
    assert (project_dir / "exports" / "onetrainer" / "dawivre_0001.jpg").exists()
    assert (project_dir / "exports" / "onetrainer" / "dawivre_0001.txt").exists()


def test_kohya_export_structure(tmp_path):
    project_dir, conn, config = setup_captioned_project(tmp_path)
    try:
        export_dataset(project_dir, conn, config, target="kohya", repeats=20)
    finally:
        conn.close()
    assert (project_dir / "exports" / "kohya" / "20_dawivre woman" / "dawivre_0001.jpg").exists()
    assert (project_dir / "exports" / "kohya" / "20_dawivre woman" / "dawivre_0001.txt").exists()


def test_report_generation(tmp_path):
    project_dir, conn, config = setup_captioned_project(tmp_path)
    try:
        export_dataset(project_dir, conn, config)
        result = generate_report(project_dir, conn)
    finally:
        conn.close()
    assert result.markdown_path.exists()
    assert result.json_path.exists()
    assert "LoRA Dataset Forge Report" in result.markdown_path.read_text()

