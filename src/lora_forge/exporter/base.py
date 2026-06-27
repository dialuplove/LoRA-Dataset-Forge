from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from lora_forge.config import ProjectConfig
from lora_forge.state import ImageRecord


class ExportAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def export_subdir(self) -> str:
        ...

    @abstractmethod
    def target_dir(self, export_base: Path, config: ProjectConfig, repeats: int) -> Path:
        ...

    @abstractmethod
    def export(
        self,
        working_dir: Path,
        export_base: Path,
        images: list[ImageRecord],
        config: ProjectConfig,
        repeats: int,
        dry_run: bool = False,
    ) -> list[tuple[ImageRecord, Path]]:
        ...

    def validate_pre_export(
        self,
        images: list[ImageRecord],
        working_dir: Path,
        allow_missing_captions: bool = False,
    ) -> list[str]:
        errors: list[str] = []
        for image in images:
            if not image.working_filename:
                errors.append(f"Image {image.id} missing working filename")
                continue
            caption_name = image.caption_filename
            if not caption_name:
                errors.append(f"Image {image.working_filename} missing caption filename")
                continue
            if not (working_dir / caption_name).exists() and not allow_missing_captions:
                errors.append(f"Missing caption: {caption_name}")
        return errors

