from __future__ import annotations

import sqlite3

from PIL import Image

from lora_forge.captioning import caption_images
from lora_forge.captioning.openai_captioner import CaptionResult
from lora_forge.config import ProjectConfig
from lora_forge.doctor import doctor_project
from lora_forge.importer import import_images
from lora_forge.project import init_project
from lora_forge.quality import validate_and_check_quality
from lora_forge.scanner import scan
from lora_forge.state import db_connection, update_stage_status
from lora_forge.status import project_status
from lora_forge.utils import DryRunContext
from lora_forge.working import build_working


class FakeCaptioner:
    def generate_caption(self, image_path, prompt):
        return CaptionResult(True, text="dawivre woman, neutral expression, indoor lighting")


def create_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 640), color=(90, 90, 90)).save(path)


def test_status_and_doctor_on_project(tmp_path):
    input_dir = tmp_path / "input"
    create_image(input_dir / "a.jpg")
    init_result = init_project(input_dir, "demo", "dawivre", "woman", base_dir=tmp_path)
    project_dir = init_result.project_dir
    config = ProjectConfig.read(project_dir / "project.json")
    config.quality.blur_threshold = -1.0
    with db_connection(project_dir / "forge.db") as conn:
        scan(input_dir, conn)
        import_images(project_dir, conn)
        validate_and_check_quality(project_dir, conn, config)
        image_id = conn.execute("SELECT id FROM images").fetchone()["id"]
        update_stage_status(conn, image_id, "dedupe", "NO_DUPLICATE")
        update_stage_status(conn, image_id, "acceptance", "ACCEPTED", acceptance_decision="ACCEPTED")
        build_working(project_dir, conn, config)
        caption_images(project_dir, conn, config, captioner=FakeCaptioner())
        status = project_status(project_dir, conn)
        doctor = doctor_project(project_dir, conn)
    assert status["working"] == 1
    assert status["captioned"] == 1
    assert doctor.ok


def test_init_dry_run_has_no_side_effects(tmp_path):
    input_dir = tmp_path / "input"
    create_image(input_dir / "a.jpg")
    result = init_project(
        input_dir,
        "demo",
        "dawivre",
        "woman",
        base_dir=tmp_path,
        dry_run=DryRunContext(True),
    )
    assert result.dry_run
    assert not (tmp_path / "demo").exists()

