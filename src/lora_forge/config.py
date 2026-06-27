from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


GENERIC_CLASS_WORDS = {
    "woman",
    "man",
    "person",
    "girl",
    "boy",
    "child",
    "dog",
    "cat",
    "animal",
    "character",
    "style",
    "portrait",
    "photo",
    "image",
    "picture",
}

CHARACTER_MODE_CLASS_TOKENS = {
    "woman",
    "man",
    "person",
    "girl",
    "boy",
    "child",
    "dog",
    "cat",
    "animal",
    "character",
}

SAFE_TOKEN_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class QualityConfig(BaseModel):
    min_width: int = 512
    min_height: int = 512
    max_aspect_ratio: float = 2.5
    blur_threshold: float = 100.0
    dark_threshold: int = 35
    bright_threshold: int = 220


class CaptionLintConfig(BaseModel):
    min_chars: int = 20
    max_chars: int = 220


class DedupeConfig(BaseModel):
    phash_threshold: int = 10


class ExportConfig(BaseModel):
    default_repeats: int = 20
    preserve_format: bool = True
    convert_format: str | None = None
    default_target: str = "onetrainer"


class ProjectConfig(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    project_name: str
    trigger_token: str
    class_token: str
    source_folder: str
    caption_mode: str = "character"
    openai_model: str = "gpt-4o"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    quality: QualityConfig = Field(default_factory=QualityConfig)
    caption_lint: CaptionLintConfig = Field(default_factory=CaptionLintConfig)
    dedupe: DedupeConfig = Field(default_factory=DedupeConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)

    @property
    def caption_prefix(self) -> str:
        return f"{self.trigger_token} {self.class_token},"

    @field_validator("trigger_token")
    @classmethod
    def validate_trigger_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Trigger token is required")
        if " " in value:
            raise ValueError("Trigger token must not contain spaces")
        if not SAFE_TOKEN_PATTERN.match(value):
            raise ValueError("Trigger token contains unsafe characters")
        if value.lower() in GENERIC_CLASS_WORDS:
            raise ValueError("Trigger token must not be a common class word")
        return value

    @field_validator("class_token")
    @classmethod
    def validate_class_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Class token is required")
        return value

    @model_validator(mode="after")
    def validate_token_pair(self) -> "ProjectConfig":
        if self.trigger_token.lower() == self.class_token.lower():
            raise ValueError("Trigger token must differ from class token")
        if (
            self.caption_mode == "character"
            and self.class_token.lower() not in CHARACTER_MODE_CLASS_TOKENS
        ):
            choices = ", ".join(sorted(CHARACTER_MODE_CLASS_TOKENS))
            raise ValueError(
                f"Class token '{self.class_token}' is not compatible with character mode. "
                f"Use one of: {choices}"
            )
        return self

    def to_json_text(self) -> str:
        return self.model_dump_json(indent=2)

    def write(self, path: Path) -> None:
        path.write_text(self.to_json_text() + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "ProjectConfig":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ProjectConfig":
        return cls.model_validate(data)


def load_project_config(project_dir: Path) -> ProjectConfig:
    return ProjectConfig.read(project_dir / "project.json")


def write_project_config(config: ProjectConfig, project_dir: Path) -> None:
    config.write(project_dir / "project.json")


def project_config_from_json(text: str) -> ProjectConfig:
    return ProjectConfig.model_validate(json.loads(text))

