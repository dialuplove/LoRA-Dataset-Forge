# Implementation Plan: LoRA Dataset Forge

## Overview

Implement a local-first Python CLI application that transforms image folders into clean, captioned, privacy-safe datasets for LoRA training. The implementation follows the three-stage file lifecycle (source → working → exports) with SQLite-backed state tracking, resume-safe processing, dry-run mode, and export adapters for OneTrainer (default) and kohya_ss.

Tasks are ordered for incremental progress: foundational modules first (config, state, project), then pipeline stages in order (init → scan → import → validate/quality → dedupe → accept → build-working → caption → lint → export → report), then cross-cutting concerns (dry-run, resume, status/doctor, testing).

## Tasks

- [ ] 1. Set up project structure and foundational modules
  - [ ] 1.1 Create Python package structure and dependencies
    - Create `src/lora_forge/` package with `__init__.py`
    - Create `pyproject.toml` with dependencies: typer, rich, pydantic, pillow, piexif, imagehash, python-dotenv, openai, numpy, opencv-python-headless
    - Create dev dependencies: pytest, hypothesis
    - Create `src/lora_forge/utils.py` with shared utilities (path helpers, rich formatting, dry-run context manager)
    - The dry-run context manager must be implemented here so all subsequent CLI commands can use it from the start; it gates file I/O, DB writes, and API calls, and prefixes output with `[DRY RUN]`
    - _Requirements: 1.1, 15.1, 15.2, 15.3, 15.4_

  - [ ] 1.2 Implement configuration module (`config.py`)
    - Define Pydantic models: `QualityConfig`, `CaptionLintConfig`, `DedupeConfig`, `ExportConfig`, `ProjectConfig`
    - Implement `caption_prefix` property on `ProjectConfig`
    - Implement `@field_validator` for `trigger_token` (non-empty, no spaces, safe chars only, not a generic class word)
    - Implement `@field_validator` for `class_token` (non-empty)
    - Implement `@model_validator` for token pair (trigger ≠ class, class_token compatible with caption_mode)
    - Define `GENERIC_CLASS_WORDS` and `CHARACTER_MODE_CLASS_TOKENS` sets
    - Define `SAFE_TOKEN_PATTERN` regex
    - Implement serialization to/from `project.json` with defaults
    - _Requirements: 1.2, 22.1, 22.2, 22.3_

  - [ ]* 1.3 Write property tests for config validation
    - **Property 21: Config Round-Trip** — serialize ProjectConfig to JSON and parse back; all fields preserved
    - **Property 23: Trigger Token Validation** — rejected if empty, has spaces, unsafe chars, generic class word, or equals class_token
    - **Validates: Requirements 1.2, 22.2**

  - [ ] 1.4 Implement state database module (`state.py`)
    - Create SQLite connection management with context manager
    - Implement schema creation (all tables: `images`, `captions`, `export_runs`, `export_items`, `conversions`, `schema_version`)
    - Implement all indexes from the design schema
    - Implement `ImageRecord` dataclass with helper methods for stage status
    - Implement query helpers: `get_images_by_stage_status`, `update_stage_status`, `record_error`
    - Implement `should_process(image, stage, force)` logic for resume-safe processing
    - _Requirements: 16.1, 16.2, 16.3, 16.4_

  - [ ] 1.5 Implement project initialization module (`project.py`)
    - Implement directory creation: `source/`, `working/`, `exports/`, `duplicates/`, `rejected/`, `reports/`
    - Implement `project.json` creation with validated `ProjectConfig`
    - Implement `forge.db` initialization via `state.py`
    - Implement `.env.example` generation with `OPENAI_API_KEY=your-key-here`
    - Implement `.gitignore` generation per requirements (ignore `.env`, `forge.db`, `source/`, `working/`, `exports/`, `duplicates/`, `rejected/`, `.DS_Store`, `Thumbs.db`, image extensions; preserve `.md`)
    - Validate that Input_Folder exists and contains supported images before creating project
    - Error if project already exists at target location
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ] 1.6 Implement CLI entry point (`cli.py`) with typer
    - Set up typer app with `lora-forge` command group
    - Wire `init` command with arguments: `input_folder`, `--name`, `--trigger`, `--class-token`
    - Add `--dry-run` global option support
    - Implement Rich console output formatting
    - _Requirements: 1.1, 15.4, 15.5_

