# Duplicate Detection and Storage Audit Tools

This repository provides command-line Python tools for detecting exact duplicate files, auditing storage usage, summarizing duplicate burden by file owner, and safely preparing duplicate files for quarantine.

The tools are designed for large research storage environments, shared servers, neuroimaging repositories, BIDS-style datasets, and institutional file systems.

---

## Scripts included

### 1. `duplicate_scan.py`

Basic duplicate scanner.

It scans a target directory, detects exact duplicate files using file-size grouping and hashing, and writes a duplicate report CSV.

Use this script when you want a direct duplicate report for a folder.

---

### 2. `duplicate_user_scan.py`

Extended owner-aware duplicate scanner.

It scans a target directory, detects exact duplicate files, records file ownership metadata, summarizes duplicate capacity by user, writes per-user reports, and optionally quarantines duplicates based on a saved CSV report.

Use this script when you want user-level storage auditing.

---

# What counts as a duplicate?

Files are considered duplicates only when they have:

1. the same file size
2. the same content hash

This means the scripts detect exact byte-for-byte duplicates.

They do **not** detect:

- similar filenames
- similar folders
- near-duplicate images
- partially overlapping files
- files with similar content but different bytes

---

# Safety model

By default, the scripts are read-only.

They do **not** delete files.

The workflow is:

```text
scan folder
↓
write duplicate report
↓
review CSV
↓
optionally quarantine duplicates
```

Quarantine means files are moved, not deleted.

---

# Hashing

The scripts support:

- BLAKE3
- SHA256

Default mode:

```bash
--hash auto
```

This means:

- use BLAKE3 if installed
- otherwise fall back to SHA256

SHA256 is built into Python and does not require installation.

BLAKE3 is faster, but optional.

---

# Installation

Download the .py or clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

Optional: create a virtual environment:

```bash
python3 -m venv dedup_env
source dedup_env/bin/activate
```

Optional: install BLAKE3:

```bash
pip install blake3
```

If BLAKE3 cannot be installed, the scripts still work with SHA256.

---

# Script 1: `duplicate_scan.py`

## Basic scan

```bash
python duplicate_scan.py /path/to/target_directory
```

Example:

```bash
python duplicate_scan.py ./data
```

This creates a report in the script launch directory (recommended to create a safe folder for the activity):

```text
./reports/
```

---

## Scan with explicit output path

```bash
python duplicate_scan.py /path/to/target_directory --out duplicate_report.csv
```

---

## Scan using SHA256

```bash
python duplicate_scan.py /path/to/target_directory --hash sha256
```

---

## Scan files up to a larger size

Default maximum file size is 20,000 MB.

To include larger files:

```bash
python duplicate_scan.py /path/to/target_directory --max-mb 50000
```

---

# Script 2: `duplicate_user_scan.py`

This is the main storage-audit script.

It creates:

```text
./user_reports/
├── duplicate_report_*.csv
├── duplicate_capacity_by_owner_*.csv
├── duplicate_capacity_by_owner_*.txt
└── per_owner/
    ├── duplicates_user1.csv
    ├── duplicates_user2.csv
    └── ...
```

---

## Full scan for all users

```bash
python duplicate_user_scan.py /path/to/target_directory --per-owner-files
```

Example:

```bash
python duplicate_user_scan.py ./data --per-owner-files
```

---

## Scan a specific user

```bash
python duplicate_user_scan.py /path/to/target_directory --user USERNAME --per-owner-files
```

Example:

```bash
python duplicate_user_scan.py /path/to/storage --user [username] --per-owner-files
```

---

## Scan multiple users

```bash
python duplicate_user_scan.py /path/to/storage --user user1 user2 user3 --per-owner-files
```

Example:

```bash
python duplicate_user_scan.py /path/to/storage --user [username] nobody --per-owner-files
```

---

## Force output directory

By default, outputs are written to:

```text
./user_reports/
```

relative to the directory where the script is launched.

To choose another output folder:

```bash
python duplicate_user_scan.py /path/to/storage --out-dir /path/to/output_folder
```

---

# Output files explained

## 1. Full duplicate report

Example:

```text
user_reports/duplicate_report_all_users_20260521_153000.csv
```

This contains one row per duplicate file candidate.

Important columns:

| Column | Meaning |
|---|---|
| `duplicate_group_id` | ID of the duplicate group |
| `recommended_action` | `KEEP` or `QUARANTINE` |
| `keep_file` | File recommended to keep |
| `candidate_file` | File being evaluated |
| `quarantine_target` | Where file would move if quarantined |
| `owner_username` | File owner |
| `last_opened` | Last access time |
| `modified` | Last modification time |
| `created_or_metadata_changed` | Unix ctime |
| `hash_algorithm` | BLAKE3 or SHA256 |
| `content_hash` | File hash |
| `size_bytes` | File size in bytes |
| `size_mb` | File size in MB |
| `size_gb` | File size in GB |

---

## 2. Owner capacity summary CSV

Example:

```text
user_reports/duplicate_capacity_by_owner_all_users_20260521_153000.csv
```

This summarizes duplicate burden by user.

Important columns:

