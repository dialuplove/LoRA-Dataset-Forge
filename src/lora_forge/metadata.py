from __future__ import annotations

import hashlib
from pathlib import Path

import imagehash
from PIL import Image


def compute_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_perceptual_hash(path: Path) -> str | None:
    try:
        with Image.open(path) as image:
            return str(imagehash.phash(image))
    except Exception:
        return None

