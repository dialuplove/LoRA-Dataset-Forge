from __future__ import annotations

import sqlite3

from PIL import Image

from lora_forge.scanner import discover_image_paths, scan
from lora_forge.state import init_db
from lora_forge.utils import DryRunContext


def create_image(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color=(0, 255, 0)).save(path)


def test_discover_image_paths_filters_extensions_and_ignores_dirs(tmp_path):
    create_image(tmp_path / "a.jpg")
    create_image(tmp_path / "b.JPEG")
    create_image(tmp_path / ".obsidian" / "hidden.jpg")
    create_image(tmp_path / ".kiro" / "hidden.webp")
    create_image(tmp_path / "working" / "hidden.png")
    (tmp_path / "notes.md").write_text("hello")

    images, skipped = discover_image_paths(tmp_path)

    assert {path.name for path in images} == {"a.jpg", "b.JPEG"}
    assert {path.name for path in skipped} >= {".obsidian", ".kiro", "working"}


def test_scan_creates_discovered_records_and_skips_existing(tmp_path):
    create_image(tmp_path / "a.jpg")
    db_path = tmp_path / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        result = scan(tmp_path, conn)
        conn.commit()
        second = scan(tmp_path, conn)
        rows = conn.execute("SELECT original_filename, scan_status FROM images").fetchall()
    finally:
        conn.close()

    assert result.discovered == 1
    assert second.skipped_existing == 1
    assert [(row["original_filename"], row["scan_status"]) for row in rows] == [("a.jpg", "DISCOVERED")]


def test_scan_dry_run_writes_no_db_rows(tmp_path):
    create_image(tmp_path / "a.jpg")
    db_path = tmp_path / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        result = scan(tmp_path, conn, DryRunContext(True))
        rows = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    finally:
        conn.close()
    assert result.discovered == 1
    assert rows == 0

