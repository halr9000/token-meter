#!/usr/bin/env python3
"""Build deterministic manifest-owned source releases and package descriptors."""

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from token_meter.packaging import load_manifest, manifest_source_files


def build(version, repository, output, winget_installer=None):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Version must be a stable MAJOR.MINOR.PATCH number.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository must be an owner/name pair.")
    paths = manifest_source_files(ROOT, load_manifest(ROOT / "runtime-manifest.txt"))
    files = {}
    for relative in paths:
        path = ROOT / relative
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Release files must remain inside the source root.")
        if "__pycache__" in Path(relative).parts or path.name == ".DS_Store" or path.suffix == ".pyc":
            continue
        if any(part in {".git", ".build"} for part in Path(relative).parts) or path.suffix == ".log":
            raise ValueError("Remove generated files from manifest-owned trees before packaging.")
        files[relative] = (path.read_bytes(), 0o755 if path.stat().st_mode & 0o111 else 0o644)
    files["RELEASE_VERSION"] = ((version + "\n").encode(), 0o644)
    prefix = "token-meter-" + version
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tar_path = output / (prefix + ".tar.gz")
    zip_path = output / (prefix + ".zip")
    with tar_path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for relative, (data, mode) in sorted(files.items()):
                entry = tarfile.TarInfo(prefix + "/" + relative)
                entry.size, entry.mode, entry.mtime = len(data), mode, 0
                archive.addfile(entry, io.BytesIO(data))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, (data, mode) in sorted(files.items()):
            entry = zipfile.ZipInfo(prefix + "/" + relative, date_time=(1980, 1, 1, 0, 0, 0))
            entry.external_attr = (0o100000 | mode) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (tar_path, zip_path)}
    base_url = f"https://github.com/{repository}/releases/download/v{version}/"
    formula = (ROOT / "packaging/homebrew/token-meter.rb").read_text()
    formula = formula.replace('  license "MIT"',
                              f'  url "{base_url}{tar_path.name}"\n'
                              f'  sha256 "{hashes[tar_path.name]}"\n'
                              f'  license "MIT"')
    formula = formula.replace("https://github.com/splunk/token-meter", f"https://github.com/{repository}")
    (output / "token-meter.rb").write_text(formula, encoding="utf-8")
    manifest = {
        "version": version,
        "description": "Local coding-agent usage dashboard and Windows tray companion",
        "homepage": f"https://github.com/{repository}",
        "license": "MIT",
        "url": base_url + zip_path.name,
        "hash": hashes[zip_path.name],
        "extract_dir": prefix,
        "depends": ["git", "python"],
        "pre_install": ["if ($global) { throw 'Token Meter supports per-user Scoop installation only.' }"],
        "post_install": ["& \"$dir\\scripts\\package-windows.ps1\" -Action install -PackageManager scoop"],
        "uninstaller": {"script": ["if ($cmd -eq 'uninstall') { & \"$dir\\scripts\\package-windows.ps1\" -Action uninstall -PackageManager scoop }"]},
        "checkver": {"github": f"https://github.com/{repository}"},
        "autoupdate": {
            "url": f"https://github.com/{repository}/releases/download/v$version/token-meter-$version.zip",
            "extract_dir": "token-meter-$version",
            "hash": {"url": f"https://github.com/{repository}/releases/download/v$version/SHA256SUMS"},
        },
    }
    (output / "token-meter.json").write_text(json.dumps(manifest, indent=4) + "\n", encoding="utf-8")
    if winget_installer is not None:
        installer = Path(winget_installer)
        expected_name = f"token-meter-{version}-windows-setup.exe"
        if installer.name != expected_name or not installer.read_bytes().startswith(b"MZ"):
            raise ValueError("WinGet requires the version-matched Windows installer executable.")
        checksum = hashlib.sha256(installer.read_bytes()).hexdigest()
        hashes[expected_name] = checksum
        winget = {
            "PackageIdentifier": "Splunk.TokenMeter",
            "PackageVersion": version,
            "PackageLocale": "en-US",
            "Publisher": "Splunk",
            "PackageName": "Token Meter",
            "License": "MIT",
            "ShortDescription": "Local coding-agent usage dashboard and Windows tray companion",
            "PackageUrl": f"https://github.com/{repository}",
            "InstallerType": "inno",
            "Scope": "user",
            "UpgradeBehavior": "install",
            "Dependencies": {"PackageDependencies": [
                {"PackageIdentifier": "Git.MinGit"},
                {"PackageIdentifier": "Python.Python.3.14"},
            ]},
            "Installers": [{"Architecture": "x64", "InstallerUrl": base_url + expected_name,
                            "InstallerSha256": checksum}],
            "ManifestType": "singleton",
            "ManifestVersion": "1.12.0",
        }
        (output / "winget").mkdir(exist_ok=True)
        # JSON is a YAML subset; WinGet accepts the ordinary YAML scalar/map types.
        (output / "winget/Splunk.TokenMeter.yaml").write_text(
            json.dumps(winget, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text("".join(f"{value}  {name}\n" for name, value in sorted(hashes.items())), encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", default="splunk/token-meter")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--winget-installer", type=Path)
    arguments = parser.parse_args()
    try:
        build(arguments.version, arguments.repository, arguments.output, arguments.winget_installer)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
