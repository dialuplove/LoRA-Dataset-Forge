from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .acceptance import decide_acceptance
from .captioning import caption_images
from .captioning.openai_captioner import OpenAICaptioner, load_api_key
from .config import load_project_config
from .dedupe import detect_duplicates
from .doctor import doctor_project
from .exporter import export_dataset
from .working import build_working
from .importer import import_images
from .project import init_project
from .quality import validate_and_check_quality
from .reporting import generate_report
from .scanner import scan as scan_images
from .state import db_connection
from .status import project_status
from .utils import DryRunContext, ForgeError


app = typer.Typer(help="Prepare LoRA image datasets for training.")
console = Console()


@app.command()
def init(
    input_folder: Path = typer.Argument(..., help="Folder of source images."),
    name: str = typer.Option(..., "--name", help="Project name."),
    trigger: str = typer.Option(..., "--trigger", help="Unique trigger token."),
    class_token: str = typer.Option(..., "--class-token", help="Subject class token."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Initialize a managed dataset project."""
    try:
        result = init_project(
            input_folder,
            name,
            trigger,
            class_token,
            dry_run=DryRunContext(enabled=dry_run, console=console),
        )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.dry_run:
        return
    console.print(f"Created project: {result.project_dir}")


def current_project_dir() -> Path:
    project_dir = Path.cwd()
    if not (project_dir / "project.json").exists() or not (project_dir / "forge.db").exists():
        raise ForgeError("No LoRA Dataset Forge project found in the current directory")
    return project_dir


@app.command()
def scan(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Discover candidate images from the configured input folder."""
    try:
        project_dir = current_project_dir()
        config = load_project_config(project_dir)
        with db_connection(project_dir / "forge.db") as conn:
            result = scan_images(
                Path(config.source_folder),
                conn,
                DryRunContext(enabled=dry_run, console=console),
            )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        f"Discovered: {result.discovered}; skipped existing: {result.skipped_existing}; "
        f"ignored paths: {len(result.skipped_paths)}"
    )


@app.command(name="import")
def import_command(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Copy discovered images into immutable source/ storage."""
    try:
        project_dir = current_project_dir()
        with db_connection(project_dir / "forge.db") as conn:
            result = import_images(
                project_dir,
                conn,
                DryRunContext(enabled=dry_run, console=console),
            )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Imported: {result.imported}; skipped: {result.skipped}; failed: {result.failed}")


@app.command()
def quality(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Validate imported images and flag basic quality issues."""
    try:
        project_dir = current_project_dir()
        config = load_project_config(project_dir)
        with db_connection(project_dir / "forge.db") as conn:
            result = validate_and_check_quality(
                project_dir,
                conn,
                config,
                DryRunContext(enabled=dry_run, console=console),
            )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        f"Validated: {result.validated}; passed: {result.passed}; "
        f"warned: {result.warned}; failed: {result.failed}"
    )


@app.command()
def dedupe(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Detect exact and near-duplicate validated images."""
    try:
        project_dir = current_project_dir()
        config = load_project_config(project_dir)
        with db_connection(project_dir / "forge.db") as conn:
            result = detect_duplicates(
                project_dir,
                conn,
                config,
                DryRunContext(enabled=dry_run, console=console),
            )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        f"Exact duplicates: {result.exact_duplicates}; near duplicates: {result.near_duplicates}; "
        f"unique: {result.no_duplicate}"
    )


@app.command()
def accept(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Apply the default accept/reject decision policy."""
    try:
        project_dir = current_project_dir()
        with db_connection(project_dir / "forge.db") as conn:
            result = decide_acceptance(
                project_dir,
                conn,
                DryRunContext(enabled=dry_run, console=console),
            )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Accepted: {result.accepted}; rejected: {result.rejected}; skipped: {result.skipped}")


@app.command("build-working")
def build_working_command(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Build EXIF-stripped sequential working images from accepted source images."""
    try:
        project_dir = current_project_dir()
        config = load_project_config(project_dir)
        with db_connection(project_dir / "forge.db") as conn:
            result = build_working(
                project_dir,
                conn,
                config,
                DryRunContext(enabled=dry_run, console=console),
            )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Working images created: {result.created}; skipped: {result.skipped}; failed: {result.failed}")


@app.command()
def caption(
    force: bool = typer.Option(False, "--force", help="Regenerate captions even when present."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum images to process."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Generate, reuse, or repair captions for working images."""
    try:
        project_dir = current_project_dir()
        config = load_project_config(project_dir)
        with db_connection(project_dir / "forge.db") as conn:
            result = caption_images(
                project_dir,
                conn,
                config,
                force=force,
                limit=limit,
                dry_run=DryRunContext(enabled=dry_run, console=console),
            )
    except (ForgeError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        f"Generated: {result.generated}; reused: {result.reused}; repaired: {result.repaired}; "
        f"skipped: {result.skipped}; failed: {result.failed}"
    )


@app.command("test-openai")
def test_openai() -> None:
    """Verify OpenAI API configuration without sending user images."""
    try:
        project_dir = current_project_dir()
        config = load_project_config(project_dir)
        captioner = OpenAICaptioner(load_api_key(project_dir), config.openai_model)
        result = captioner.test_connection()
    except (ForgeError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not result.success:
        raise typer.BadParameter(result.error or "OpenAI connection failed")
    console.print("OpenAI connection succeeded")


@app.command()
def export(
    target: str = typer.Option("onetrainer", "--target", help="Export target: onetrainer, kohya, or all."),
    repeats: int | None = typer.Option(None, "--repeats", help="Kohya repeat count."),
    allow_missing_captions: bool = typer.Option(False, "--allow-missing-captions"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Export the working dataset to a trainer format."""
    try:
        project_dir = current_project_dir()
        config = load_project_config(project_dir)
        with db_connection(project_dir / "forge.db") as conn:
            result = export_dataset(
                project_dir,
                conn,
                config,
                target=target,
                repeats=repeats,
                allow_missing_captions=allow_missing_captions,
                dry_run=DryRunContext(enabled=dry_run, console=console),
            )
    except (ForgeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.errors:
        raise typer.BadParameter("; ".join(result.errors))
    console.print(f"Exported {result.exported_items} images to: {', '.join(result.targets)}")


@app.command()
def report(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Generate Markdown and JSON dataset reports."""
    try:
        project_dir = current_project_dir()
        with db_connection(project_dir / "forge.db") as conn:
            result = generate_report(
                project_dir,
                conn,
                DryRunContext(enabled=dry_run, console=console),
            )
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Wrote reports: {result.markdown_path}, {result.json_path}")


@app.command()
def status() -> None:
    """Display a summary of the current project state."""
    try:
        project_dir = current_project_dir()
        with db_connection(project_dir / "forge.db") as conn:
            data = project_status(project_dir, conn)
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for key, value in data.items():
        console.print(f"{key}: {value}")


@app.command()
def doctor() -> None:
    """Check project file/database integrity."""
    try:
        project_dir = current_project_dir()
        with db_connection(project_dir / "forge.db") as conn:
            result = doctor_project(project_dir, conn)
    except ForgeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.ok:
        console.print("Project integrity check passed")
        return
    for issue in result.issues:
        console.print(f"Issue: {issue}")
    raise typer.Exit(code=1)


@app.command()
def run(
    input_folder: Path = typer.Argument(..., help="Folder of source images."),
    name: str = typer.Option(..., "--name", help="Project name."),
    trigger: str = typer.Option(..., "--trigger", help="Unique trigger token."),
    class_token: str = typer.Option(..., "--class-token", help="Subject class token."),
    repeats: int | None = typer.Option(None, "--repeats", help="Kohya repeat count."),
    target: str = typer.Option("onetrainer", "--target", help="Export target."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without side effects."),
) -> None:
    """Run the full preparation pipeline."""
    context = DryRunContext(enabled=dry_run, console=console)
    init_result = init_project(input_folder, name, trigger, class_token, dry_run=context)
    if dry_run:
        return
    project_dir = init_result.project_dir
    config = init_result.config
    with db_connection(project_dir / "forge.db") as conn:
        scan_images(Path(config.source_folder), conn, context)
        import_images(project_dir, conn, context)
        validate_and_check_quality(project_dir, conn, config, context)
        detect_duplicates(project_dir, conn, config, context)
        decide_acceptance(project_dir, conn, context)
        build_working(project_dir, conn, config, context)
        caption_images(project_dir, conn, config, dry_run=context)
        export_dataset(project_dir, conn, config, target=target, repeats=repeats, dry_run=context)
        generate_report(project_dir, conn, context)
    console.print(f"Pipeline complete: {project_dir}")
