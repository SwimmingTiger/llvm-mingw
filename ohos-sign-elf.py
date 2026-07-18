#!/usr/bin/env python3
"""Sign/unsign ELF files under a directory with binary-sign-tool."""

import argparse
import os
import subprocess
import sys

BINARY_SIGN_TOOL = "binary-sign-tool"
LLVM_OBJCOPY = "llvm-objcopy"


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

    for dirpath, dirnames, filenames in os.walk(args.directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.islink(filepath):
                continue
            if not is_elf(filepath):
                continue
            process_file(filepath, do_unsign, do_sign)


if __name__ == "__main__":
    main()
