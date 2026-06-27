# Requirements Document

## Introduction

LoRA Dataset Forge is a local-first Python CLI application that prepares image datasets for training LoRAs with kohya_ss. The application reads a folder of images, imports them into a managed project workspace, detects duplicates and quality issues, strips EXIF metadata for privacy, generates captions using OpenAI vision models, enforces trigger/class token conventions, lints captions, and exports the finished dataset in a kohya_ss-compatible folder structure. The application uses a three-stage file lifecycle (source → working → exports) and supports resume-safe processing, dry-run mode, and comprehensive reporting.

## Glossary

- **Forge**: The LoRA Dataset Forge application, invoked via the `lora-forge` CLI command
- **Project**: A managed workspace directory containing all project state, configuration, images, and exports for a single LoRA dataset
- **Source_Directory**: The `source/` folder within a Project that holds immutable copies of original input images with original filenames and metadata preserved
- **Working_Directory**: The `working/` folder within a Project that holds accepted, renamed, EXIF-stripped images paired with `.txt` caption files
- **Export_Directory**: The `exports/` folder within a Project that holds final kohya_ss-compatible dataset output
- **Input_Folder**: The user's original folder of images provided during project initialization; never modified by the Forge
- **Project_Config**: The `project.json` file that stores project settings, quality thresholds, caption lint limits, dedupe thresholds, and export configuration
- **State_Database**: The `forge.db` SQLite database that tracks per-image processing status, mappings, errors, and retry counts
- **Image_Record**: A database entry tracking one image through all processing stages
- **Trigger_Token**: A unique identifier word used as the LoRA activation token in captions (e.g., "dawivre")
- **Class_Token**: A word describing the subject class for LoRA training (e.g., "woman", "man", "style")
- **Caption_Prefix**: The string `{trigger_token} {class_token},` that must begin every caption
- **Caption_File**: A `.txt` file containing the caption text, named identically to its paired image (different extension)
- **Working_Image**: An accepted image that has been copied to Working_Directory with sequential naming and EXIF stripped
- **Perceptual_Hash**: A hash derived from image visual content using the imagehash library, used for near-duplicate detection
- **File_Hash**: A cryptographic hash (SHA-256) of a file's byte content, used for exact duplicate detection
- **kohya_ss**: A popular LoRA training framework that expects datasets in a specific folder structure: `{repeats}_{token} {class}/` containing paired image and caption files
- **OneTrainer**: A LoRA training application that expects datasets as flat directories containing paired image and caption files without a repeats folder wrapper
- **Export_Profile**: A named export target format (onetrainer, kohya, or all) that determines folder structure conventions for the Export_Directory
- **Repeats**: The number of times kohya_ss repeats each image during training, encoded in the kohya export folder name
- **Dry_Run**: A mode where the Forge reports planned actions without creating, modifying, or deleting any files, directories, database records, or making API calls
- **Scanner**: The component that recursively discovers supported image files in the Input_Folder
- **Quality_Check**: An automated assessment of image properties (resolution, aspect ratio, blur, brightness, corruption)
- **Caption_Lint**: An automated check of caption text for structural and content issues

## Requirements

### Requirement 1: Project Initialization

**User Story:** As a LoRA trainer, I want to initialize a dataset project from an image folder, so that I have a managed workspace for preparing my training data.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge init <input_folder> --name <project_name> --trigger <trigger_token> --class-token <class_token>`, THE Forge SHALL create a Project directory containing `project.json`, `forge.db`, and subdirectories `source/`, `working/`, `exports/`, `duplicates/`, `rejected/`, and `reports/`
2. THE Forge SHALL generate a Project_Config file with the provided project name, trigger token, class token, source folder path, creation timestamp, and configurable defaults for quality thresholds, caption lint limits, dedupe threshold, and export settings
3. THE Forge SHALL generate a `.env.example` file containing a placeholder entry for the OpenAI API key
4. THE Forge SHALL generate a `.gitignore` file that ignores `.env`, `forge.db`, `source/`, `working/`, `exports/`, `duplicates/`, `rejected/`, `.DS_Store`, `Thumbs.db`, and image file extensions (`.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`, `.tiff`, `.bmp`) while preserving `.md` files
5. IF the specified Input_Folder does not exist or contains no supported image files, THEN THE Forge SHALL report an error and abort initialization
6. IF a Project already exists at the target location, THEN THE Forge SHALL report a conflict error and abort without overwriting

### Requirement 2: Image Scanning

**User Story:** As a LoRA trainer, I want to scan my image folder recursively, so that the application discovers all candidate images for the dataset.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge scan`, THE Scanner SHALL recursively discover all files with extensions `.jpg`, `.jpeg`, `.png`, or `.webp` (case-insensitive) in the configured Input_Folder
2. THE Scanner SHALL ignore directories named `.obsidian/`, `.git/`, `.kiro/`, `__MACOSX/`, `node_modules/`, `.venv/`, `venv/`, `exports/`, `working/`, `source/`, `duplicates/`, `rejected/`, and `reports/`
3. THE Scanner SHALL ignore files named `.DS_Store` and `Thumbs.db`
4. WHEN a supported image file is discovered, THE Forge SHALL create an Image_Record in the State_Database with status DISCOVERED, recording original filename, original path, file size, and file extension
5. THE Forge SHALL compute and store a File_Hash and Perceptual_Hash for each discovered image
6. THE Forge SHALL report the total count of discovered images and any skipped paths upon completion

