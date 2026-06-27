from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import piexif
from PIL import Image
from PIL.PngImagePlugin import PngInfo


@dataclass(frozen=True)
class ExifStripResult:
    success: bool
    method: str
    recompressed: bool
    error: str | None = None


def strip_exif(input_path: Path, output_path: Path) -> ExifStripResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ext = input_path.suffix.lower()
    try:
        if ext in {".jpg", ".jpeg"}:
            return strip_exif_jpeg(input_path, output_path)
        if ext == ".png":
            return strip_exif_png(input_path, output_path)
        if ext == ".webp":
            return strip_exif_webp(input_path, output_path)
        raise ValueError(f"Unsupported image format for EXIF stripping: {ext}")
    except Exception as exc:
        return ExifStripResult(False, "failed", False, str(exc))


def strip_exif_jpeg(input_path: Path, output_path: Path) -> ExifStripResult:
    # The two-argument form writes a separate output file and leaves input untouched.
    piexif.remove(str(input_path), str(output_path))
    return ExifStripResult(True, "piexif_remove", False)


def strip_exif_png(input_path: Path, output_path: Path) -> ExifStripResult:
    with Image.open(input_path) as image:
        image.save(output_path, pnginfo=PngInfo())
    return ExifStripResult(True, "pillow_png_metadata_strip", False)


def strip_exif_webp(input_path: Path, output_path: Path) -> ExifStripResult:
    with Image.open(input_path) as image:
        image.save(output_path, format="WEBP", exif=b"")
    return ExifStripResult(True, "pillow_webp_resave", True)

