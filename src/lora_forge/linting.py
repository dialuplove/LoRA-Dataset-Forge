from __future__ import annotations

from dataclasses import dataclass

from .config import CaptionLintConfig


SUBJECTIVE_WORDS = {"beautiful", "stunning", "gorgeous", "perfect", "amazing"}


@dataclass
class LintWarning:
    filename: str
    rule_id: str
    severity: str
    message: str
    excerpt: str
    fixable: bool
    fixed: bool = False


def lint_caption(
    caption_text: str,
    trigger_token: str,
    class_token: str,
    config: CaptionLintConfig,
    all_captions: dict[str, str] | None = None,
    filename: str = "",
) -> list[LintWarning]:
    text = caption_text.strip()
    prefix = f"{trigger_token} {class_token},"
    warnings: list[LintWarning] = []
    if not text:
        warnings.append(_warning(filename, "EMPTY_CAPTION", "ERROR", "Caption is empty", text, False))
        return warnings
    if not text.startswith(prefix):
        warnings.append(_warning(filename, "PREFIX_MISSING", "ERROR", "Caption prefix is missing", text, True))
    if trigger_token not in text:
        warnings.append(_warning(filename, "PREFIX_TRIGGER_MISSING", "ERROR", "Trigger token is missing", text, True))
    if not text.startswith(f"{trigger_token} {class_token}"):
        warnings.append(_warning(filename, "PREFIX_CLASS_MISSING", "ERROR", "Class token is missing or misplaced", text, True))
    if text.count(prefix) > 1:
        warnings.append(_warning(filename, "PREFIX_DUPLICATED", "WARNING", "Caption prefix is duplicated", text, True))
    if text.startswith(f"{trigger_token} {class_token}") and not text.startswith(prefix):
        warnings.append(_warning(filename, "PREFIX_COMMA_MISSING", "ERROR", "Caption prefix comma is missing", text, True))
    if len(text) < config.min_chars:
        warnings.append(_warning(filename, "CAPTION_TOO_SHORT", "WARNING", "Caption is too short", text, False))
    if len(text) > config.max_chars:
        warnings.append(_warning(filename, "CAPTION_TOO_LONG", "WARNING", "Caption is too long", text, False))
    lower = text.lower()
    if any(word in lower for word in SUBJECTIVE_WORDS):
        warnings.append(_warning(filename, "SUBJECTIVE_LANGUAGE", "WARNING", "Caption contains subjective language", text, False))
    if text != " ".join(text.split()):
        warnings.append(_warning(filename, "EXCESS_WHITESPACE", "WARNING", "Caption has excess whitespace", text, True))
    if all_captions:
        duplicates = [name for name, other in all_captions.items() if name != filename and other.strip() == text]
        if duplicates:
            warnings.append(_warning(filename, "DUPLICATE_CAPTION", "WARNING", "Caption text is duplicated", text, False))
    return warnings


def lint_and_fix(
    caption_text: str,
    trigger_token: str,
    class_token: str,
) -> tuple[str, list[LintWarning]]:
    config = CaptionLintConfig()
    prefix = f"{trigger_token} {class_token},"
    text = " ".join(caption_text.strip().split())
    if text.startswith(f"{trigger_token} {class_token}") and not text.startswith(prefix):
        text = prefix + text[len(f"{trigger_token} {class_token}") :].lstrip(" ,")
    if text.count(prefix) > 1:
        text = prefix + " " + text.replace(prefix, "").strip()
    if text and not text.startswith(prefix):
        text = f"{prefix} {text}"
    return text, lint_caption(text, trigger_token, class_token, config)


def has_error_warnings(warnings: list[LintWarning]) -> bool:
    return any(warning.severity == "ERROR" for warning in warnings)


def _warning(filename: str, rule_id: str, severity: str, message: str, text: str, fixable: bool) -> LintWarning:
    return LintWarning(filename, rule_id, severity, message, text[:80], fixable)