### Requirement 3: Image Import to Source

**User Story:** As a LoRA trainer, I want to import discovered images into the project workspace, so that I have a local immutable copy for traceability and recovery.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge import`, THE Forge SHALL copy each DISCOVERED image from the Input_Folder into the Source_Directory preserving original filenames
2. THE Forge SHALL preserve all original metadata and file content in the Source_Directory copy without modification
3. WHEN an image is successfully copied, THE Forge SHALL update the Image_Record status to IMPORTED
4. IF a file copy fails, THEN THE Forge SHALL record the error in the Image_Record, set the status to FAILED, and continue processing remaining images
5. THE Forge SHALL skip images that have already been successfully imported on subsequent runs

### Requirement 4: Image Validation

**User Story:** As a LoRA trainer, I want imported images validated for readability, so that corrupt or unreadable files are identified early.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge quality` (or during the pipeline), THE Forge SHALL attempt to open and decode each IMPORTED image using Pillow
2. WHEN an image is successfully decoded, THE Forge SHALL record its dimensions (width and height) and update the Image_Record status to VALIDATED
3. IF an image cannot be decoded or is corrupt, THEN THE Forge SHALL update the Image_Record status to FAILED with an ERROR_UNREADABLE quality flag and record the error message

### Requirement 5: Duplicate Detection

**User Story:** As a LoRA trainer, I want exact and near-duplicate images detected, so that I can remove redundant training data.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge dedupe`, THE Forge SHALL identify exact duplicates by comparing File_Hash values across all VALIDATED images
2. THE Forge SHALL identify near-duplicates by comparing Perceptual_Hash values with a configurable hamming distance threshold (default: 10) stored in Project_Config
3. WHEN an image is identified as an exact duplicate of another image, THE Forge SHALL update the Image_Record status to DUPLICATE_CANDIDATE and record which image it duplicates
4. WHEN an image is identified as a near-duplicate, THE Forge SHALL update the Image_Record status to DUPLICATE_CANDIDATE and record the hamming distance and reference image
5. THE Forge SHALL copy or move duplicate candidate images to the `duplicates/` directory for user review
6. THE Forge SHALL report the count of exact duplicates and near-duplicates found

### Requirement 6: Quality Checks

**User Story:** As a LoRA trainer, I want basic quality assessments performed on my images, so that I can identify low-quality training data before investing in captioning.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge quality`, THE Forge SHALL check each VALIDATED (non-duplicate) image against configurable quality thresholds defined in Project_Config
2. THE Forge SHALL flag images with width or height below the configured minimum (default: 512px) as WARN_LOW_RESOLUTION
3. THE Forge SHALL flag images with aspect ratio exceeding the configured maximum (default: 2.5) as WARN_EXTREME_ASPECT
4. THE Forge SHALL flag images with a Laplacian variance below the configured blur threshold (default: 100.0) as WARN_BLURRY
5. THE Forge SHALL flag images with mean brightness below the configured dark threshold (default: 35) as WARN_DARK
6. THE Forge SHALL flag images with mean brightness above the configured bright threshold (default: 220) as WARN_BRIGHT
7. WHEN quality warnings are found, THE Forge SHALL update the Image_Record status to QUALITY_WARNING and record all applicable warning flags
8. THE Forge SHALL report a summary of quality warning counts grouped by warning type

### Requirement 7: Accept/Reject Decision

**User Story:** As a LoRA trainer, I want to accept or reject images before captioning, so that I do not waste API calls on images I will not use.

#### Acceptance Criteria

