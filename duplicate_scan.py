#!/usr/bin/env python3
"""
Read-only duplicate scanner.

Finds exact-content duplicates across a selected path using:
1. recursive file discovery
2. file-size grouping
3. BLAKE3 or SHA256 hashing
4. CSV report with quarantine recommendation

This script never deletes, moves, uploads, or downloads files.
"""

import argparse
import csv
import hashlib
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import blake3
except ImportError:
    blake3 = None


EXCLUDED_NAMES = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "$recycle.bin",
    "system volume information",
    "appdata",
    "node_modules",
    "__pycache__",
    ".cache",
    ".git",
    ".venv",
    "venv",
    "env",
    "site-packages",
    ".nim_quarantine",
}


def is_excluded_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(parts & EXCLUDED_NAMES)


def file_hash(path: Path, algorithm: str) -> str:
    algorithm = algorithm.lower()

    if algorithm == "blake3":
        if blake3 is None:
            raise RuntimeError("BLAKE3 selected but package is not installed. Install with: pip install blake3")
        h = blake3.blake3()
    elif algorithm == "sha256":
        h = hashlib.sha256()
    else:
        raise ValueError("Unsupported hash algorithm. Use blake3 or sha256.")

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def collect_files(root: Path, max_mb: float, skip_symlinks: bool, exclude_system: bool):
    max_bytes = int(max_mb * 1024 * 1024)
    files = []

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)

        if exclude_system:
            dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDED_NAMES]

        for filename in filenames:
            path = current_dir / filename

            try:
                if skip_symlinks and path.is_symlink():
                    continue

                if exclude_system and is_excluded_path(path):
                    continue

                if not path.is_file():
                    continue

                size = path.stat().st_size

                if size <= 0:
                    continue

                if size > max_bytes:
                    continue

                files.append(path)

            except Exception:
                continue

    return files


def choose_keep_file(paths):
    """
    Default rule:
    keep newest file.
    If modified time ties, keep shortest path.
    """
    return sorted(
        paths,
        key=lambda p: (-p.stat().st_mtime, len(str(p)))
    )[0]


def scan_duplicates(root: Path, output_csv: Path, algorithm: str, max_mb: float, skip_symlinks: bool, exclude_system: bool):
    files = collect_files(root, max_mb, skip_symlinks, exclude_system)

    by_size = defaultdict(list)
    for path in files:
        try:
            by_size[path.stat().st_size].append(path)
        except Exception:
            continue

    by_hash = defaultdict(list)

    for size, same_size_files in by_size.items():
        if len(same_size_files) < 2:
            continue

        for path in same_size_files:
            try:
                digest = file_hash(path, algorithm)
                by_hash[(size, digest)].append(path)
            except Exception:
                continue

    rows = []
    duplicate_group_id = 1

    for (size, digest), paths in by_hash.items():
        if len(paths) < 2:
            continue

        keep_file = choose_keep_file(paths)

        for path in sorted(paths, key=lambda p: str(p).lower()):
            stat = path.stat()
            quarantine_recommended = path != keep_file

            rows.append({
                "duplicate_group_id": duplicate_group_id,
                "quarantine_recommended": "YES" if quarantine_recommended else "NO_KEEP_THIS_FILE",
                "recommended_action": "QUARANTINE" if quarantine_recommended else "KEEP",
                "keep_file": str(keep_file),
                "candidate_file": str(path),
                "hash_algorithm": algorithm.upper(),
                "content_hash": digest,
                "size_bytes": size,
                "size_mb": round(size / (1024 ** 2), 3),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "reason": f"same {algorithm.upper()} content hash",
            })

        duplicate_group_id += 1

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "duplicate_group_id",
            "quarantine_recommended",
            "recommended_action",
            "keep_file",
            "candidate_file",
            "hash_algorithm",
            "content_hash",
            "size_bytes",
            "size_mb",
            "modified",
            "reason",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Files scanned: {len(files)}")
    print(f"Duplicate groups: {duplicate_group_id - 1}")
    print(f"Duplicate rows written: {len(rows)}")
    print(f"CSV report: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Read-only exact-content duplicate scanner.")

    parser.add_argument("path", help="Root folder to scan")
    parser.add_argument("--out", default="duplicate_report.csv", help="Output CSV path")
    parser.add_argument("--hash", choices=["blake3", "sha256"], default="blake3", help="Hash algorithm")
    parser.add_argument("--max-mb", type=float, default=2000, help="Maximum file size to hash in MB")
    parser.add_argument("--follow-symlinks", action="store_true", help="Allow symlinks")
    parser.add_argument("--include-system", action="store_true", help="Do not exclude system/cache/environment folders")

    args = parser.parse_args()

    root = Path(args.path).expanduser().resolve()
    output_csv = Path(args.out).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        print(f"Invalid scan path: {root}", file=sys.stderr)
        sys.exit(1)

    scan_duplicates(
        root=root,
        output_csv=output_csv,
        algorithm=args.hash,
        max_mb=args.max_mb,
        skip_symlinks=not args.follow_symlinks,
        exclude_system=not args.include_system,
    )


if __name__ == "__main__":
    main()
