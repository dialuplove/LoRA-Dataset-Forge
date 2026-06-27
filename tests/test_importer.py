from __future__ import annotations

import sqlite3

from PIL import Image

from lora_forge.importer import import_images
from lora_forge.scanner import scan
from lora_forge.state import init_db


def create_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color=(0, 0, 255)).save(path)


def test_import_preserves_source_bytes(tmp_path):
    input_dir = tmp_path / "input"
    image_path = input_dir / "a.jpg"
    create_image(image_path)
    original_bytes = image_path.read_bytes()

    project_dir = tmp_path / "project"
    (project_dir / "source").mkdir(parents=True)
    db_path = project_dir / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        scan(input_dir, conn)
        result = import_images(project_dir, conn)
        row = conn.execute("SELECT import_status, source_filename FROM images").fetchone()
    finally:
        conn.close()

    assert result.imported == 1
    assert row["import_status"] == "IMPORTED"
    assert row["source_filename"] == "a.jpg"
    assert (project_dir / "source" / "a.jpg").read_bytes() == original_bytes

