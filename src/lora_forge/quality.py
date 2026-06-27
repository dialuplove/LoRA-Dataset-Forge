from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageStat

from .config import ProjectConfig
from .state import get_images_by_stage_status, record_error, update_stage_status, utc_now
from .utils import DryRunContext


@dataclass
class QualityResult:
    validated: int = 0
    passed: int = 0
    warned: int = 0
    failed: int = 0
    warning_counts: dict[str, int] = field(default_factory=dict)


def _source_path(project_dir: Path, source_filename: str | None) -> Path:
    if not source_filename:
        raise ValueError("Image is missing source_filename")
    return project_dir / "source" / source_filename


def validate_and_check_quality(
    project_dir: Path,
    conn,
    config: ProjectConfig,
    dry_run: DryRunContext | None = None,
) -> QualityResult:
    dry_run = dry_run or DryRunContext(False)
    result = QualityResult()
    candidates = get_images_by_stage_status(conn, "import", "IMPORTED")
    for image in candidates:
        if image.validation_status == "VALIDATED" and image.quality_status in {"PASS", "QUALITY_WARNING"}:
            continue
        source_path = _source_path(project_dir, image.source_filename)
        if dry_run.enabled:
            dry_run.echo(f"Would validate and quality-check {source_path}")
            result.validated += 1
            continue
        try:
            width, height, flags = inspect_image_quality(source_path, config)
            update_stage_status(
                conn,
                image.id,
                "validation",
                "VALIDATED",
                width=width,
                height=height,
                validated_at=utc_now(),
            )
            quality_status = "QUALITY_WARNING" if flags else "PASS"
            update_stage_status(
                conn,
                image.id,
                "quality",
                quality_status,
                quality_flags=",".join(flags) if flags else None,
            )
            result.validated += 1
            if flags:
                result.warned += 1
                for flag in flags:
                    result.warning_counts[flag] = result.warning_counts.get(flag, 0) + 1
            else:
                result.passed += 1
        except Exception as exc:
            record_error(conn, image.id, "validation", str(exc))
            conn.execute(
                "UPDATE images SET quality_flags = ? WHERE id = ?",
                ("ERROR_UNREADABLE", image.id),
            )
            result.failed += 1
    return result


def inspect_image_quality(path: Path, config: ProjectConfig) -> tuple[int, int, list[str]]:
    with Image.open(path) as image:
        image.load()
        width, height = image.size
        flags: list[str] = []
        if width < config.quality.min_width or height < config.quality.min_height:
            flags.append("WARN_LOW_RESOLUTION")
        aspect_ratio = max(width / height, height / width)
        if aspect_ratio > config.quality.max_aspect_ratio:
            flags.append("WARN_EXTREME_ASPECT")

        gray = image.convert("L")
        mean_brightness = ImageStat.Stat(gray).mean[0]
        if mean_brightness < config.quality.dark_threshold:
            flags.append("WARN_DARK")
        if mean_brightness > config.quality.bright_threshold:
            flags.append("WARN_BRIGHT")

        array = np.array(gray)
        variance = float(cv2.Laplacian(array, cv2.CV_64F).var())
        if variance < config.quality.blur_threshold:
            flags.append("WARN_BLURRY")
        return width, height, flags

