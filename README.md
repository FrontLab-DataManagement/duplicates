# Duplicate Detection and Storage Audit Tools

Command-line tools for identifying exact duplicate files and reviewing potential storage savings in research and shared computing environments.

## Tools

| Script | Purpose |
|---|---|
| `duplicate_scan.py` | Scan a directory and write a general duplicate report. |
| `duplicate_owner_summary.py` | Add file-owner summaries, per-owner reports, and CSV-based quarantine. |

Duplicates are identified by matching file size and a BLAKE3 or SHA-256 content hash. The tools do not detect near-duplicates or files that merely have similar names.

## Requirements

- Python 3 on Linux or macOS
- Read permission for the files being scanned
- Optional: [`blake3`](https://pypi.org/project/blake3/) for faster hashing

```bash
git clone https://github.com/FrontLab-DataManagement/duplicates.git
cd duplicates
python -m pip install blake3  # optional
```

The owner-aware tool uses POSIX ownership metadata and is not currently supported on Windows.

## Quick start

Run a general scan:

```bash
python duplicate_scan.py /path/to/data
```

Run an owner-aware scan and create per-owner reports:

```bash
python duplicate_owner_summary.py /path/to/data --per-owner-files
```

Restrict the scan to one or more owners:

```bash
python duplicate_owner_summary.py /path/to/data \
  --user example_user another_user \
  --per-owner-files
```

Use SHA-256 explicitly:

```bash
python duplicate_owner_summary.py /path/to/data --hash sha256
```

See all options:

```bash
python duplicate_scan.py --help
python duplicate_owner_summary.py --help
```

## Outputs

The general scanner writes reports to `./reports/`. The owner-aware scanner writes reports to `./user_reports/` and can optionally create one CSV per owner.

Reports include duplicate groups, candidate paths, file ownership, timestamps, hashes, sizes, proposed actions, and potential reclaimable capacity.

## Safety and interpretation

Scanning reads file contents for hashing and writes reports, but does not modify source files. Files are moved only when quarantine is explicitly requested and confirmed.

```bash
python duplicate_owner_summary.py \
  --quarantine-from user_reports/duplicate_report_all_users_YYYYMMDD_HHMMSS.csv
```

Before quarantining files:

1. Verify that a current backup exists.
2. Review every proposed action in the CSV.
3. Confirm that the retained copy is authoritative and used by no active workflow.
4. Use a dedicated quarantine directory on storage with sufficient capacity.
5. Retain the quarantine manifest until the project has been validated.

The `KEEP` selection is a heuristic: the newest modification time is preferred, with the shortest path used as a tie-breaker.

## License and citation

Released under the [MIT License](LICENSE). Citation metadata are available in [`CITATION.cff`](CITATION.cff).
