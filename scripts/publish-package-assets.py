#!/usr/bin/env python3
"""Attach missing release assets without replacing previously published bytes."""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


def run_gh(arguments):
    return subprocess.run(["gh", *arguments], check=True, text=True,
                          stdout=subprocess.PIPE).stdout


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def publish_assets(repository, tag, paths):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must be owner/name")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("tag must be vMAJOR.MINOR.PATCH")
    paths = [Path(path).resolve() for path in paths]
    if not paths or any(not path.is_file() for path in paths):
        raise ValueError("every release asset must be an existing file")
    if len({path.name for path in paths}) != len(paths):
        raise ValueError("release asset names must be unique")
    release = json.loads(run_gh(["release", "view", tag, "--repo", repository,
                                "--json", "assets"]))
    names = {asset["name"] for asset in release["assets"]}
    missing = []
    with tempfile.TemporaryDirectory(prefix="token-meter-release-") as tmp:
        directory = Path(tmp)
        # Reconcile every existing asset before uploading any missing file.
        # A partial upload can then be retried using the identical build artifact.
        for path in paths:
            if path.name not in names:
                missing.append(path)
                continue
            run_gh(["release", "download", tag, "--repo", repository,
                    "--pattern", path.name, "--dir", str(directory)])
            if checksum(directory / path.name) != checksum(path):
                raise ValueError(f"published asset {path.name} differs; use the original build artifacts")
        for path in missing:
            run_gh(["release", "upload", tag, str(path), "--repo", repository])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("assets", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        publish_assets(args.repository, args.tag, args.assets)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Release asset publication failed: {error}\n")


if __name__ == "__main__":
    main()
