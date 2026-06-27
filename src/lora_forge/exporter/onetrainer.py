from __future__ import annotations

import shutil
from pathlib import Path

from lora_forge.config import ProjectConfig
from lora_forge.exif import strip_exif
from lora_forge.renamer import caption_filename_for, working_filename
from lora_forge.state import ImageRecord

from .base import ExportAdapter


class OneTrainerExporter(ExportAdapter):
    @property
    def name(self) -> str:
        return "onetrainer"

    @property
    def export_subdir(self) -> str:
        return "onetrainer"

    def target_dir(self, export_base: Path, config: ProjectConfig, repeats: int) -> Path:
        return export_base / self.export_subdir

    def export(
        self,
        working_dir: Path,
        export_base: Path,
        images: list[ImageRecord],
        config: ProjectConfig,
        repeats: int,
        dry_run: bool = False,
    ) -> list[tuple[ImageRecord, Path]]:
        target_dir = self.target_dir(export_base, config, repeats)
        exported: list[tuple[ImageRecord, Path]] = []
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        for index, image in enumerate(images, start=1):
            exported_name = working_filename(config, index, image.file_extension)
            image_target = target_dir / exported_name
            caption_target = target_dir / caption_filename_for(exported_name)
            if not dry_run:
                strip_exif(working_dir / (image.working_filename or ""), image_target)
                caption_source = working_dir / (image.caption_filename or "")
                if caption_source.exists():
                    shutil.copy2(caption_source, caption_target)
            exported.append((image, image_target))
        return exported