- [ ] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Implement image scanning stage
  - [ ] 3.1 Implement scanner module (`scanner.py`)
    - Implement recursive file discovery with extension filtering (`.jpg`, `.jpeg`, `.png`, `.webp`, case-insensitive)
    - Implement directory ignore list: `.obsidian/`, `.git/`, `.kiro/`, `__MACOSX/`, `node_modules/`, `.venv/`, `venv/`, `exports/`, `working/`, `source/`, `duplicates/`, `rejected/`, `reports/`
    - Implement file ignore list: `.DS_Store`, `Thumbs.db`
    - Create Image_Records in DB with `scan_status='DISCOVERED'`, recording original filename, path, size, extension
    - Report total discovered count and skipped paths
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6_

  - [ ] 3.2 Implement metadata module (`metadata.py`)
    - Implement SHA-256 file hash computation
    - Implement perceptual hash computation using `imagehash` library (pHash)
    - Store computed hashes in Image_Record during scan
    - _Requirements: 2.5_

  - [ ] 3.3 Wire `lora-forge scan` CLI command
    - Connect scanner to CLI with dry-run support
    - Skip images already in DB on re-run (resume-safe)
    - _Requirements: 2.1, 16.2_

  - [ ]* 3.4 Write property tests for scanner
    - **Property 1: Scanner Extension Filtering** — only `.jpg`, `.jpeg`, `.png`, `.webp` returned
    - **Property 2: Scanner Directory Ignore Rules** — no files from ignored directories appear in results
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [ ] 4. Implement image import stage
  - [ ] 4.1 Implement importer module (`importer.py`)
    - Copy each DISCOVERED image from Input_Folder to `source/` preserving original filenames
    - Preserve all original metadata and file content without modification
    - Update Image_Record `import_status` to `IMPORTED` on success
    - Record error and set `import_status='FAILED'` on copy failure; continue batch
    - Skip already-IMPORTED images on subsequent runs
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ] 4.2 Wire `lora-forge import` CLI command
    - Connect importer to CLI with dry-run support
    - _Requirements: 3.1, 15.1_

  - [ ]* 4.3 Write property test for source immutability
    - **Property 3: Source Immutability Invariant** — source files remain byte-identical to input across all pipeline operations
    - **Validates: Requirements 3.1, 3.2, 9.5**

- [ ] 5. Implement validation and quality check stages
  - [ ] 5.1 Implement quality module (`quality.py`)
    - Implement image decode validation using Pillow (open and verify each IMPORTED image)
    - Record dimensions (width, height) on successful decode; set `validation_status='VALIDATED'`
    - Set `validation_status='FAILED'` with ERROR_UNREADABLE flag for corrupt/undecodable images
    - Implement quality threshold checks against `ProjectConfig` values:
      - WARN_LOW_RESOLUTION: width or height < minimum (default 512)
      - WARN_EXTREME_ASPECT: aspect ratio > maximum (default 2.5)
      - WARN_BLURRY: Laplacian variance < threshold (default 100.0)
      - WARN_DARK: mean brightness < threshold (default 35)
      - WARN_BRIGHT: mean brightness > threshold (default 220)
    - Store quality flags (comma-separated) in Image_Record
    - Set `quality_status='QUALITY_WARNING'` or `quality_status='PASS'`
    - Report summary of warnings grouped by type
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [ ] 5.2 Wire `lora-forge quality` CLI command
    - Run validation first (decode check), then quality checks on validated images
    - Support dry-run mode
    - Skip already-validated and quality-checked images on re-run
    - _Requirements: 4.1, 6.1, 16.2_

  - [ ]* 5.3 Write property test for quality flag assignment
    - **Property 15: Quality Flag Assignment** — flags assigned deterministically per thresholds
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**

