from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from rich.console import Console


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ForgeError(Exception):
    """Base exception for user-facing Forge errors."""


@dataclass(frozen=True)
class DryRunContext:
    """Small guard object used by commands to avoid side effects."""

    enabled: bool = False
    console: Console | None = None

    def echo(self, message: str) -> None:
        prefix = "[DRY RUN] " if self.enabled else ""
        target = self.console or Console()
        target.print(f"{prefix}{message}")

    def require_write(self, action: str) -> bool:
        if self.enabled:
            self.echo(action)
            return False
        return True

    def require_db_write(self, action: str) -> bool:
        return self.require_write(action)

    def require_api_call(self, action: str) -> bool:
        return self.require_write(action)


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def iter_supported_images(folder: Path) -> Iterable[Path]:
    for path in folder.rglob("*"):
        if is_supported_image(path):
            yield path


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text_if_allowed(path: Path, content: str, dry_run: DryRunContext) -> None:
    if not dry_run.require_write(f"Would write {path}"):
        return
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def mkdir_if_allowed(path: Path, dry_run: DryRunContext) -> None:
    if not dry_run.require_write(f"Would create directory {path}"):
        return
    path.mkdir(parents=True, exist_ok=True)


def run_if_allowed(dry_run: DryRunContext, action: str, fn: Callable[[], None]) -> None:
    if not dry_run.require_write(action):
        return
    fn()

