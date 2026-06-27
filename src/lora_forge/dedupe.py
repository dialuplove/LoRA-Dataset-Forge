from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig
from .state import get_images_by_stage_status, update_stage_status
from .utils import DryRunContext


@dataclass
class DedupeResult:
    exact_duplicates: int = 0
    near_duplicates: int = 0
    no_duplicate: int = 0


def hamming_distance_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def detect_duplicates(
    project_dir: Path,
    conn,
    config: ProjectConfig,
    dry_run: DryRunContext | None = None,
) -> DedupeResult:
    dry_run = dry_run or DryRunContext(False)
    result = DedupeResult()
    images = get_images_by_stage_status(conn, "validation", "VALIDATED")
    seen_hashes: dict[str, int] = {}
    seen_phashes: list[tuple[str, int]] = []
    for image in images:
        if image.dedupe_status in {"NO_DUPLICATE", "DUPLICATE_CANDIDATE"}:
            continue
        duplicate_type = None
        duplicate_of_id = None
        distance = None
        if image.file_hash and image.file_hash in seen_hashes:
            duplicate_type = "exact"
            duplicate_of_id = seen_hashes[image.file_hash]
        elif image.perceptual_hash:
            for phash, other_id in seen_phashes:
                current_distance = hamming_distance_hex(image.perceptual_hash, phash)
                if current_distance <= config.dedupe.phash_threshold:
                    duplicate_type = "near"
                    duplicate_of_id = other_id
                    distance = current_distance
                    break

        if dry_run.enabled:
            dry_run.echo(f"Would dedupe {image.original_filename}")
        elif duplicate_type:
            update_stage_status(
                conn,
                image.id,
                "dedupe",
                "DUPLICATE_CANDIDATE",
                duplicate_of_id=duplicate_of_id,
                duplicate_type=duplicate_type,
                hamming_distance=distance,
                lifecycle_state="DUPLICATE_CANDIDATE",
            )
            _copy_duplicate_candidate(project_dir, image.source_filename)
        else:
            update_stage_status(conn, image.id, "dedupe", "NO_DUPLICATE")

        if duplicate_type == "exact":
            result.exact_duplicates += 1
        elif duplicate_type == "near":
            result.near_duplicates += 1
        else:
            result.no_duplicate += 1

        if image.file_hash and image.file_hash not in seen_hashes:
            seen_hashes[image.file_hash] = image.id
        if image.perceptual_hash:
            seen_phashes.append((image.perceptual_hash, image.id))
    return result


def _copy_duplicate_candidate(project_dir: Path, source_filename: str | None) -> None:
    if not source_filename:
        return
    source = project_dir / "source" / source_filename
    target = project_dir / "duplicates" / source_filename
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

