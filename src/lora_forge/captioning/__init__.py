from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lora_forge.config import ProjectConfig
from lora_forge.linting import has_error_warnings, lint_and_fix, lint_caption
from lora_forge.state import get_images_by_stage_status, update_stage_status, utc_now
from lora_forge.utils import DryRunContext

from .openai_captioner import CaptionResult, OpenAICaptioner, load_api_key
from .prompts import render_character_prompt


class Captioner(Protocol):
    def generate_caption(self, image_path: Path, prompt: str) -> CaptionResult:
        ...


@dataclass
class CaptionSummary:
    generated: int = 0
    reused: int = 0
    repaired: int = 0
    skipped: int = 0
    failed: int = 0


def enforce_prefix(text: str, config: ProjectConfig) -> str:
    prefix = config.caption_prefix
    cleaned = " ".join(text.strip().split())
    while cleaned.startswith(prefix + " " + prefix):
        cleaned = cleaned[len(prefix) :].strip()
    if cleaned.startswith(prefix):
        rest = cleaned[len(prefix) :].strip()
        return f"{prefix} {rest}".strip()
    without_duplicate = cleaned.replace(prefix, "").strip()
    return f"{prefix} {without_duplicate}".strip()


def caption_images(
    project_dir: Path,
    conn,
    config: ProjectConfig,
    *,
    captioner: Captioner | None = None,
    force: bool = False,
    limit: int | None = None,
    dry_run: DryRunContext | None = None,
) -> CaptionSummary:
    dry_run = dry_run or DryRunContext(False)
    summary = CaptionSummary()
    images = get_images_by_stage_status(conn, "working", "WORKING_CREATED")
    eligible = [
        image
        for image in images
        if image.acceptance_status == "ACCEPTED"
        and (force or image.caption_status != "CAPTIONED")
    ]
    if limit is not None:
        eligible = eligible[:limit]

    if captioner is None and any(_needs_captioner(project_dir, image, config, force) for image in eligible):
        captioner = OpenAICaptioner(load_api_key(project_dir), config.openai_model)

    for image in eligible:
        image_path = project_dir / "working" / (image.working_filename or "")
        caption_path = project_dir / "working" / (image.caption_filename or f"{image_path.stem}.txt")
        if not force and caption_path.exists():
            text = caption_path.read_text(encoding="utf-8").strip()
            warnings = lint_caption(text, config.trigger_token, config.class_token, config.caption_lint)
            if text and not has_error_warnings(warnings):
                _record_caption(conn, image.id, text, "existing_file")
                update_stage_status(conn, image.id, "caption", "CAPTIONED", current_caption_id=_last_caption_id(conn))
                summary.reused += 1
                continue
            fixed, fixed_warnings = lint_and_fix(text, config.trigger_token, config.class_token)
            if fixed and not has_error_warnings(fixed_warnings):
                if dry_run.enabled:
                    dry_run.echo(f"Would repair caption {caption_path}")
                else:
                    caption_path.write_text(fixed + "\n", encoding="utf-8")
                    _record_caption(conn, image.id, fixed, "repaired")
                    update_stage_status(conn, image.id, "caption", "CAPTIONED", current_caption_id=_last_caption_id(conn))
                summary.repaired += 1
                continue

        if dry_run.enabled:
            dry_run.echo(f"Would call OpenAI captioner for {image_path}")
            summary.generated += 1
            continue
        if captioner is None:
            summary.failed += 1
            continue
        prompt = render_character_prompt(config)
        result = captioner.generate_caption(image_path, prompt)
        if not result.success or not result.text:
            conn.execute(
                """
                UPDATE images SET caption_status = 'FAILED', failed_stage = 'caption',
                    last_error = ?, retry_count = retry_count + 1, last_attempted_at = ?
                WHERE id = ?
                """,
                (result.error or "Caption generation failed", utc_now(), image.id),
            )
            summary.failed += 1
            continue
        caption_text = enforce_prefix(result.text, config)
        caption_path.write_text(caption_text + "\n", encoding="utf-8")
        _record_caption(
            conn,
            image.id,
            caption_text,
            "openai",
            model_name=result.model_name,
            prompt_version=result.prompt_version,
            token_count=result.token_count,
        )
        update_stage_status(
            conn,
            image.id,
            "caption",
            "CAPTIONED",
            current_caption_id=_last_caption_id(conn),
            captioned_at=utc_now(),
            lifecycle_state="CAPTIONED",
        )
        summary.generated += 1
    return summary


def _needs_captioner(project_dir: Path, image, config: ProjectConfig, force: bool) -> bool:
    if force:
        return True
    caption_path = project_dir / "working" / (image.caption_filename or "")
    if not caption_path.exists():
        return True
    text = caption_path.read_text(encoding="utf-8").strip()
    fixed, warnings = lint_and_fix(text, config.trigger_token, config.class_token)
    return not fixed or has_error_warnings(warnings)


def _record_caption(
    conn,
    image_id: int,
    text: str,
    source: str,
    *,
    model_name: str | None = None,
    prompt_version: str | None = None,
    token_count: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO captions (
            image_id, caption_text, caption_source, model_name, prompt_version,
            generated_at, generation_status, retry_count, token_count
        ) VALUES (?, ?, ?, ?, ?, ?, 'success', 0, ?)
        """,
        (image_id, text, source, model_name, prompt_version, utc_now(), token_count),
    )


def _last_caption_id(conn) -> int:
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

