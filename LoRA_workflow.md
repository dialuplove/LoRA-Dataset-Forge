# LoRA Dataset Forge MVP Test Workflow

This guide is for a nontechnical customer testing LoRA Dataset Forge with a real image dataset.

The app helps turn a folder of images into a clean dataset for LoRA training. It does not train the LoRA itself. It prepares the images and captions so they can be used later in tools such as OneTrainer or kohya_ss.

## What The App Does

LoRA Dataset Forge takes your original image folder and creates a separate project workspace.

It uses this flow:

```text
your original image folder
  -> source/
  -> working/
  -> exports/
```

- `source/` keeps copies of your original images with original filenames and metadata preserved.
- `working/` contains accepted images renamed in order, with private metadata stripped.
- `working/` also stores the matching `.txt` caption files beside each image.
- `exports/` contains the final dataset formatted for a training tool.

Your original image folder is not modified.

## Before You Start

You need:

- A folder of images to test with
- JPG, JPEG, PNG, or WebP images
- A terminal window
- Python 3.11 or newer
- Optional: an OpenAI API key if you want the app to generate captions automatically

For best results, test with 10-30 images first. Use a small real-world dataset before trying a large folder.

Recommended image folder example:

```text
/Users/you/Pictures/my_lora_test_images/
```

## Step 0: Set Up The App After Pulling The Repo

If you have just pulled or downloaded the repository, you need to create a local Python environment and install the app dependencies.

Open Terminal and go to the LoRA Dataset Forge folder:

```bash
cd "/path/to/LoRA Dataset Forge"
```

Example:

```bash
cd "/Volumes/projects/LoRA Dataset Forge"
```

### 0.1 Check Python

Run:

```bash
python3 --version
```

You should see Python 3.11 or newer.

Example:

```text
Python 3.12.3
```

