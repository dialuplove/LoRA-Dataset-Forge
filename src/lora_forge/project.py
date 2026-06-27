from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .config import ProjectConfig, write_project_config
from .state import init_db
from .utils import DryRunContext, ForgeError, iter_supported_images, mkdir_if_allowed, normalize_path, write_text_if_allowed


PROJECT_DIRS = ("source", "working", "exports", "duplicates", "rejected", "reports")

PROJECT_GITIGNORE = """# Secrets
.env

# Local Forge state
forge.db
source/
working/
exports/
duplicates/
rejected/

# Images
*.jpg
*.jpeg
*.png
*.webp
*.heic
*.tiff
*.bmp

# OS noise
.DS_Store
Thumbs.db
"""


@dataclass(frozen=True)
class InitResult:
    project_dir: Path
    config: ProjectConfig
    dry_run: bool = False


def project_dir_for_name(base_dir: Path, project_name: str) -> Path:
    return base_dir / project_name


def validate_input_folder(input_folder: Path) -> None:
    if not input_folder.exists():
        raise ForgeError(f"Input folder does not exist: {input_folder}")
    if not input_folder.is_dir():
        raise ForgeError(f"Input folder is not a directory: {input_folder}")
    if not any(iter_supported_images(input_folder)):
        raise ForgeError(f"Input folder contains no supported images: {input_folder}")


def init_project(
    input_folder: str | Path,
    project_name: str,
    trigger_token: str,
    class_token: str,
    *,
    base_dir: str | Path = ".",
    dry_run: DryRunContext | None = None,
) -> InitResult:
    dry_run = dry_run or DryRunContext(False)
    input_path = normalize_path(input_folder)
    base_path = normalize_path(base_dir)
    project_dir = project_dir_for_name(base_path, project_name)

    validate_input_folder(input_path)
    if project_dir.exists() and not dry_run.enabled:
        raise ForgeError(f"Project already exists: {project_dir}")

    try:
        config = ProjectConfig(
            project_name=project_name,
            trigger_token=trigger_token,
            class_token=class_token,
            source_folder=str(input_path),
        )
    except ValidationError as exc:
        raise ForgeError(str(exc)) from exc

    if dry_run.enabled:
        dry_run.echo(f"Would create project at {project_dir}")
        for dirname in PROJECT_DIRS:
            dry_run.echo(f"Would create directory {project_dir / dirname}")
        dry_run.echo(f"Would write {project_dir / 'project.json'}")
        dry_run.echo(f"Would initialize {project_dir / 'forge.db'}")
        dry_run.echo(f"Would write {project_dir / '.env.example'}")
        dry_run.echo(f"Would write {project_dir / '.gitignore'}")
        return InitResult(project_dir=project_dir, config=config, dry_run=True)

    project_dir.mkdir(parents=True, exist_ok=False)
    for dirname in PROJECT_DIRS:
        mkdir_if_allowed(project_dir / dirname, dry_run)
    write_project_config(config, project_dir)
    init_db(project_dir / "forge.db")
    write_text_if_allowed(project_dir / ".env.example", "OPENAI_API_KEY=your-key-here\n", dry_run)
    write_text_if_allowed(project_dir / ".gitignore", PROJECT_GITIGNORE, dry_run)
    return InitResult(project_dir=project_dir, config=config)

