from __future__ import annotations

import sqlite3

from lora_forge.state import init_db, record_error, update_stage_status


def test_init_db_creates_required_tables(tmp_path):
    db_path = tmp_path / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert {"images", "captions", "export_runs", "export_items", "conversions", "schema_version"} <= tables


def test_update_stage_status_and_record_error(tmp_path):
    db_path = tmp_path / "forge.db"
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO images (
                original_filename, original_path, file_extension, file_size, discovered_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("a.jpg", "/tmp/a.jpg", ".jpg", 10, "now"),
        )
        image_id = conn.execute("SELECT id FROM images").fetchone()[0]
        update_stage_status(conn, image_id, "import", "IMPORTED")
        assert conn.execute("SELECT import_status FROM images").fetchone()[0] == "IMPORTED"
        record_error(conn, image_id, "working", "copy failed")
        row = conn.execute(
            "SELECT working_status, failed_stage, last_error, retry_count FROM images"
        ).fetchone()
    finally:
        conn.close()
    assert row == ("FAILED", "working", "copy failed", 1)

