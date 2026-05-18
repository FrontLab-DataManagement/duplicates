#!/usr/bin/env python3

import argparse
import csv
import hashlib
import os
import pwd
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import blake3
except ImportError:
    blake3 = None


EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".cache",
    "node_modules", "site-packages", "duplication_audit",
    "quarantined_duplicates"
}


def get_owner(path: Path) -> str:
    try:
        return pwd.getpwuid(path.stat().st_uid).pw_name
    except Exception:
        return ""


def get_group(path: Path) -> str:
    try:
        return pwd.getpwuid(path.stat().st_gid).pw_name
    except Exception:
        return ""


def user_matches(owner: str, query: str, partial: bool) -> bool:
    owner = owner.lower()
    query = query.lower()
    return query in owner if partial else owner == query


def compute_hash(path: Path, algorithm: str) -> str:
    if algorithm == "blake3":
        if blake3 is None:
            raise RuntimeError("BLAKE3 is not installed. Install with: pip install blake3")
        h = blake3.blake3()
    elif algorithm == "sha256":
        h = hashlib.sha256()
    else:
        raise ValueError("Unsupported hash algorithm")

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def collect_files(root: Path, skip_symlinks: bool = True):
    files = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDED_DIRS]

        for filename in filenames:
            path = Path(dirpath) / filename
            try:
                if skip_symlinks and path.is_symlink():
                    continue
                if path.is_file():
                    files.append(path)
            except Exception:
                continue

    return files


def file_row(path: Path):
    stat = path.stat()
    return {
        "owner": get_owner(path),
        "group": get_group(path),
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 ** 2), 3),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "extension": path.suffix.lower(),
        "path": str(path),
    }


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: r.get("size_bytes", 0), reverse=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def choose_keep_file(paths):
    return sorted(paths, key=lambda p: (-p.stat().st_mtime, len(str(p))))[0]


def duplicate_audit(user_files, algorithm: str):
    by_size = defaultdict(list)

    for path in user_files:
        try:
            size = path.stat().st_size
            if size > 0:
                by_size[size].append(path)
        except Exception:
            continue

    by_hash = defaultdict(list)

    for size, paths in by_size.items():
        if len(paths) < 2:
            continue

        for path in paths:
            try:
                digest = compute_hash(path, algorithm)
                by_hash[(size, digest)].append(path)
            except Exception:
                continue

    rows = []
    group_id = 1

    for (size, digest), paths in by_hash.items():
        if len(paths) < 2:
            continue

        keep_file = choose_keep_file(paths)

        for path in paths:
            stat = path.stat()
            quarantine = path != keep_file

            rows.append({
                "duplicate_group_id": group_id,
                "recommended_action": "QUARANTINE" if quarantine else "KEEP",
                "quarantine_recommended": "YES" if quarantine else "NO_KEEP_THIS_FILE",
                "keep_file": str(keep_file),
                "candidate_file": str(path),
                "owner": get_owner(path),
                "size_bytes": size,
                "size_mb": round(size / (1024 ** 2), 3),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "hash_algorithm": algorithm.upper(),
                "content_hash": digest,
                "reason": f"same {algorithm.upper()} content hash",
            })

        group_id += 1

    return rows


def safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in text)


def main():
    parser = argparse.ArgumentParser(
        description="NIM user ownership and duplicate audit."
    )

    parser.add_argument("sourcepath", help="Root folder to scan")
    parser.add_argument("user_query", help="User/owner name or partial handle to audit")
    parser.add_argument("--partial", action="store_true", help="Allow partial username matching")
    parser.add_argument("--hash", choices=["blake3", "sha256"], default="blake3")

    args = parser.parse_args()

    root = Path(args.sourcepath).expanduser().resolve()
    user_query = args.user_query
    safe_user = safe_filename(user_query)

    if not root.exists() or not root.is_dir():
        print(f"Invalid source path: {root}", file=sys.stderr)
        sys.exit(1)

    output_dir = root / "duplication_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning: {root}")
    print(f"User query: {user_query}")
    print(f"Partial matching: {args.partial}")
    print(f"Output folder: {output_dir}")

    all_files = collect_files(root)
    user_files = []

    matched_owners = set()

    for path in all_files:
        owner = get_owner(path)
        if user_matches(owner, user_query, args.partial):
            user_files.append(path)
            matched_owners.add(owner)

    owned_rows = [file_row(p) for p in user_files]

    write_csv(
        output_dir / f"{safe_user}_owned_files.csv",
        owned_rows,
        ["owner", "group", "size_bytes", "size_mb", "modified", "extension", "path"]
    )

    write_csv(
        output_dir / f"{safe_user}_recently_modified_files.csv",
        owned_rows,
        ["owner", "group", "size_bytes", "size_mb", "modified", "extension", "path"]
    )

    duplicate_rows = duplicate_audit(user_files, args.hash)

    write_csv(
        output_dir / f"{safe_user}_duplicate_report.csv",
        duplicate_rows,
        [
            "duplicate_group_id",
            "recommended_action",
            "quarantine_recommended",
            "keep_file",
            "candidate_file",
            "owner",
            "size_bytes",
            "size_mb",
            "modified",
            "hash_algorithm",
            "content_hash",
            "reason",
        ]
    )

    print()
    print(f"Total files scanned: {len(all_files)}")
    print(f"Matched owners: {', '.join(sorted(matched_owners)) if matched_owners else 'none'}")
    print(f"Matched files: {len(user_files)}")
    print(f"Duplicate rows: {len(duplicate_rows)}")
    print()
    print("Reports written to:")
    print(output_dir)


if __name__ == "__main__":
    main()
