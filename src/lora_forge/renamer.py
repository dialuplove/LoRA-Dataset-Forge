from __future__ import annotations

from pathlib import Path

from .config import ProjectConfig


def working_filename(config: ProjectConfig, index: int, original_extension: str) -> str:
    return f"{config.trigger_token}_{index:04d}{original_extension.lower()}"


def caption_filename_for(image_filename: str) -> str:
    return f"{Path(image_filename).stem}.txt"


def next_working_index(conn) -> int:
    value = conn.execute("SELECT COALESCE(MAX(working_index), 0) FROM images").fetchone()[0]
    return int(value) + 1