| Column | Meaning |
|---|---|
| `owner_username` | File owner |
| `duplicate_groups` | Number of duplicate groups involving this owner |
| `duplicate_rows_all` | Number of duplicate file rows |
| `keep_rows` | Number of files recommended to keep |
| `quarantine_candidates` | Number of files recommended for quarantine |
| `duplicate_capacity_mb_all` | Total duplicate capacity in MB |
| `duplicate_capacity_gb_all` | Total duplicate capacity in GB |
| `quarantine_capacity_mb` | Potential reclaimable capacity in MB |
| `quarantine_capacity_gb` | Potential reclaimable capacity in GB |

Rows are sorted in descending order by reclaimable quarantine capacity.

---

## 3. Human-readable text report

Example:

```text
user_reports/duplicate_capacity_by_owner_all_users_20260521_153000.txt
```

This report summarizes:

```text
Total duplicate rows
Total duplicate capacity
Total duplicate capacity GB
Total quarantine candidates
Potential reclaimable capacity
Potential reclaimable capacity GB
```

It also lists the users with the largest duplicate burden.

---

## 4. Per-user duplicate reports

If `--per-owner-files` is used, the script creates:

```text
user_reports/per_owner/
```

Example files:

```text
duplicates_[username].csv
duplicates_nobody.csv
```

Each file contains only the duplicates associated with that user.

---

# Quarantine behavior

The scanner recommends one file to keep per duplicate group.

For example, if two files are identical:

```text
file_A.nii.gz → KEEP
file_B.nii.gz → QUARANTINE
```

If three files are identical:

```text
file_A.nii.gz → KEEP
file_B.nii.gz → QUARANTINE
file_C.nii.gz → QUARANTINE
```

The default rule is:

1. keep the newest modified file
2. if tied, keep the shortest path

Only the files marked `QUARANTINE` are moved.

---

# Quarantine from a saved CSV

After reviewing a duplicate report, quarantine can be triggered later without rescanning.

```bash
python duplicate_user_scan.py --quarantine-from user_reports/duplicate_report_all_users_YYYYMMDD_HHMMSS.csv
```

Example:

```bash
python duplicate_user_scan.py --quarantine-from user_reports/duplicate_report_[username]_20260521_153000.csv
```

The script reads the CSV and moves only rows where:

```text
recommended_action = QUARANTINE
```

Files are moved into:

```text
./quarantined_duplicates/
```

relative to the directory where the script is launched.

A quarantine manifest is written to:

```text
./user_reports/
```

---

# Quarantine safety

The script asks for confirmation before moving files:

```text
Move 120 files to quarantined_duplicates? Type y or n:
```

Files are moved only if the user types:

```text
y
```

Otherwise, no files are moved.

---

# Recommended workflow

## Step 1: Run a scan

```bash
python duplicate_user_scan.py /path/to/storage --per-owner-files
```

## Step 2: Review reports

Open:

```text
user_reports/duplicate_capacity_by_owner_*.csv
user_reports/duplicate_capacity_by_owner_*.txt
user_reports/duplicate_report_*.csv
```

## Step 3: Optionally quarantine later

```bash
python duplicate_user_scan.py --quarantine-from user_reports/duplicate_report_*.csv
```

---

# Example workflow on shared storage

```bash
cd /path/to/my/workspace
python duplicate_user_scan.py /path/to/shared/storage --per-owner-files
```

Outputs:

```text
/path/to/my/workspace/user_reports/
```

Quarantine later:

```bash
python duplicate_user_scan.py --quarantine-from user_reports/duplicate_report_all_users_20260521_153000.csv
```

Quarantined files:

```text
/path/to/my/workspace/quarantined_duplicates/
```

---

# Keeping the PC awake during long scans

On macOS, use:

```bash
caffeinate python duplicate_user_scan.py /path/to/storage --per-owner-files
```

For a user-specific scan:

```bash
caffeinate python duplicate_user_scan.py /path/to/storage --user Victor.Altmayer --per-owner-files
```

---

# Running long jobs on a cluster

For long network scans, use `tmux`, `screen`, or a scheduler such as SLURM.

Example with `tmux`:

```bash
tmux new -s dedup_scan
python duplicate_user_scan.py /path/to/storage --per-owner-files
```

Detach:

```text
Ctrl + B
D
```

Reattach:

```bash
tmux attach -t dedup_scan
```

---

# Notes on permissions

Some files may be skipped because of:

- permission restrictions
- unreadable files
- broken symlinks
- network interruptions
- missing files during scan

The terminal summary reports:

```text
Skipped permission denied
Skipped unreadable/other files
Permission errors during hashing
Hash/read errors during hashing
```

---

# GitHub portability

The scripts do not contain hardcoded storage paths.

Users specify the scan target at runtime:

```bash
python duplicate_user_scan.py /path/to/target_directory
```

Outputs are written relative to the launch directory by default:

```text
./user_reports/
./quarantined_duplicates/
```

This makes the tools portable across local machines, servers, HPC systems, and institutional storage environments.

---

# License

See `LICENSE`.

---

# Citation

If you use these tools for research, data management, or institutional storage auditing, please cite this repository.

See `CITATION.cff`.
