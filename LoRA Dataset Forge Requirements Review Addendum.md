
# LoRA Dataset Forge Requirements Review Addendum

## Status

The original Kiro-generated requirements document is close, but it should not be accepted until the following revisions are incorporated.

This addendum records accepted architecture decisions, corrections, and deferred topics.

---

# 1. Source / Working / Export Folder Lifecycle

The application should use a clear three-stage file lifecycle.

```text
Original input folder
  ↓ copy
project/source/
  ↓ validate, accept/reject, rename, strip EXIF
project/working/
  ↓ export
project/exports/kohya/{repeats}_{trigger_token} {class_token}/
```

## Folder Responsibilities

### `source/`

The `source/` directory is a local immutable copy of the original input images.

- Files in `source/` should preserve original filenames.
- Files in `source/` should preserve original metadata.
- Files in `source/` should not be modified, renamed, moved, compressed, or stripped.
- `source/` exists for traceability and recovery.

### `working/`

The `working/` directory is the active dataset preparation directory.

Images in `working/` should be:

- Accepted for processing
- Renamed sequentially
- EXIF-stripped
- Privacy-safe
- Paired with matching `.txt` caption files after captioning

Example:

```text
working/
  dawivre_0001.jpg
  dawivre_0001.txt
  dawivre_0002.jpg
  dawivre_0002.txt
```

### `exports/`

The `exports/` directory contains final exported training datasets.

For kohya_ss, the export structure should be:

```text
exports/
  kohya/
    20_dawivre woman/
      dawivre_0001.jpg
      dawivre_0001.txt
      dawivre_0002.jpg
      dawivre_0002.txt
```

---

# 2. Remove Separate `captions/` Directory from MVP

The MVP should not use a separate `captions/` directory.

Reason:

kohya_ss expects images and corresponding caption `.txt` files to live in the same directory. Since LoRA Dataset Forge already creates sequentially renamed working images, the matching caption file should live beside the image in `working/`.

Example:

```text
working/
  dawivre_0001.jpg
  dawivre_0001.txt
```

This keeps the pipeline simple, inspectable, and compatible with kohya-style dataset expectations.

Caption history/versioning may be added later, but should not be included in the MVP unless needed.

---

# 3. Accepted / Rejected Phase Must Happen Before Captioning

The application should not caption images that may later be rejected.

Caption generation uses paid API calls and should happen only after the application has determined which images are eligible for the dataset.

The corrected pipeline should be:

```text
init
scan
import to source/
validate
dedupe
quality checks
accepted/rejected decision phase
create working/ images
rename working/ images
strip EXIF from working/ images
caption accepted working images
lint captions
export
report
```

The phrase “accepted image” must be operationally defined before captioning.

Recommended image state model:

```text
DISCOVERED
IMPORTED
VALIDATED
DUPLICATE_CANDIDATE
QUALITY_WARNING
ACCEPTED
REJECTED
WORKING_CREATED
CAPTIONED
EXPORTED
FAILED
```

The app may also use per-stage statuses in the database:

```text
scan_status
import_status
validation_status
dedupe_status
quality_status
acceptance_status
working_status
caption_status
export_status
```

Captioning should run only against images with an acceptance status of `ACCEPTED`.

---

# 4. Sequential Renaming Behavior

Sequential renaming should happen when accepted images are copied into `working/`.

The application should not rename source images.

The `working/` directory should use stable sequential filenames.

Example:

```text
working/
  dawivre_0001.jpg
  dawivre_0002.jpg
  dawivre_0003.jpg
```

The application should store a traceable mapping:

```json
{
  "original_filename": "IMG_3847.JPG",
  "source_filename": "IMG_3847.JPG",
  "working_filename": "dawivre_0001.jpg",
  "caption_filename": "dawivre_0001.txt"
}
```

## No-Gap Rule

The final exported dataset should contain sequential filenames without gaps.

Working filenames should remain stable once assigned. The app should avoid renumbering existing working files unless an explicit rebuild command is introduced later.

Corrected rule:

```text
The Forge SHALL maintain stable working filenames once assigned. The kohya export SHALL contain sequential filenames without gaps for exported accepted images.
```

