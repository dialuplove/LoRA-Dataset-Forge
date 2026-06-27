from __future__ import annotations

import sqlite3

from PIL import Image

from lora_forge.config import ProjectConfig
from lora_forge.dedupe import detect_duplicates
from lora_forge.importer import import_images
from lora_forge.quality import validate_and_check_quality
from lora_forge.scanner import scan
from lora_forge.state import init_db


def create_image(path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 640), color=color).save(path)


def test_exact_duplicate_detection(tmp_path):
    input_dir = tmp_path / "input"
    create_image(input_dir / "a.jpg", color=(100, 100, 100))
    (input_dir / "b.jpg").write_bytes((input_dir / "a.jpg").read_bytes())
    project_dir = tmp_path / "project"
    (project_dir / "source").mkdir(parents=True)
    (project_dir / "duplicates").mkdir()
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
    try:
        scan(input_dir, conn)
        import_images(project_dir, conn)
        validate_and_check_quality(project_dir, conn, config)
        result = detect_duplicates(project_dir, conn, config)
        rows = conn.execute("SELECT dedupe_status FROM images ORDER BY id").fetchall()
    finally:
        conn.close()
    assert result.exact_duplicates == 1
    assert [row["dedupe_status"] for row in rows] == ["NO_DUPLICATE", "DUPLICATE_CANDIDATE"]

