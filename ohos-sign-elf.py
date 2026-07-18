#!/usr/bin/env python3
"""Sign/unsign ELF files under a directory with binary-sign-tool."""

import argparse
import concurrent.futures
import os
import subprocess
import sys
import threading

BINARY_SIGN_TOOL = "binary-sign-tool"
LLVM_OBJCOPY = "llvm-objcopy"
MAX_WORKERS = min(os.cpu_count() or 1, 8)


def is_elf(filepath: str) -> bool:
    try:
        with open(filepath, "rb") as f:
            magic = f.read(4)
    except OSError:
        return False
    return magic == b"\x7fELF"


def unsign_elf(filepath: str) -> None:
    cmd = [
        LLVM_OBJCOPY,
        "--remove-section", ".codesign",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAILED: {filepath} (unsign): {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"UNSIGNED: {filepath}")
    return True


def sign_elf(filepath: str) -> None:
    cmd = [
        BINARY_SIGN_TOOL,
        "sign",
        "-inFile", filepath,
        "-outFile", filepath,
        "-selfSign", "1",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAILED: {filepath} (sign): {result.stderr.strip()}", file=sys.stderr)
    else:
        print(f"SIGNED: {filepath}")


def process_file(filepath: str, do_unsign: bool, do_sign: bool) -> None:
    if do_unsign:
        unsign_elf(filepath)
    if do_sign:
        sign_elf(filepath)


def walk_and_submit(path: str, sign_executor: concurrent.futures.ThreadPoolExecutor,
                    do_unsign: bool, do_sign: bool,
                    scan_pool: concurrent.futures.ThreadPoolExecutor,
                    scan_slots: threading.Semaphore) -> None:
    """Walk a directory tree, offloading subdirectories to the scan pool when slots
    are available, and submit ELF files to the sign pool."""
    try:
        if os.path.isfile(path):
            if not os.path.islink(path) and is_elf(path):
                sign_executor.submit(process_file, path, do_unsign, do_sign)
            return
        for dirpath, dirnames, filenames in os.walk(path):
            # Try to offload subdirectories to idle scan threads.
            for dirname in list(dirnames):
                subdir = os.path.join(dirpath, dirname)
                if scan_slots.acquire(blocking=False):
                    dirnames.remove(dirname)
                    scan_pool.submit(
                        walk_and_submit, subdir,
                        sign_executor, do_unsign, do_sign,
                        scan_pool, scan_slots,
                    )
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.islink(filepath):
                    continue
                if not is_elf(filepath):
                    continue
                sign_executor.submit(process_file, filepath, do_unsign, do_sign)
    finally:
        scan_slots.release()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sign or unsign ELF files using binary-sign-tool."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--unsign", action="store_true",
        help="Remove .codesign section via llvm-objcopy"
    )
    group.add_argument(
        "--resign", action="store_true",
        help="Remove .codesign section then re-sign"
    )
    parser.add_argument("directory", help="Root directory to scan")
    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    do_unsign = args.unsign or args.resign
    do_sign = not args.unsign  # sign by default, or on --resign

    print(f"Scanning and processing with up to {MAX_WORKERS} threads")

    scan_slots = threading.Semaphore(MAX_WORKERS)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as sign_pool:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as scan_pool:
            futures = []
            for entry in os.listdir(args.directory):
                entry_path = os.path.join(args.directory, entry)
                scan_slots.acquire()
                futures.append(
                    scan_pool.submit(
                        walk_and_submit, entry_path,
                        sign_pool, do_unsign, do_sign,
                        scan_pool, scan_slots,
                    )
                )
            concurrent.futures.wait(futures)


if __name__ == "__main__":
    main()