If `python3` is not found, install Python from [python.org](https://www.python.org/downloads/) or use your normal system package manager.

### 0.2 Create A Virtual Environment

A virtual environment is a local folder that keeps this app’s Python packages separate from the rest of your computer.

Run:

```bash
python3 -m venv .venv
```

This creates a folder named:

```text
.venv/
```

### 0.3 Install The App And Dependencies

Run:

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

This installs LoRA Dataset Forge and its required packages, including:

- Typer and Rich for the command-line interface
- Pydantic for project configuration
- Pillow, piexif, imagehash, NumPy, and OpenCV for image processing
- python-dotenv and OpenAI for optional caption generation
- pytest and hypothesis for testing

If installation fails because your version of `pip` is old, run:

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

### 0.4 Verify The App Command

Run:

```bash
.venv/bin/lora-forge --help
```

You should see commands such as:

```text
init
scan
import
quality
dedupe
accept
build-working
caption
export
report
status
doctor
run
```

### 0.5 Optional: Run The Test Suite

To confirm the app is working locally, run:

```bash
.venv/bin/python -m pytest
```

You should see passing tests.

Example:

```text
30 passed
```

If tests fail, copy the error output and share it with the project maintainer.

## Step 1: Choose Your Trigger And Class Token

The trigger token is the special word that activates your LoRA.

Example:

```text
dawivre
```

The class token describes the subject type.

Examples:

```text
woman
man
person
character
style
dog
cat
```

For a person dataset, a caption may look like:

```text
dawivre woman, smiling, wearing a blue shirt, outdoor lighting
```

Rules:

- The trigger token should be unique.
- Do not use a common word like `woman`, `person`, `photo`, or `image` as the trigger.
- The trigger token should not contain spaces.

## Step 2: Create A Project

Run this command, replacing the image folder path and names with your own:

```bash
.venv/bin/lora-forge init "/path/to/your/images" \
  --name my_lora_test \
  --trigger dawivre \
  --class-token woman
```

Example:

```bash
.venv/bin/lora-forge init "/Users/you/Pictures/my_lora_test_images" \
  --name dawivre_test \
  --trigger dawivre \
  --class-token woman
```

This creates a new project folder:

```text
dawivre_test/
```

Inside it, you should see:

```text
project.json
forge.db
source/
working/
exports/
duplicates/
rejected/
reports/
.env.example
.gitignore
```

## Step 3: Enter The Project Folder

After initialization, go into the project folder:

```bash
cd dawivre_test
```

All following commands should be run from inside this project folder.

## Step 4: Scan For Images

Scan finds supported image files in your original image folder.

```bash
../.venv/bin/lora-forge scan
```

What this does:

- Finds `.jpg`, `.jpeg`, `.png`, and `.webp` files
- Ignores app folders such as `.git`, `.kiro`, `.obsidian`, `source`, `working`, and `exports`
- Records each discovered image in the project database
- Computes hashes used later for duplicate detection

Your original files are not modified.

## Step 5: Import Images Into `source/`

Import copies the discovered images into the project’s `source/` folder.

```bash
../.venv/bin/lora-forge import
```

What this does:

- Copies images from your original folder into `source/`
- Preserves original filenames
- Preserves original file metadata
- Does not modify your original folder

At this point, `source/` is your traceable backup copy inside the project.

## Step 6: Check Image Quality

Run:

```bash
../.venv/bin/lora-forge quality
```

What this checks:

- Can the image be opened?
- Is it too small?
- Is it too wide or tall?
- Is it possibly blurry?
- Is it very dark?
- Is it very bright?

Images with warnings are not automatically deleted. The app records warnings so it can make a default accept/reject decision in the next step.

## Step 7: Detect Duplicates

Run:

```bash
../.venv/bin/lora-forge dedupe
```

What this does:

- Detects exact duplicate files
- Detects near-duplicate images using visual similarity
- Copies duplicate candidates into `duplicates/` for review

Duplicates are not deleted from your original folder.

## Step 8: Accept Or Reject Images

Run:

```bash
../.venv/bin/lora-forge accept
```

What this MVP does:

- Accepts images with no duplicate warning and no quality warning
- Rejects images with duplicate or quality warnings
- Copies rejected images into `rejected/`

This is an automatic MVP decision step. A future version may include a nicer human review workflow.

## Step 9: Build The Working Dataset

Run:

```bash
../.venv/bin/lora-forge build-working
```

What this does:

- Selects only accepted images
- Copies them from `source/` into `working/`
- Renames them sequentially
- Strips private metadata from the working copies
- Creates the expected caption filename mapping

Example working files:

```text
working/
  dawivre_0001.jpg
  dawivre_0002.jpg
  dawivre_0003.jpg
```

The app never strips metadata from your original image folder or from `source/`.

## Step 10: Add Captions

Captions are stored as `.txt` files beside each image in `working/`.

Example:

```text
working/
  dawivre_0001.jpg
  dawivre_0001.txt
```

Each caption should start with:

```text
trigger_token class_token,
```

Example:

```text
dawivre woman, smiling, wearing a blue shirt, indoor lighting, medium shot
```

### Option A: Add Captions Manually

Open the `working/` folder.

For each image, create a `.txt` file with the same base name:

```text
dawivre_0001.jpg
dawivre_0001.txt
```

Then run:

```bash
../.venv/bin/lora-forge caption
```

What happens:

- The app checks for existing `.txt` files first
- Valid captions are reused
- Fixable captions are repaired locally
- No OpenAI call is made for valid existing captions

This is the safest way to test caption reuse without using an API key.

### Option B: Use OpenAI Captioning

Create a `.env` file in the project folder:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your API key:

```env
OPENAI_API_KEY=your-real-api-key
```

Test the connection:

```bash
../.venv/bin/lora-forge test-openai
```

Then generate captions:

```bash
../.venv/bin/lora-forge caption
```

For a small test run:

```bash
../.venv/bin/lora-forge caption --limit 5
```

To regenerate captions even if they already exist:

```bash
../.venv/bin/lora-forge caption --force
```

Important:

- OpenAI is only used after `build-working`.
- Only accepted working images are eligible for captioning.
- Existing valid `.txt` captions are reused before any OpenAI call.
- Your API key is not printed by the app.

## Step 11: Export The Dataset

The default export target is OneTrainer:

```bash
../.venv/bin/lora-forge export
```

This creates:

```text
exports/onetrainer/
  dawivre_0001.jpg
  dawivre_0001.txt
  dawivre_0002.jpg
  dawivre_0002.txt
```

To export for kohya_ss:

```bash
../.venv/bin/lora-forge export --target kohya --repeats 20
```

This creates:

```text
exports/kohya/20_dawivre woman/
  dawivre_0001.jpg
  dawivre_0001.txt
  dawivre_0002.jpg
  dawivre_0002.txt
```

To export both:

```bash
../.venv/bin/lora-forge export --target all --repeats 20
```

Export expects accepted working images to have captions. If captions are missing, export may fail.

## Step 12: Generate A Report

Run:

```bash
../.venv/bin/lora-forge report
```

This creates:

```text
reports/report.md
reports/report.json
```

The report summarizes the project counts, captions, and export runs.

## Step 13: Check Project Status

Run:

```bash
../.venv/bin/lora-forge status
```

This shows counts such as:

- Scanned images
- Imported images
- Accepted images
- Rejected images
- Working images
- Captioned images
- Export runs

## Step 14: Run Integrity Check

Run:

```bash
../.venv/bin/lora-forge doctor
```

This checks whether important project files match the database.

It can detect issues such as:

- Missing `project.json`
- Missing `forge.db`
- Missing source files
- Missing working files
- Missing caption files for captioned images

## Optional: Preview Commands With Dry Run

Some commands support:

```bash
--dry-run
```

Example:

```bash
../.venv/bin/lora-forge scan --dry-run
```

Dry-run mode is intended to show planned actions without creating files, changing the database, or making API calls.

## Optional: Full Pipeline Command

There is also a full pipeline command:

```bash
.venv/bin/lora-forge run "/path/to/your/images" \
  --name my_lora_test \
  --trigger dawivre \
  --class-token woman \
  --target onetrainer
```

For first-time testing, the step-by-step workflow is recommended instead. It is easier to see what happened at each stage.

## How To Review The Results

After the workflow, inspect these folders:

### `source/`

This should contain copies of your original input images.

Use this to confirm:

- Original filenames are preserved
- Files were copied into the project
- The original image folder was not changed

### `working/`

This is the main prepared dataset.

Use this to confirm:

- Only accepted images are present
- Filenames are sequential
- Captions are beside images
- Captions begin with the trigger and class token

### `duplicates/`

This contains duplicate candidates.

### `rejected/`

This contains images automatically rejected by the MVP rules.

### `exports/`

This contains the final trainer-ready output.

For most testers, the OneTrainer export is the easiest first target:

```text
exports/onetrainer/
```

## Current MVP Limitations

This MVP is functional, but still early.

Known limitations:

- The automatic accept/reject step is simple.
- There is no graphical review screen yet.
- Reports are basic and will become more detailed.
- `doctor` checks core file consistency but is not yet a full repair tool.
- The safest captioning test is to create `.txt` files manually and confirm the app reuses them.
- Full OpenAI captioning requires a valid API key and may cost money.

## Recommended Customer Test Script

For a first real-world test, use this exact order:

```bash
cd "/Volumes/projects/LoRA Dataset Forge"

.venv/bin/lora-forge init "/path/to/your/images" \
  --name my_lora_test \
  --trigger dawivre \
  --class-token woman

cd my_lora_test

../.venv/bin/lora-forge scan
../.venv/bin/lora-forge import
../.venv/bin/lora-forge quality
../.venv/bin/lora-forge dedupe
../.venv/bin/lora-forge accept
../.venv/bin/lora-forge build-working
```

Then either manually add captions in `working/` or configure OpenAI.

After captions exist:

```bash
../.venv/bin/lora-forge caption
../.venv/bin/lora-forge export
../.venv/bin/lora-forge report
../.venv/bin/lora-forge status
../.venv/bin/lora-forge doctor
```

The final dataset should be in:

```text
exports/onetrainer/
```