- [ ] 6. Implement duplicate detection stage
  - [ ] 6.1 Implement dedupe module (`dedupe.py`)
    - Identify exact duplicates by comparing `file_hash` values across all VALIDATED images
    - Identify near-duplicates by comparing `perceptual_hash` with configurable hamming distance threshold
    - Set `dedupe_status='DUPLICATE_CANDIDATE'` and record `duplicate_of_id`, `duplicate_type`, `hamming_distance`
    - Set `dedupe_status='NO_DUPLICATE'` for non-duplicate images
    - Copy/move duplicate candidate images to `duplicates/` directory
    - Report counts of exact and near-duplicates found
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 6.2 Wire `lora-forge dedupe` CLI command
    - Connect dedupe to CLI with dry-run support
    - Skip already-deduped images on re-run
    - _Requirements: 5.1, 16.2_

  - [ ]* 6.3 Write property tests for duplicate detection
    - **Property 13: Exact Duplicate Detection** — identical SHA-256 hashes result in DUPLICATE_CANDIDATE marking
    - **Property 14: Near-Duplicate Detection** — perceptual hash distance ≤ threshold results in DUPLICATE_CANDIDATE
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [ ] 7. Implement accept/reject decision stage
  - [ ] 7.1 Implement acceptance logic (in `quality.py` or separate `acceptance.py`)
    - Auto-ACCEPT images with no quality flags and no DUPLICATE_CANDIDATE status
    - Auto-REJECT images with DUPLICATE_CANDIDATE or QUALITY_WARNING status
    - Copy REJECTED images to `rejected/` directory
    - Record acceptance decision and timestamp in Image_Record
    - Set `acceptance_status` to `ACCEPTED` or `REJECTED`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ] 7.2 Wire `lora-forge accept` CLI command
    - Connect acceptance to CLI with dry-run support
    - Skip already-decided images on re-run
    - _Requirements: 7.1, 16.2_

  - [ ]* 7.3 Write property tests for acceptance logic
    - **Property 7: Accept/Reject Decision Correctness** — no flags = ACCEPTED, flags present = REJECTED
    - **Property 8: Only Accepted Images in Working Directory** — working/ contains only ACCEPTED images
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.5**