1. THE Forge SHALL provide a mechanism to mark images as ACCEPTED or REJECTED based on duplicate and quality assessment results
2. WHEN an image has no duplicate flags and no quality warnings, THE Forge SHALL mark it as ACCEPTED by default
3. WHEN an image has DUPLICATE_CANDIDATE or QUALITY_WARNING status, THE Forge SHALL mark it as REJECTED by default
4. THE Forge SHALL copy REJECTED images to the `rejected/` directory for user reference
5. THE Forge SHALL proceed to Working_Directory creation only for images with ACCEPTED status
6. THE Forge SHALL record the acceptance decision and timestamp in each Image_Record

### Requirement 8: Working Directory Creation and Sequential Renaming

**User Story:** As a LoRA trainer, I want accepted images copied to a working directory with sequential filenames, so that my dataset has consistent, predictable naming.

#### Acceptance Criteria

1. WHEN images are ACCEPTED, THE Forge SHALL copy each accepted image from Source_Directory to Working_Directory with a sequential filename following the pattern `{trigger_token}_{index:04d}.{original_extension}`
2. THE Forge SHALL assign sequential indices starting from 1 with no gaps for newly accepted images
3. THE Forge SHALL preserve the original supported image format unless explicit conversion is requested via a `--convert` flag
4. THE Forge SHALL maintain stable Working_Directory filenames once assigned and not renumber existing files on subsequent runs
5. THE Forge SHALL store the mapping between original filename, source filename, working filename, and caption filename in the State_Database
6. WHEN working images are created, THE Forge SHALL update Image_Record status to WORKING_CREATED

### Requirement 9: EXIF Metadata Stripping

**User Story:** As a LoRA trainer, I want EXIF metadata stripped from working and exported images, so that my dataset does not leak private location, device, or timestamp information.

#### Acceptance Criteria

1. THE Forge SHALL strip all EXIF metadata (GPS, camera, device, timestamp, and embedded EXIF fields) from images when copying them to Working_Directory
2. THE Forge SHALL strip all EXIF metadata from images when copying them to Export_Directory
3. THE Forge SHALL preserve image dimensions and visual content during EXIF stripping
4. THE Forge SHALL avoid unnecessary recompression where technically feasible during EXIF removal
5. THE Forge SHALL not modify images in Source_Directory or the original Input_Folder
6. THE Forge SHALL record EXIF stripping status in each Image_Record

### Requirement 10: OpenAI Caption Generation

**User Story:** As a LoRA trainer, I want AI-generated captions for my accepted images, so that I have consistent, training-ready text descriptions without manual work.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge caption`, THE Forge SHALL generate a caption for each Working_Image that does not already have a Caption_File (unless `--force` is specified)
2. THE Forge SHALL load the OpenAI API key from environment variables or a `.env` file and never log or display the key value
3. THE Forge SHALL use the vision-capable model name configured in Project_Config to generate captions from image content
4. THE Forge SHALL encode images for API submission without modifying the local Working_Image files
5. THE Forge SHALL implement retry logic with exponential backoff for transient API errors and rate limit responses
6. WHEN a caption is successfully generated, THE Forge SHALL write it to a Caption_File beside the Working_Image and update Image_Record status to CAPTIONED
7. THE Forge SHALL record the caption model name, prompt version, generation timestamp, and generation status for each caption in the State_Database
8. WHEN `--limit <n>` is specified, THE Forge SHALL generate captions for at most n uncaptioned images and then stop
9. IF an API call fails after retries, THEN THE Forge SHALL record the error in the Image_Record, increment the retry count, and continue processing remaining images

### Requirement 11: Caption Content and Token Enforcement

**User Story:** As a LoRA trainer, I want every caption to include my trigger token and class token as a prefix, so that kohya_ss correctly associates captions with my LoRA subject.

#### Acceptance Criteria

1. THE Forge SHALL ensure every generated caption begins with the Caption_Prefix `{trigger_token} {class_token},` followed by descriptive comma-separated tags
2. THE Forge SHALL generate captions in character mode describing: pose, clothing, expression, setting, lighting, and camera angle or framing when obvious
3. THE Forge SHALL avoid generating poetic descriptions, overly subjective language, identity guesses, sensitive attribute assumptions, and private metadata references in captions
4. IF a caption does not include the required Caption_Prefix, THEN THE Forge SHALL prepend it automatically
5. IF a caption contains a duplicated Caption_Prefix, THEN THE Forge SHALL remove the duplication

### Requirement 12: Caption Linting

**User Story:** As a LoRA trainer, I want my captions checked for common issues, so that I catch formatting problems before export.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge lint`, THE Forge SHALL check each Caption_File in Working_Directory against the following rules: missing trigger token, missing class token, missing Caption_Prefix, duplicated Caption_Prefix, empty caption, caption shorter than the configured minimum (default: 20 characters), caption longer than the configured maximum (default: 220 characters), duplicate caption text across multiple files, and subjective or overly poetic language
2. THE Forge SHALL report each lint warning with the affected filename, warning type, and relevant excerpt
3. WHEN `--fix` is specified, THE Forge SHALL apply automatic repairs limited to: prepending missing prefix, removing duplicated prefix, and trimming whitespace
4. THE Forge SHALL report the total count of lint warnings grouped by warning type