---

# 5. EXIF Metadata Stripping

Privacy is a core requirement.

The source copy should remain intact.

EXIF stripping should apply to:

- `working/` images
- `exports/` images

EXIF stripping should not apply to:

- original input folder
- `source/` copies

Corrected requirement:

```text
THE Forge SHALL strip metadata from working and exported images while preserving image dimensions and visual content. THE Forge SHALL avoid unnecessary recompression where technically feasible and SHALL document any format conversion or resave behavior.
```

The application should specifically remove:

- GPS metadata
- Camera metadata
- Device metadata
- Original timestamp metadata
- Embedded EXIF fields

---

# 6. OpenAI Captioning Requirements

Caption generation should be specific enough for implementation.

The app should:

- Load the OpenAI API key from `.env` or environment variables
- Never log or display the API key
- Support a configurable OpenAI vision-capable model name in `project.json`
- Resize or encode images for API submission without modifying local `working/` images
- Use retry logic with exponential backoff for transient errors and rate limits
- Record caption model, prompt version, timestamp, and generation status for each caption
- Skip already-captioned images unless `--force` is used
- Support `--limit <n>` for test runs
- Avoid sending any user images during `test-openai`

Each caption should be written beside its matching image:

```text
working/dawivre_0001.jpg
working/dawivre_0001.txt
```

---

# 7. Trigger and Class Token Enforcement

Every caption must begin with:

```text
{trigger_token} {class_token},
```

Example:

```text
dawivre woman, smiling, wearing a blue shirt, standing outdoors, natural lighting, medium shot
```

The app should:

- Automatically prepend the prefix if missing
- Avoid duplicated prefixes
- Support multi-word class tokens if needed
- Lint captions for missing or malformed prefixes

---

# 8. Format Preservation and Optional Conversion

The MVP should preserve original supported image formats unless a conversion switch is explicitly provided.

Supported MVP formats:

```text
.jpg
.jpeg
.png
.webp
```

Default behavior:

```text
Preserve original supported format.
```

Optional future or MVP switch:

```bash
lora-forge export --convert jpg
```

or:

```bash
lora-forge working-build --convert jpg
```

Conversion should never modify `source/`.

If conversion is used, the app should record:

- Original format
- Converted format
- Conversion timestamp
- Conversion settings

---

# 9. Dry-Run Requirements

Dry-run mode should apply to all commands.

In dry-run mode, the app should not:

- Create directories
- Create files
- Modify files
- Move files
- Delete files
- Write database records
- Make OpenAI API calls

For `init --dry-run`, the app should validate the input and display the project structure and configuration that would be created.

All dry-run output should be prefixed with:

```text
[DRY RUN]
```

---

# 10. Recursive Scan Ignore Rules

The recursive scanner must avoid self-ingestion and project clutter.

The scanner should ignore:

```text
.obsidian/
.git/
.kiro/
__MACOSX/
.DS_Store
Thumbs.db
node_modules/
.venv/
venv/
exports/
working/
source/
duplicates/
rejected/
reports/
```

Important note:

This project is also being used as an Obsidian project folder. The `.obsidian/` folder must be ignored.

Markdown files in the project root should not be ignored globally because project documentation may live there, including:

```text
README.md
LICENSE
original Kiro prompt markdown files
requirements notes
architecture notes
implementation notes
```

The scanner should only scan supported image formats and should not treat project Markdown files as image inputs.

---

# 11. Configuration Defaults

The app should define configurable defaults in `project.json`.

Recommended schema:

```json
{
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
    "preserve_format": true,
    "convert_format": null
  }
}
```

These values may be changed later, but the configuration surface should exist.

---

# 12. Caption Linting and Repair

Caption linting should check for:

- Missing trigger token
- Missing class token
- Missing required caption prefix
- Duplicated caption prefix
- Empty caption
- Caption too short
- Caption too long
- Duplicate captions across multiple files
- Subjective language
- Unsupported or overly poetic phrasing

The app may support:

```bash
lora-forge lint --fix
```

For MVP, `--fix` may be limited to:

- Prepending missing prefix
- Removing duplicated prefix
- Trimming whitespace

---