- [ ] 8. Implement build-working stage
  - [ ] 8.1 Implement EXIF stripping module (`exif.py`)
    - Implement `strip_exif_jpeg` using piexif (zero recompression, byte-stream EXIF segment removal)
    - Implement `strip_exif_png` using Pillow (save without metadata chunks)
    - Implement `strip_exif_webp` using Pillow (re-save with `exif=b""`, lossless detection)
    - Implement unified `strip_exif(input_path, output_path)` dispatcher by extension
    - Return `ExifStripResult` with success, method, recompressed, error fields
    - Never modify input files or `source/` — always write to a separate output path
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ] 8.2 Implement renamer module (`renamer.py`)
    - Implement sequential naming: `{trigger_token}_{index:04d}.{original_extension}`
    - Assign indices starting from 1 with no gaps for new images
    - Maintain stable filenames — never renumber existing working files on re-run
    - Compute next available index from max existing `working_index` in DB
    - _Requirements: 8.1, 8.2, 8.4_

  - [ ] 8.3 Implement working module (`working.py`)
    - Select images with `acceptance_status='ACCEPTED'` and `working_status` incomplete/failed
    - Assign sequential working filenames via renamer
    - Copy accepted images from `source/` to `working/`, stripping EXIF via `exif.py`
    - Never mutate input folder or `source/`
    - Store mappings: original → source → working → caption filename
    - Set `working_status='WORKING_CREATED'` and record `working_exif_stripped`, timestamp
    - Preserve original image format (no conversion unless explicitly requested)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.5, 9.6_

  - [ ] 8.4 Wire `lora-forge build-working` CLI command
    - Connect working module to CLI with dry-run support
    - Skip images already at `working_status='WORKING_CREATED'`
    - _Requirements: 8.1, 16.2_

  - [ ]* 8.5 Write property tests for EXIF and renaming
    - **Property 4: Round-Trip Pixel Preservation** — decoded pixel data identical at each stage
    - **Property 5: JPEG EXIF Stripping Without Recompression** — JPEG scan data preserved byte-for-byte
    - **Property 6: EXIF Removal Completeness** — no EXIF metadata in working/ files
    - **Property 9: Sequential Rename Correctness** — indices 1..N, no gaps, correct pattern
    - **Property 10: Working Filename Stability** — re-run does not change existing filenames
    - **Property 11: File Mapping Completeness** — all mapping fields non-null for WORKING_CREATED images
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4**

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement captioning stage
  - [ ] 10.1 Implement caption prompts module (`captioning/prompts.py`)
    - Define `CHARACTER_CAPTION_PROMPT` template with trigger/class token placeholders
    - Implement prompt rendering with token substitution
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ] 10.2 Implement OpenAI captioner (`captioning/openai_captioner.py`)
    - Implement `OpenAICaptioner` class with API key, model, max_retries config
    - Implement `generate_caption(image_path, prompt)` — base64 encode image, call vision API
    - Implement retry with exponential backoff (2^attempt * base_delay, jitter, cap at 60s)
    - Retry on: 429, 500, 502, 503, 504
    - Implement `test_connection()` — verify API key and connectivity without sending images
    - Load API key from env → `.env` in project → `.env` in home (never log key value)
    - _Requirements: 10.2, 10.3, 10.4, 10.5, 10.9, 18.1, 18.2, 18.3, 18.4_

  - [ ] 10.3 Implement caption orchestration (`captioning/__init__.py`)
    - Only process images with `acceptance_status='ACCEPTED'` AND `working_status='WORKING_CREATED'`
    - Implement caption discovery/reuse: check for existing `.txt` beside working image before calling OpenAI
    - If valid existing caption: record as `caption_source='existing_file'`, set `caption_status='CAPTIONED'`
    - If fixable existing caption: apply local repair, record as `caption_source='repaired'`
    - If no valid caption or `--force`: call OpenAI, record as `caption_source='openai'`
    - Enforce prefix after generation: prepend if missing, deduplicate if doubled
    - Write caption to `.txt` file beside working image
    - Update `caption_status='CAPTIONED'`, set `current_caption_id` on images table
    - Support `--limit <n>` to cap images processed
    - Support `--force` to regenerate even CAPTIONED images (creates new caption record, old preserved)
    - Record: caption_source, model_name, prompt_version, generated_at, generation_status, retry_count, token_count
    - _Requirements: 10.1, 10.6, 10.7, 10.8, 10.9, 11.1, 11.4, 11.5_

  - [ ] 10.4 Wire `lora-forge caption` and `lora-forge test-openai` CLI commands
    - Connect caption orchestration to CLI with `--force`, `--limit`, `--dry-run`
    - Connect `test_connection()` to `test-openai` command
    - _Requirements: 10.1, 10.8, 18.1, 18.2, 18.3, 18.4_

  - [ ]* 10.5 Write property tests for captioning
    - **Property 12: Caption Prefix Invariant** — after enforcement, text begins with exactly one `{trigger} {class},`
    - **Property 22: Caption Discovery Prevents Duplicate API Calls** — existing valid caption = no OpenAI call
    - **Property 24: Caption Source Provenance** — caption_source is exactly one of openai/existing_file/repaired/manual
    - **Validates: Requirements 10.1, 10.6, 10.7, 11.1, 11.4, 11.5, 16.5**

- [ ] 11. Implement caption linting stage
  - [ ] 11.1 Implement linting module (`linting.py`)
    - Implement all lint rules: PREFIX_MISSING, PREFIX_TRIGGER_MISSING, PREFIX_CLASS_MISSING, PREFIX_MALFORMED, PREFIX_DUPLICATED, PREFIX_NOT_AT_START, PREFIX_COMMA_MISSING, EMPTY_CAPTION, CAPTION_TOO_SHORT, CAPTION_TOO_LONG, DUPLICATE_CAPTION, SUBJECTIVE_LANGUAGE, EXCESS_WHITESPACE
    - Implement `lint_caption()` returning `List[LintWarning]`
    - Implement `lint_and_fix()` applying safe local repairs: prepend missing prefix, remove duplicated prefix, trim whitespace, add missing comma
    - `--fix` must NOT call OpenAI, rewrite content, fix subjective language, or fix short/long captions
    - Report warnings with filename, type, and excerpt
    - Report totals grouped by warning type
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [ ] 11.2 Wire `lora-forge lint` CLI command
    - Connect linting to CLI with `--fix` and `--dry-run` support
    - _Requirements: 12.1, 12.3_

  - [ ]* 11.3 Write property test for lint fix round-trip
    - **Property 20: Lint Fix Round-Trip** — applying `--fix` then re-linting produces zero warnings for fixed issue types
    - **Validates: Requirements 12.3**

