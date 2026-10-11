#!/usr/bin/env python3
"""safexml Version Synchronization Utility.

Ensures strict version parity across manifests:
- Cargo.toml (root package)
- pyproject.toml (Python package)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CARGO_PATH = REPO_ROOT / "Cargo.toml"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def normalize_version(ver: str) -> str:
    """Normalize version string by stripping leading 'v'."""
    v = ver.strip().lstrip("v")
    if not re.match(r"^\d+\.\d+\.\d+.*$", v):
        raise ValueError(f"Invalid semantic version format: '{ver}'")
    return v


def get_cargo_version() -> str:
    content = CARGO_PATH.read_text(encoding="utf-8")
    m = re.search(r'(?ms)\[package\].*?^version\s*=\s*"([^"]+)"', content)
    if not m:
        raise RuntimeError("Could not find [package].version in Cargo.toml")
    return m.group(1)


def get_pyproject_version() -> str:
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    m = re.search(r'(?ms)\[project\].*?^version\s*=\s*"([^"]+)"', content)
    if not m:
        raise RuntimeError("Could not find [project].version in pyproject.toml")
    return m.group(1)


def set_cargo_version(new_ver: str) -> None:
    content = CARGO_PATH.read_text(encoding="utf-8")
    new_content = re.sub(
        r'(?ms)(\[package\].*?^version\s*=\s*)"[^"]+"',
        rf'\g<1>"{new_ver}"',
        content,
        count=1,
    )
    CARGO_PATH.write_text(new_content, encoding="utf-8")


def set_pyproject_version(new_ver: str) -> None:
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    new_content = re.sub(
        r'(?ms)(\[project\].*?^version\s*=\s*)"[^"]+"',
        rf'\g<1>"{new_ver}"',
        content,
        count=1,
    )
    PYPROJECT_PATH.write_text(new_content, encoding="utf-8")


def check_versions() -> bool:
    c_ver = get_cargo_version()
    p_ver = get_pyproject_version()
    if c_ver != p_ver:
        print(f"Version mismatch detected:\n  Cargo.toml:     {c_ver}\n  pyproject.toml: {p_ver}", file=sys.stderr)
        return False
    print(f"Version parity confirmed: {c_ver}")
    return True


def sync_all(target_ver: str) -> None:
    ver = normalize_version(target_ver)
    print(f"Setting version across manifests to: {ver}")
    set_cargo_version(ver)
    set_pyproject_version(ver)
    print("Version synchronization complete.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync or check safexml version parity.")
    parser.add_argument("--check", action="store_true", help="Check version parity across manifests")
    parser.add_argument("--set", dest="set_version", metavar="VERSION", help="Set new version across all manifests")
    parser.add_argument("--get", action="store_true", help="Print current version")

    args = parser.parse_args()

    if args.get:
        print(get_cargo_version())
        return 0

    if args.check:
        return 0 if check_versions() else 1

    if args.set_version:
        sync_all(args.set_version)
        return 0 if check_versions() else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
