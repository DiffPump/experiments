"""
Download MPS instances from MIPLIB.

Usage
-----
    python experiments/instances/download.py experiments/instances/sample.csv
    python experiments/instances/download.py experiments/instances/instances.csv --out data/mps
    python experiments/instances/download.py experiments/instances/instances.csv --jobs 8

The script reads instance names from the first column of a CSV file (header
row is skipped), downloads each <name>.mps.gz from MIPLIB 2017, decompresses
it, and writes <name>.mps to the output directory.

Default output directory: miplib{version}/mps/ next to the CSV file.
Already-downloaded files are skipped unless --force is given.

CSV format (see instances.csv / sample.csv)
-------------------------------------------
    Instance,Variables,Integers,Binaries,Type
    noswot,128,25,75,MIP
    ...

Only the first column (Instance name) is used; the rest are ignored.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# Base URL template — fill in {version} and {name}
_URL_TEMPLATE = "https://miplib.zib.de/WebData/instances/{name}.mps.gz"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download MIPLIB instances as .mps files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("csv", help="CSV file with instance names in the first column")
    p.add_argument(
        "--out",
        default=None,
        help="Output directory (default: miplib{version}/mps relative to CSV location)",
    )
    p.add_argument("--version", default="2017", help="MIPLIB version tag (used in default output path)")
    p.add_argument("--jobs", type=int, default=1, help="Parallel download workers")
    p.add_argument("--force", action="store_true", help="Re-download even if file exists")
    p.add_argument("--timeout", type=int, default=60, help="HTTP timeout per request (seconds)")
    p.add_argument("--retries", type=int, default=3, help="Retry attempts on failure")
    p.add_argument("--delay", type=float, default=0.2, help="Seconds to wait between requests (serial mode)")
    return p.parse_args(argv)


def read_instance_names(csv_path: Path) -> list[str]:
    names: list[str] = []
    with csv_path.open(newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0 or not row:
                continue  # skip header and blank lines
            name = row[0].strip()
            if name:
                names.append(name)
    return names


def download_one(
    name: str,
    out_dir: Path,
    *,
    timeout: int,
    retries: int,
    force: bool,
) -> tuple[str, str]:
    """
    Download and decompress one instance.

    Returns (name, status) where status is one of:
      "skipped"  — already exists and --force not set
      "ok"       — downloaded successfully
      "error: …" — failure message
    """
    dest = out_dir / f"{name}.mps"
    if dest.exists() and not force:
        return name, "skipped"

    url = _URL_TEMPLATE.format(name=name)
    gz_path = out_dir / f"{name}.mps.gz"

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                gz_path.write_bytes(resp.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                gz_path.unlink(missing_ok=True)
                return name, f"error: HTTP 404 (not in MIPLIB {url})"
            if attempt == retries:
                gz_path.unlink(missing_ok=True)
                return name, f"error: HTTP {exc.code} after {retries} attempts"
            time.sleep(1.5 ** attempt)
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                gz_path.unlink(missing_ok=True)
                return name, f"error: {exc}"
            time.sleep(1.5 ** attempt)

    # Decompress
    try:
        with gzip.open(gz_path, "rb") as f_in, dest.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        gz_path.unlink()
    except Exception as exc:  # noqa: BLE001
        gz_path.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        return name, f"error: decompression failed — {exc}"

    return name, "ok"


def _worker(args: tuple) -> tuple[str, str]:
    return download_one(*args[0], **args[1])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    names = read_instance_names(csv_path)
    if not names:
        print("Error: no instance names found in CSV.", file=sys.stderr)
        return 1

    out_dir = (
        Path(args.out).resolve()
        if args.out
        else csv_path.parent / f"miplib{args.version}" / "mps"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(names)
    print(f"Instances : {total}")
    print(f"Output    : {out_dir}")
    print(f"Workers   : {args.jobs}")
    print()

    ok = skipped = errors = 0

    if args.jobs > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        worker_args = [
            ((name, out_dir), {"timeout": args.timeout, "retries": args.retries, "force": args.force})
            for name in names
        ]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(_worker, a): a[0][0] for a in worker_args}
            done = 0
            for fut in as_completed(futures):
                name, status = fut.result()
                done += 1
                _print_status(name, status, done, total)
                if status == "ok":
                    ok += 1
                elif status == "skipped":
                    skipped += 1
                else:
                    errors += 1
    else:
        for i, name in enumerate(names, 1):
            name, status = download_one(
                name, out_dir,
                timeout=args.timeout,
                retries=args.retries,
                force=args.force,
            )
            _print_status(name, status, i, total)
            if status == "ok":
                ok += 1
            elif status == "skipped":
                skipped += 1
            else:
                errors += 1
            if i < total:
                time.sleep(args.delay)

    print()
    print(f"Done — downloaded: {ok}  skipped: {skipped}  errors: {errors}")
    return 0 if errors == 0 else 2


def _print_status(name: str, status: str, done: int, total: int) -> None:
    tag = {"ok": "OK", "skipped": "SKIP"}.get(status, "FAIL")
    detail = "" if status in ("ok", "skipped") else f"  ({status})"
    print(f"  [{done:>{len(str(total))}}/{total}] {tag:<4}  {name}{detail}")


if __name__ == "__main__":
    sys.exit(main())
