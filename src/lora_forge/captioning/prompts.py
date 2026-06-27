from __future__ import annotations

from lora_forge.config import ProjectConfig


PROMPT_VERSION = "character_v1"

CHARACTER_CAPTION_PROMPT = """You are generating training captions for a LoRA character dataset.

RULES:
- Begin with EXACTLY: "{trigger_token} {class_token},"
- Follow with comma-separated descriptive tags
- Describe: pose, clothing, expression, setting, lighting, camera angle/framing
- Use concise, factual phrases
- Do NOT use poetic language, subjective opinions, or full sentences
- Do NOT guess identity, age, ethnicity, or sensitive attributes
- Do NOT reference private metadata, EXIF data, or filenames
- Keep the caption between 20 and 220 characters total

Generate a caption for this image:
"""


def render_character_prompt(config: ProjectConfig) -> str:
    return CHARACTER_CAPTION_PROMPT.format(
        trigger_token=config.trigger_token,
        class_token=config.class_token,
    )