- [ ] 12. Implement export stage
  - [ ] 12.1 Implement export base adapter (`exporter/base.py`)
    - Define abstract `ExportAdapter` class with: `name`, `export_subdir`, `export()`, `validate_pre_export()`
    - Export reads ONLY from `working/` — never accesses `source/` or modifies `working/`
    - _Requirements: 13.1, 13.11_

  - [ ] 12.2 Implement OneTrainer exporter (`exporter/onetrainer.py`)
    - Create `exports/onetrainer/` with flat image + caption pairs
    - Sequential filenames without gaps, EXIF stripped on all exported images
    - No repeats folder wrapper
    - _Requirements: 13.2, 13.3, 13.6_

  - [ ] 12.3 Implement Kohya exporter (`exporter/kohya.py`)
    - Create `exports/kohya/{repeats}_{trigger_token} {class_token}/` directory
    - Copy image + caption pairs with sequential filenames, EXIF stripped
    - Use default repeats from ProjectConfig (default: 20) when `--repeats` not specified
    - _Requirements: 13.4, 13.6, 13.10_

  - [ ] 12.4 Implement adapter registry and export orchestration (`exporter/__init__.py`)
    - Register adapters: `onetrainer`, `kohya`
    - Implement `get_adapter(target)` factory
    - Implement `export_all()` for `--target all`
    - Validate pre-export: fail if any accepted working image lacks a caption (unless `--allow-missing-captions`)
    - Record `export_runs` and `export_items` in DB per target and per image; export state lives in these tables, not on the `images` row
    - _Requirements: 13.1, 13.5, 13.7, 13.8, 13.9_

  - [ ] 12.5 Wire `lora-forge export` CLI command
    - Connect export orchestration to CLI with `--target`, `--repeats`, `--allow-missing-captions`, `--dry-run`
    - Default target: `onetrainer`
    - _Requirements: 13.1, 13.2_

  - [ ]* 12.6 Write property tests for export structure
    - **Property 18: OneTrainer Export Structure** — flat directory with 2N files (N images + N captions)
    - **Property 19: Kohya Export Structure** — single `{R}_{T} {C}/` folder with 2N files
    - **Validates: Requirements 13.3, 13.4**

- [ ] 13. Implement reporting stage
  - [ ] 13.1 Implement reporting module (`reporting.py`)
    - Generate `reports/report.md` with Markdown formatting
    - Generate `reports/report.json` with valid JSON
    - Include all required metrics: files scanned, imported, source retained, working created, accepted, rejected, exact/near duplicates, EXIF stripped, quality warnings by type, captions generated/missing, lint warnings, model used, prompt version, thresholds, export paths/targets/completeness
    - Include timestamps for report generation and last completed stage
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ] 13.2 Wire `lora-forge report` CLI command
    - Connect reporting to CLI with dry-run support
    - _Requirements: 14.1_

