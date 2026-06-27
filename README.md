# LoRA Dataset Forge

A local-first CLI tool that turns messy image folders into clean, captioned, privacy-safe datasets for LoRA training.

LoRA Dataset Forge handles the tedious prep work so you can focus on training: scanning, deduplication, quality checks, EXIF stripping, AI captioning, token enforcement, and export to OneTrainer or kohya_ss format.

## Features

- **Three-stage file lifecycle** — source (immutable copy) → working (renamed, stripped, captioned) → exports (trainer-ready)
- **Privacy-first** — EXIF metadata stripped from working and exported images; originals never modified
- **AI captioning** — OpenAI vision models generate concise, LoRA-friendly captions
- **Caption discovery** — reuses valid existing `.txt` captions without burning API calls
- **Trigger/class token enforcement** — every caption starts with your configured prefix
- **Duplicate detection** — exact (SHA-256) and near-duplicate (perceptual hash) detection
- **Quality checks** — flags low-res, blurry, dark, bright, and extreme aspect ratio images
- **Export profiles** — OneTrainer (default, flat directory) and kohya_ss (`{repeats}_{trigger} {class}/`)
- **Resume-safe** — per-stage state tracking in SQLite; interrupted runs pick up where they left off
- **Dry-run mode** — preview every command's effects without touching files, DB, or API
- **Comprehensive reports** — Markdown and JSON reports with full dataset metrics

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/lora-dataset-forge.git
cd lora-dataset-forge

# Install in development mode
pip install -e ".[dev]"
```

### Requirements

- Python 3.10+
- An OpenAI API key (for caption generation only)

## Quick Start

```bash
# 1. Initialize a project from your image folder
lora-forge init ./my_photos --name my_character_v1 --trigger mychar --class-token woman

# 2. Run the full pipeline
lora-forge run ./my_photos \
  --name my_character_v1 \
  --trigger mychar \
  --class-token woman \
  --target onetrainer
```

Or run each stage individually for more control:

```bash
lora-forge scan
lora-forge import
lora-forge quality
lora-forge dedupe
lora-forge accept
lora-forge build-working
lora-forge caption
lora-forge lint
lora-forge export --target onetrainer
lora-forge report
```

## Configuration

Create a `.env` file in your project directory:

```env
OPENAI_API_KEY=your_api_key_here
```

Project settings are stored in `project.json` with sensible defaults:

```json
{
  "project_name": "my_character_v1",
  "trigger_token": "mychar",
  "class_token": "woman",
  "caption_mode": "character",
  "openai_model": "gpt-4o",
  "quality": {
    "min_width": 512,
    "min_height": 512,
    "max_aspect_ratio": 2.5,
    "blur_threshold": 100.0,
    "dark_threshold": 35,
    "bright_threshold": 220
  },
  "caption_lint": {
    "min_chars": 20,
    "max_chars": 220
  },
  "dedupe": {
    "phash_threshold": 10
  },
  "export": {
    "default_repeats": 20,
    "default_target": "onetrainer"
  }
}
```

## Project Structure

When initialized, a project creates:

```
my_character_v1/
  project.json          # Configuration
  forge.db              # State database
  .env                  # API key (gitignored)
  .env.example          # Template
  .gitignore            # Safe defaults
  source/               # Immutable copies of original images
  working/              # Accepted, renamed, EXIF-stripped images + captions
  exports/              # Trainer-ready exports
    onetrainer/         # Flat image + caption pairs
    kohya/              # {repeats}_{trigger} {class}/ structure
  duplicates/           # Flagged duplicates for review
  rejected/             # Rejected images for reference
  reports/              # Markdown and JSON reports
```

## Commands

| Command | Description |
|---------|-------------|
| `lora-forge init` | Initialize a new project from an image folder |
| `lora-forge scan` | Discover supported images in the input folder |
| `lora-forge import` | Copy images into `source/` (immutable) |
| `lora-forge quality` | Validate images and run quality checks |
| `lora-forge dedupe` | Detect exact and near-duplicate images |
| `lora-forge accept` | Auto-accept/reject based on quality and duplicates |
| `lora-forge build-working` | Copy accepted images to `working/`, rename, strip EXIF |
| `lora-forge caption` | Generate AI captions (or discover existing ones) |
| `lora-forge lint` | Check captions for formatting issues |
| `lora-forge export` | Export dataset for OneTrainer or kohya_ss |
| `lora-forge report` | Generate dataset summary reports |
| `lora-forge status` | Show current project state |
| `lora-forge doctor` | Validate project integrity |
| `lora-forge test-openai` | Verify API key and connectivity |
| `lora-forge run` | Execute the full pipeline end-to-end |

All commands support `--dry-run` to preview without making changes.

## Export Targets

### OneTrainer (default)

```
exports/onetrainer/
  mychar_0001.jpg
  mychar_0001.txt
  mychar_0002.jpg
  mychar_0002.txt
```

### kohya_ss

```bash
lora-forge export --target kohya --repeats 20
```

```
exports/kohya/
  20_mychar woman/
    mychar_0001.jpg
    mychar_0001.txt
    mychar_0002.jpg
    mychar_0002.txt
```

### Both

```bash
lora-forge export --target all --repeats 20
```

## Caption Format

Captions use a structured format for LoRA training:

```
mychar woman, smiling, wearing a blue shirt, standing outdoors, natural lighting, medium shot
```

Every caption starts with `{trigger_token} {class_token},` followed by comma-separated descriptive tags covering pose, clothing, expression, setting, lighting, and framing.

## Supported Image Formats

- `.jpg` / `.jpeg`
- `.png`
- `.webp`

## Design Principles

- **Never modify originals** — source images and the input folder are read-only
- **Trainer-agnostic internally** — `working/` is the source of truth; exports are adapters
- **Resume over restart** — every operation is idempotent and tracked per-image
- **Cost-conscious** — discovers existing captions before calling OpenAI
- **Advisory, not prescriptive** — surfaces issues for human decision-making

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=lora_forge
```

## Tech Stack

- [typer](https://typer.tiangolo.com/) — CLI framework
- [rich](https://rich.readthedocs.io/) — terminal formatting
- [pydantic](https://docs.pydantic.dev/) — configuration validation
- [Pillow](https://pillow.readthedocs.io/) — image handling
- [piexif](https://piexif.readthedocs.io/) — JPEG EXIF stripping without recompression
- [imagehash](https://github.com/JohannesBuchner/imagehash) — perceptual hashing
- [OpenCV](https://opencv.org/) — blur and brightness quality checks
- [OpenAI Python SDK](https://github.com/openai/openai-python) — caption generation
- [pytest](https://pytest.org/) + [hypothesis](https://hypothesis.readthedocs.io/) — testing with property-based verification

## Status

**Pre-release / In Development**

The spec (requirements, design, and implementation plan) is complete. Implementation is underway.

## License

[GNU General Public License v3.0](LICENSE.md)