### Requirement 13: Export Profiles

**User Story:** As a LoRA trainer, I want to export my prepared dataset in multiple trainer-compatible formats, so that I can use it with OneTrainer, kohya_ss, or both.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge export --target <target>`, THE Forge SHALL export the dataset using the specified target profile where valid targets are `onetrainer`, `kohya`, or `all`
2. THE Forge SHALL use `onetrainer` as the default export target when `--target` is not specified
3. WHEN target is `onetrainer`, THE Forge SHALL create `exports/onetrainer/` containing paired image and Caption_File for each CAPTIONED Working_Image with sequential filenames and no repeats folder wrapper
4. WHEN target is `kohya`, THE Forge SHALL create `exports/kohya/{repeats}_{trigger_token} {class_token}/` containing paired image and Caption_File for each CAPTIONED Working_Image
5. WHEN target is `all`, THE Forge SHALL produce both the `onetrainer` and `kohya` export structures
6. THE Forge SHALL export images with EXIF stripped and sequential filenames without gaps
7. IF any ACCEPTED Working_Image lacks a valid Caption_File, THEN THE Forge SHALL fail the export and report the files with missing captions
8. WHEN `--allow-missing-captions` is specified, THE Forge SHALL export even if some images lack captions, skipping those without captions
9. THE Forge SHALL update Image_Record status to EXPORTED for each successfully exported image
10. THE Forge SHALL use a default repeat count from Project_Config (default: 20) when `--repeats` is not specified for the `kohya` target
11. THE Forge SHALL treat the Working_Directory as the trainer-agnostic source of truth; export profiles SHALL NOT influence the internal project structure

### Requirement 14: Report Generation

**User Story:** As a LoRA trainer, I want comprehensive reports about my dataset, so that I can review the preparation results and share them.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge report`, THE Forge SHALL generate `reports/report.md` and `reports/report.json` containing: total files scanned, total images imported, source images retained, working images created, accepted count, rejected count, exact duplicate count, near-duplicate count, images with EXIF stripped, quality warning counts by type, captions generated, captions missing, caption lint warning count, caption model used, caption prompt version, quality thresholds used, dedupe threshold used, export path(s), export target(s) used, and export completeness status
2. THE Forge SHALL produce valid Markdown formatting in `report.md` and valid JSON in `report.json`
3. THE Forge SHALL include timestamps for report generation and last completed pipeline stage

### Requirement 15: Dry-Run Mode

**User Story:** As a LoRA trainer, I want a dry-run mode for every command, so that I can preview what changes will be made before committing to them.

#### Acceptance Criteria

1. WHEN `--dry-run` is specified on any command, THE Forge SHALL not create, modify, or delete any files or directories
2. WHILE in Dry_Run mode, THE Forge SHALL not write to the State_Database
3. WHILE in Dry_Run mode, THE Forge SHALL not make OpenAI API calls
4. WHILE in Dry_Run mode, THE Forge SHALL prefix all output lines describing planned actions with `[DRY RUN]`
5. WHEN `init --dry-run` is used, THE Forge SHALL display the project structure and configuration that would be created without creating any files

### Requirement 16: Resume and Failure Tracking

**User Story:** As a LoRA trainer, I want the application to resume where it left off after interruptions, so that I do not repeat expensive operations.

#### Acceptance Criteria

1. THE Forge SHALL track per-image processing status across stages (scan, import, validation, dedupe, quality, acceptance, working, caption, export) in the State_Database
2. WHEN a command is re-run, THE Forge SHALL skip images that have already completed the current stage successfully
3. WHEN a stage fails for an image, THE Forge SHALL record the failed stage, last error message, retry count, and last attempted timestamp in the Image_Record
4. WHEN a previously failed image is retried, THE Forge SHALL increment the retry count and attempt processing again
5. THE Forge SHALL not regenerate existing captions unless `--force` is specified

### Requirement 17: Pipeline Command

