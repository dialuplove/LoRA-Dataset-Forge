from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import PROMPT_VERSION


@dataclass
class CaptionResult:
    success: bool
    text: str | None = None
    model_name: str | None = None
    prompt_version: str | None = PROMPT_VERSION
    token_count: int | None = None
    error: str | None = None


class OpenAICaptioner:
    def __init__(self, api_key: str, model: str, max_retries: int = 3):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def generate_caption(self, image_path: Path, prompt: str) -> CaptionResult:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        mime = _mime_for_suffix(image_path.suffix)
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                                },
                            ],
                        }
                    ],
                )
                text = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                token_count = getattr(usage, "total_tokens", None) if usage else None
                return CaptionResult(True, text=text.strip(), model_name=self.model, token_count=token_count)
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 60))
        return CaptionResult(False, error=last_error)

    def test_connection(self) -> CaptionResult:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Reply with ok."}],
                max_tokens=5,
            )
            text = response.choices[0].message.content or ""
            return CaptionResult(True, text=text.strip(), model_name=self.model)
        except Exception as exc:
            return CaptionResult(False, error=str(exc))


def load_api_key(project_dir: Path | None = None) -> str:
    if project_dir:
        load_dotenv(project_dir / ".env")
    load_dotenv(Path.home() / ".env")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return key


def _mime_for_suffix(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"

