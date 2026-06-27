from __future__ import annotations

from PIL import Image

from lora_forge.project import PROJECT_DIRS, init_project
from lora_forge.utils import DryRunContext


def create_image(path):
    Image.new("RGB", (8, 8), color=(255, 0, 0)).save(path)


def test_init_project_creates_workspace(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "a.jpg")

    result = init_project(input_dir, "demo", "dawivre", "woman", base_dir=tmp_path)

    assert result.project_dir == tmp_path / "demo"
    assert (result.project_dir / "project.json").exists()
    assert (result.project_dir / "forge.db").exists()
    for dirname in PROJECT_DIRS:
        assert (result.project_dir / dirname).is_dir()
    assert "OPENAI_API_KEY" in (result.project_dir / ".env.example").read_text()


def test_init_project_dry_run_creates_nothing(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "a.jpg")

    result = init_project(
        input_dir,
        "demo",
        "dawivre",
        "woman",
        base_dir=tmp_path,
        dry_run=DryRunContext(True),
    )

    assert result.dry_run
    assert not (tmp_path / "demo").exists()