**User Story:** As a LoRA trainer, I want a single command to run the entire preparation pipeline, so that I can process a dataset end-to-end with minimal interaction.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge run <input_folder> --name <project_name> --trigger <trigger_token> --class-token <class_token> --repeats <n> --target <target>`, THE Forge SHALL execute the full pipeline in order: init, scan, import, quality (including validation and dedupe), accept/reject, working directory creation (rename and EXIF strip), caption, lint, export, and report
2. IF any stage fails with unrecoverable errors, THEN THE Forge SHALL stop the pipeline, report the failure, and record state for future resume
3. THE Forge SHALL support `--dry-run` on the pipeline command, applying dry-run behavior to all stages
4. THE Forge SHALL use `onetrainer` as the default export target for the pipeline command when `--target` is not specified

### Requirement 18: OpenAI Connection Test

**User Story:** As a LoRA trainer, I want to verify my OpenAI API configuration before running captioning, so that I catch authentication issues early.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge test-openai`, THE Forge SHALL verify that an OpenAI API key is available from environment variables or `.env` file
2. THE Forge SHALL verify connectivity to the OpenAI API by making a minimal non-image request
3. THE Forge SHALL not send any user images during the test-openai command
4. THE Forge SHALL report success or failure with a descriptive message indicating the issue (missing key, invalid key, network error, model not available)

### Requirement 19: Status Command

**User Story:** As a LoRA trainer, I want to see a summary of my project's current state, so that I know where I am in the preparation pipeline.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge status`, THE Forge SHALL display: project name, source folder path, scanned image count, imported image count, accepted image count, rejected image count, working image count, duplicate candidate count, quality warning count, captioned image count, missing caption count, export status, and last completed stage
2. IF no project exists in the current directory, THEN THE Forge SHALL report that no project was found

### Requirement 20: Doctor Command

**User Story:** As a LoRA trainer, I want to validate my project's integrity, so that I can detect and fix consistency issues between files and database state.

#### Acceptance Criteria

1. WHEN the user runs `lora-forge doctor`, THE Forge SHALL verify that `project.json` exists and is valid
2. THE Forge SHALL verify that `forge.db` exists and is accessible
3. THE Forge SHALL verify that Source_Directory files match State_Database IMPORTED records
4. THE Forge SHALL verify that Working_Directory files match State_Database ACCEPTED/WORKING_CREATED records
5. THE Forge SHALL verify that each Working_Image has a corresponding Caption_File if the image status is CAPTIONED
6. THE Forge SHALL verify that the Export_Directory is complete if an export has been recorded
7. THE Forge SHALL verify that the OpenAI API key is available if captioning is required but incomplete
8. THE Forge SHALL report each integrity issue found with a description and suggested repair action

### Requirement 21: Format Preservation and Optional Conversion

**User Story:** As a LoRA trainer, I want my images preserved in their original format by default, so that I avoid unnecessary quality loss from format conversion.

#### Acceptance Criteria

1. THE Forge SHALL preserve the original supported image format (.jpg, .jpeg, .png, .webp) when copying to Working_Directory and Export_Directory by default
2. WHEN `--convert <format>` is specified during export, THE Forge SHALL convert images to the specified format in the Export_Directory only
3. THE Forge SHALL not modify images in Source_Directory regardless of conversion settings
4. WHEN conversion is performed, THE Forge SHALL record the original format, converted format, conversion timestamp, and conversion settings in the State_Database

### Requirement 22: Configuration Defaults

**User Story:** As a LoRA trainer, I want sensible defaults for quality thresholds and processing parameters, so that I can start quickly and tune later.

#### Acceptance Criteria

1. THE Forge SHALL include the following default configuration in Project_Config: quality minimum width 512, minimum height 512, maximum aspect ratio 2.5, blur threshold 100.0, dark threshold 35, bright threshold 220; caption lint minimum characters 20, maximum characters 220; dedupe perceptual hash threshold 10; export default repeats 20, preserve format true
2. WHEN the user modifies values in Project_Config, THE Forge SHALL use the modified values for all subsequent processing
3. IF a required configuration value is missing from Project_Config, THEN THE Forge SHALL use the documented default value and log a warning

### Requirement 23: Testing

**User Story:** As a developer, I want automated tests for major workflow components, so that I can verify correctness and prevent regressions.

#### Acceptance Criteria

1. THE Forge SHALL include pytest-based tests covering: project initialization, image scanning and ignore rules, image import to source, sequential renaming logic, EXIF metadata stripping, exact and near-duplicate detection, quality check thresholds, caption prefix enforcement, caption linting rules, kohya_ss export folder structure, resume behavior across stages, and dry-run mode producing no side effects
2. THE Forge SHALL include a test for the round-trip property: an image imported to source, accepted to working, and exported to kohya_ss retains identical visual content (pixel data) at each stage
3. THE Forge SHALL include tests verifiable without an active OpenAI API key by using mocked API responses
