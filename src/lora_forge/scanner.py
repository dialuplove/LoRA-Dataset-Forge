from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .metadata import compute_file_hash, compute_perceptual_hash
from .state import get_image_by_original_path, insert_discovered_image
from .utils import DryRunContext, SUPPORTED_IMAGE_EXTENSIONS


IGNORE_DIRS = {
    ".obsidian",
    ".git",
    ".kiro",
    "__MACOSX",
    "node_modules",
    ".venv",
    "venv",
    "exports",
    "working",
    "source",
    "duplicates",
    "rejected",
    "reports",
}

IGNORE_FILES = {".DS_Store", "Thumbs.db"}


@dataclass
class ScanResult:
    discovered: int = 0
    skipped_existing: int = 0
    skipped_paths: list[Path] = field(default_factory=list)


def should_ignore_dir(path: Path) -> bool:
    return path.name in IGNORE_DIRS


def discover_image_paths(input_folder: Path) -> tuple[list[Path], list[Path]]:
    images: list[Path] = []
    skipped: list[Path] = []

    def visit(folder: Path) -> None:
        for path in sorted(folder.iterdir()):
            if path.is_dir():
                if should_ignore_dir(path):
                    skipped.append(path)
                    continue
                visit(path)
                continue
            if path.name in IGNORE_FILES:
                skipped.append(path)
                continue
            if path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                images.append(path)

    visit(input_folder)
    return images, skipped


def scan(input_folder: Path, conn, dry_run: DryRunContext | None = None) -> ScanResult:
    dry_run = dry_run or DryRunContext(False)
    paths, skipped = discover_image_paths(input_folder)
    result = ScanResult(skipped_paths=skipped)
    for path in paths:
        original_path = str(path.resolve())
        if get_image_by_original_path(conn, original_path):
            result.skipped_existing += 1
            continue
        if dry_run.enabled:
            dry_run.echo(f"Would discover image {path}")
            result.discovered += 1
            continue
        insert_discovered_image(
            conn,
            original_filename=path.name,
            original_path=original_path,
            file_extension=path.suffix.lower(),
            file_size=path.stat().st_size,
            file_hash=compute_file_hash(path),
            perceptual_hash=compute_perceptual_hash(path),
        )
        result.discovered += 1
    return result