- [ ] 14. Implement cross-cutting concerns
  - [ ] 14.1 Audit and harden dry-run mode across all commands
    - Verify the dry-run context (implemented in 1.1) is correctly applied in every CLI command
    - Ensure no command bypasses the context for file I/O, DB writes, or API calls
    - For `init --dry-run`: display project structure that would be created
    - Add integration test confirming `[DRY RUN]` prefix on all output lines
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

  - [ ] 14.2 Implement status command
    - Query DB for project summary: name, source folder, counts by stage status
    - Report: scanned, imported, accepted, rejected, working, duplicate, quality warning, captioned, missing caption, export status, last stage
    - Error if no project found in current directory
    - _Requirements: 19.1, 19.2_

  - [ ] 14.3 Implement doctor command
    - Verify `project.json` exists and is valid
    - Verify `forge.db` exists and accessible
    - Verify `source/` files match IMPORTED records
    - Verify `working/` files match ACCEPTED/WORKING_CREATED records
    - Verify caption files exist for CAPTIONED images
    - Verify export directory completeness if export recorded
    - Verify OpenAI API key available if captioning incomplete
    - Report issues with descriptions and suggested repairs
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8_

  - [ ] 14.4 Implement pipeline command (`lora-forge run`)
    - Execute full pipeline in order: init → scan → import → quality → dedupe → accept → build-working → caption → lint → export → report
    - Accept all required arguments: input_folder, --name, --trigger, --class-token, --repeats, --target
    - Default target: `onetrainer`
    - Stop on unrecoverable errors, report failure, record state for resume
    - Support `--dry-run` applying to all stages
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

  - [ ] 14.5 Wire `lora-forge status`, `lora-forge doctor`, and `lora-forge run` CLI commands
    - Connect all remaining commands to typer CLI
    - _Requirements: 17.1, 19.1, 20.1_

  - [ ]* 14.6 Write property tests for dry-run and resume
    - **Property 16: Dry-Run Side-Effect Freedom** — no filesystem changes, no DB changes, no API calls
    - **Property 17: Resume Skip-on-Success** — re-run skips already-completed images
    - **Validates: Requirements 15.1, 15.2, 15.3, 16.2, 16.5**

- [ ] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` include property-based tests. The following are **required guardrails** and must not be skipped: 1.3 (config/token validation), 3.4 (scanner), 4.3 (source immutability), 8.5 (EXIF/rename), 10.5 (caption reuse), 12.6 (export structure), 14.6 (dry-run/resume). Tasks 5.3, 6.3, 7.3, and 11.3 may be deferred if needed for velocity but are strongly recommended.
- The dry-run context is built in task 1.1 and enforced incrementally from the first CLI command onward; task 14.1 is the final audit pass.
- Export state is tracked in `export_runs` and `export_items` tables, not on the `images` row. `lifecycle_state` on images is derived/display only.
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- All OpenAI API tests use mocked responses — no live API key required for testing
- The implementation language is Python throughout (Pydantic, typer, Pillow, piexif, imagehash, hypothesis)
- OneTrainer is the default export target; kohya_ss is secondary
- `working/` is the trainer-agnostic source of truth; export adapters never influence internal structure
- EXIF stripping never mutates input files or `source/` — always writes to a separate output path
- Per-stage status columns (scan_status, import_status, etc.) drive resume logic — not a single status field

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.4"] },
    { "id": 2, "tasks": ["1.3", "1.5"] },
    { "id": 3, "tasks": ["1.6"] },
    { "id": 4, "tasks": ["3.1", "3.2"] },
    { "id": 5, "tasks": ["3.3", "3.4"] },
    { "id": 6, "tasks": ["4.1"] },
    { "id": 7, "tasks": ["4.2", "4.3"] },
    { "id": 8, "tasks": ["5.1"] },
    { "id": 9, "tasks": ["5.2", "5.3"] },
    { "id": 10, "tasks": ["6.1"] },
    { "id": 11, "tasks": ["6.2", "6.3"] },
    { "id": 12, "tasks": ["7.1"] },
    { "id": 13, "tasks": ["7.2", "7.3"] },
    { "id": 14, "tasks": ["8.1", "8.2"] },
    { "id": 15, "tasks": ["8.3"] },
    { "id": 16, "tasks": ["8.4", "8.5"] },
    { "id": 17, "tasks": ["10.1", "10.2"] },
    { "id": 18, "tasks": ["10.3"] },
    { "id": 19, "tasks": ["10.4", "10.5"] },
    { "id": 20, "tasks": ["11.1"] },
    { "id": 21, "tasks": ["11.2", "11.3"] },
    { "id": 22, "tasks": ["12.1"] },
    { "id": 23, "tasks": ["12.2", "12.3"] },
    { "id": 24, "tasks": ["12.4"] },
    { "id": 25, "tasks": ["12.5", "12.6"] },
    { "id": 26, "tasks": ["13.1"] },
    { "id": 27, "tasks": ["13.2"] },
    { "id": 28, "tasks": ["14.1", "14.2", "14.3"] },
    { "id": 29, "tasks": ["14.4"] },
    { "id": 30, "tasks": ["14.5", "14.6"] }
  ]
}
```
