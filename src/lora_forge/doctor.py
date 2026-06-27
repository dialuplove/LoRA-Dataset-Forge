from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DoctorResult:
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def doctor_project(project_dir: Path, conn) -> DoctorResult:
    result = DoctorResult()
    if not (project_dir / "project.json").exists():
        result.issues.append("project.json is missing")
    if not (project_dir / "forge.db").exists():
        result.issues.append("forge.db is missing")

    imported = conn.execute(
        "SELECT source_filename FROM images WHERE import_status = 'IMPORTED'"
    ).fetchall()
    for row in imported:
        if row["source_filename"] and not (project_dir / "source" / row["source_filename"]).exists():
            result.issues.append(f"Missing source file: {row['source_filename']}")

    working = conn.execute(
        "SELECT working_filename, caption_filename, caption_status FROM images WHERE working_status = 'WORKING_CREATED'"
    ).fetchall()
    for row in working:
        if row["working_filename"] and not (project_dir / "working" / row["working_filename"]).exists():
            result.issues.append(f"Missing working file: {row['working_filename']}")
        if row["caption_status"] == "CAPTIONED" and row["caption_filename"]:
            if not (project_dir / "working" / row["caption_filename"]).exists():
                result.issues.append(f"Missing caption file: {row['caption_filename']}")
    return result

