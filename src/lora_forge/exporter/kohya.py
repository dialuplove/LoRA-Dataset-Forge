from __future__ import annotations

from pathlib import Path

from lora_forge.config import ProjectConfig

from .onetrainer import OneTrainerExporter


class KohyaExporter(OneTrainerExporter):
    @property
    def name(self) -> str:
        return "kohya"

    @property
    def export_subdir(self) -> str:
        return "kohya"

    def target_dir(self, export_base: Path, config: ProjectConfig, repeats: int) -> Path:
        return export_base / self.export_subdir / f"{repeats}_{config.trigger_token} {config.class_token}"

