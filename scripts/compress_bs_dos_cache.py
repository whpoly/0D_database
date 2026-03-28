from __future__ import annotations

import argparse
import gzip
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compress existing bs/dos cache JSON files to .json.gz without reparsing VASP outputs."
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path("dos_bs"),
        help="Root directory that contains per-material bs.json and dos.json files.",
    )
    parser.add_argument(
        "--delete-originals",
        action="store_true",
        help="Delete the original .json files after writing .json.gz.",
    )
    return parser.parse_args()


def compress_file(path: Path, delete_originals: bool) -> tuple[int, int]:
    target = path.with_name(f"{path.name}.gz")
    with path.open("rb") as src, gzip.open(target, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)

    original_size = path.stat().st_size
    compressed_size = target.stat().st_size

    if delete_originals:
        path.unlink()

    return original_size, compressed_size


def main() -> None:
    args = parse_args()
    cache_root = args.cache_root.resolve()

    if not cache_root.is_dir():
        raise SystemExit(f"Cache root not found: {cache_root}")

    total_original = 0
    total_compressed = 0
    processed = 0

    for path in sorted(cache_root.rglob("*.json")):
        original_size, compressed_size = compress_file(path, args.delete_originals)
        total_original += original_size
        total_compressed += compressed_size
        processed += 1
        ratio = compressed_size / original_size if original_size else 0
        print(
            f"{path.relative_to(cache_root)} -> {path.name}.gz "
            f"({original_size / 1024 / 1024:.2f} MB -> {compressed_size / 1024 / 1024:.2f} MB, ratio={ratio:.3f})"
        )

    saved_mb = (total_original - total_compressed) / 1024 / 1024
    print(
        f"Compressed {processed} files under {cache_root}. "
        f"Before={total_original / 1024 / 1024:.2f} MB, after={total_compressed / 1024 / 1024:.2f} MB, saved={saved_mb:.2f} MB."
    )


if __name__ == "__main__":
    main()