# 13. Export Strictness

By default, export should fail if accepted working images are missing valid captions.

Reason:

A kohya_ss export should be complete and training-ready.

Default behavior:

```text
If any accepted Working_Image lacks a valid Caption_File, export SHALL fail and report the missing files.
```

Optional override:

```bash
lora-forge export --allow-missing-captions
```

This override may be deferred if not needed in MVP.

---

# 14. Report Improvements

The report should include:

- Total files scanned
- Total images imported
- Source images retained
- Working images created
- Accepted image count
- Rejected image count
- Duplicate candidate count
- Near-duplicate candidate count
- Images with EXIF stripped
- Quality warning counts by type
- Captions generated
- Captions missing
- Caption lint warning count
- Caption model used
- Caption prompt version
- Quality thresholds used
- Dedupe threshold used
- Export path
- kohya_ss folder name
- Export completeness status

Reports should be generated as:

```text
reports/report.md
reports/report.json
```

---

# 15. Resume and Failure Tracking

The state database should track per-stage processing status.

For failed stages, the app should record:

- Failed stage
- Last error message
- Retry count
- Last attempted timestamp

When a stage is re-run:

- Previously successful images should be skipped
- Failed images should be retried
- Existing captions should not be regenerated unless `--force` is used

---

# 16. Status Command

Add:

```bash
lora-forge status
```

The status command should show:

```text
Project name
Source folder
Scanned image count
Imported image count
Accepted image count
Rejected image count
Working image count
Duplicate candidates
Quality warnings
Captioned images
Missing captions
Export status
Last completed stage
```

This is necessary for resumability and usability.

---

# 17. Doctor / Integrity Check Command

Add:

```bash
lora-forge doctor
```

The doctor command should validate project integrity.

It should check:

- `project.json` exists
- `forge.db` exists
- `source/` files match database records
- `working/` files match accepted records
- `.txt` caption files match working images
- export folder is complete if export has been run
- OpenAI key is available if captioning is required
- no obvious broken mappings exist

If problems are found, the app should report each issue with a suggested repair action.

---

# 18. `.gitignore` and Project Hygiene

The app should generate a safe `.gitignore`.

Recommended `.gitignore` entries:

```gitignore
.env
forge.db
source/
working/
exports/
duplicates/
rejected/
*.jpg
*.jpeg
*.png
*.webp
*.heic
*.tiff
*.bmp
.DS_Store
Thumbs.db
```

Do not ignore:

```text
README.md
LICENSE
*.md
```

Reason:

Markdown files are part of the project documentation workflow and may be intentionally stored in the project root for Obsidian, Kiro, Codex, and human review.

The app should ignore `.obsidian/` during image scanning, but the repository does not necessarily need to ignore `.obsidian/` unless the user chooses to.

---

# 19. Deferred Topic: Human Review Without GUI

Human review is important, but the MVP requirements should not force a poor CLI review experience before the workflow is stable.

The topic is deferred for later review.

Open question:

```text
What is the best human review mechanism for LoRA Dataset Forge before building a full GUI?
```

Potential future approaches:

```text
1. Simple CLI list/accept/reject commands
2. Generated HTML contact sheet report
3. Local FastAPI review interface
4. Streamlit/Gradio review UI
5. Open working folder in the OS file explorer and use file moves as signals
6. CSV/Markdown review manifest edited manually
```

Do not finalize this yet.

Do not generate a new Kiro prompt until this topic is revisited.

---

# 20. Current Acceptance Decision

Do not accept the current Kiro requirements document as final.

Accept the direction, but require revision around:

- `source/` / `working/` / `exports/` lifecycle
- removal of separate `captions/` directory
- accepted/rejected state before captioning
- source image integrity
- EXIF stripping behavior
- stable working filenames and no-gap export filenames
- OpenAI model, prompt, retry, and metadata handling
- format preservation unless explicit conversion is requested
- dry-run behavior
- recursive scan ignore rules, especially `.obsidian/`
- status command
- doctor command
- report completeness
- resume/failure tracking
- export strictness
- project hygiene and `.gitignore`

Human review without a GUI remains unresolved and should be discussed before generating the next Kiro revision prompt.