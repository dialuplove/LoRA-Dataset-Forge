from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from PIL import Image

from lora_forge.captioning import caption_images, enforce_prefix
from lora_forge.captioning.openai_captioner import CaptionResult
from lora_forge.config import ProjectConfig
from lora_forge.importer import import_images
from lora_forge.linting import has_error_warnings, lint_and_fix, lint_caption
from lora_forge.quality import validate_and_check_quality
from lora_forge.scanner import scan
from lora_forge.state import init_db, update_stage_status
from lora_forge.working import build_working


@dataclass
class FakeCaptioner:
    calls: int = 0

    def generate_caption(self, image_path, prompt):
        self.calls += 1
        return CaptionResult(True, text="smiling, indoor lighting", model_name="fake")


def create_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 640), color=(20, 40, 60)).save(path)


def make_config(input_dir):
    config = ProjectConfig(
        project_name="demo",
        trigger_token="dawivre",
        class_token="woman",
        source_folder=str(input_dir),
    )
    config.quality.blur_threshold = -1.0
    return config


def setup_caption_project(tmp_path):
    input_dir = tmp_path / "input"
    create_image(input_dir / "a.jpg")
    project_dir = tmp_path / "project"
    for dirname in ["source", "working"]:
        (project_dir / dirname).mkdir(parents=True, exist_ok=True)
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
    build_working(project_dir, conn, config)
    return project_dir, conn, config


def test_enforce_prefix_adds_exactly_one_prefix():
    config = make_config("/tmp/input")
    assert enforce_prefix("smiling", config) == "dawivre woman, smiling"
    assert enforce_prefix("dawivre woman, smiling", config) == "dawivre woman, smiling"


def test_existing_valid_caption_reused_without_openai(tmp_path):
    project_dir, conn, config = setup_caption_project(tmp_path)
    (project_dir / "working" / "dawivre_0001.txt").write_text(
        "dawivre woman, smiling, indoor lighting\n",
        encoding="utf-8",
    )
    fake = FakeCaptioner()
    try:
        result = caption_images(project_dir, conn, config, captioner=fake)
        row = conn.execute(
            "SELECT caption_status, current_caption_id FROM images"
        ).fetchone()
    finally:
        conn.close()
    assert result.reused == 1
    assert fake.calls == 0
    assert row["caption_status"] == "CAPTIONED"
    assert row["current_caption_id"] is not None


def test_missing_caption_calls_captioner_and_writes_prefix(tmp_path):
    project_dir, conn, config = setup_caption_project(tmp_path)
    fake = FakeCaptioner()
    try:
        result = caption_images(project_dir, conn, config, captioner=fake)
    finally:
        conn.close()
    assert result.generated == 1
    assert fake.calls == 1
    assert (project_dir / "working" / "dawivre_0001.txt").read_text().startswith("dawivre woman,")


def test_lint_and_fix_repairs_missing_prefix():
    fixed, warnings = lint_and_fix(" smiling  indoors ", "dawivre", "woman")
    assert fixed == "dawivre woman, smiling indoors"
    assert not has_error_warnings(warnings)
    assert not lint_caption(
        fixed,
        "dawivre",
        "woman",
        ProjectConfig(project_name="x", trigger_token="dawivre", class_token="woman", source_folder="/tmp").caption_lint,
    )
