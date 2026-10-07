"""Package ownership and reproducible release contracts."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import meter
from tests import test_installer_modes

ROOT = Path(__file__).resolve().parents[1]


class PackageUpdateTests(unittest.TestCase):
    def test_package_manager_blocks_every_update_entrypoint_without_io(self):
        for manager, command in (("homebrew", "brew upgrade token-meter"),
                                 ("scoop", "scoop update token-meter"),
                                 ("winget", "winget upgrade --id Splunk.TokenMeter --exact")):
            with self.subTest(manager=manager), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "PACKAGE_MANAGER").write_text(manager + "\n")
                settings = root / "settings.json"
                original = '{"updates":{"enabled":true,"auto_install":true},"keep":1}'
                settings.write_text(original)
                status_file = root / "status.json"
                status_file.write_text(json.dumps({
                    "phase": "failed", "error_code": "install_failed",
                    "available": True, "can_update": True,
                    "latest_revision": "b" * 40, "failed_revision": "b" * 40,
                }))
                saved_status = status_file.read_bytes()
                with mock.patch.object(meter, "_SOURCE_ROOT", str(root)), \
                     mock.patch.object(meter, "_run_update_git") as git, \
                     mock.patch.object(meter.threading, "Thread") as thread:
                    status = meter.software_update_status(str(settings), str(status_file))
                    self.assertFalse(status["enabled"])
                    self.assertFalse(status["auto_install"])
                    self.assertFalse(status["available"])
                    self.assertFalse(status["can_update"])
                    self.assertIn(command, status["message"])
                    self.assertFalse(status["actions"]["check"])
                    self.assertFalse(status["actions"]["install"])
                    self.assertEqual(meter.source_checkout_path(), "")
                    meter.check_for_software_update(
                        checkout=str(root), settings_path=str(settings),
                        status_path=str(status_file),
                    )
                    self.assertFalse(meter.trigger_software_update_check(
                        str(settings), str(status_file))["ok"])
                    popen = mock.Mock()
                    self.assertFalse(meter.start_software_update(
                        popen, str(settings), str(status_file))["ok"])
                    git.assert_not_called()
                    thread.assert_not_called()
                    popen.assert_not_called()
                self.assertEqual(settings.read_text(), original)
                self.assertEqual(status_file.read_bytes(), saved_status)

    def test_unknown_marker_does_not_expose_arbitrary_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PACKAGE_MANAGER").write_text("private arbitrary content")
            with mock.patch.object(meter, "_SOURCE_ROOT", str(root)):
                status = meter.software_update_status(str(root / "settings.json"),
                                                      str(root / "status.json"))
            self.assertTrue(status["enabled"])
            self.assertNotIn("private arbitrary content", json.dumps(status))

    def test_package_settings_cannot_enable_git_updates_or_change_saved_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PACKAGE_MANAGER").write_text("homebrew\n")
            settings = root / "settings.json"
            original = '{"updates":{"enabled":true,"auto_install":false}}'
            settings.write_text(original)
            with mock.patch.object(meter, "_SOURCE_ROOT", str(root)):
                result = meter.set_update_settings({"enabled": True}, str(settings))
                self.assertFalse(result["ok"])
                self.assertIn("brew upgrade token-meter", result["error"])
            self.assertEqual(settings.read_text(), original)

    def test_disabled_package_settings_write_preserves_checkout_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "PACKAGE_MANAGER").write_text("homebrew\n")
            settings = root / "settings.json"
            original = '{"updates":{"enabled":true,"auto_install":true}}'
            settings.write_text(original)
            with mock.patch.object(meter, "_SOURCE_ROOT", str(root)):
                result = meter.set_update_settings(
                    {"enabled": False, "auto_install": False}, str(settings))
            self.assertFalse(result["ok"])
            self.assertEqual(settings.read_text(), original)

    def test_dashboard_locks_controls_when_package_manager_owns_updates(self):
        page = (ROOT / "page.html").read_text()
        self.assertIn("$('update-enabled').disabled=status.actions?.check===false", page)

    @unittest.skipUnless(os.name == "posix", "POSIX updater guard")
    def test_direct_update_helper_refuses_managed_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "update").write_bytes((ROOT / "scripts/update").read_bytes())
            (root / "PACKAGE_MANAGER").write_text("homebrew\n")
            status = root / "status.json"
            result = subprocess.run(["bash", str(root / "scripts/update"),
                                     str(root), str(status)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("brew upgrade token-meter", result.stderr)
            self.assertFalse(status.exists())


class PackageInstallerTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "POSIX archive installer integration")
    def test_archive_install_uses_release_version_instead_of_an_ancestor_git_revision(self):
        helper = test_installer_modes.InstallerModeTests()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            output = workspace / "packages"
            result = ReleasePackageTests().build(output)
            self.assertEqual(result.returncode, 0, result.stderr)
            parent = workspace / "ancestor-repository"
            parent.mkdir()
            helper.git("init", cwd=parent)
            helper.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                       "commit", "--allow-empty", "-m", "ancestor fixture", cwd=parent)
            with tarfile.open(output / "token-meter-0.1.0.tar.gz") as archive:
                archive.extractall(parent, filter="data")
            source = parent / "token-meter-0.1.0"
            env, runtime, _ = helper.installer_environment(workspace, "Darwin")
            env["TOKEN_METER_PACKAGE_MANAGER"] = "homebrew"
            installed = subprocess.run(["bash", str(source / "scripts/install"), "--backend-only"],
                                       env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertEqual((runtime / "INSTALLED_REVISION").read_text(), "0.1.0\n")

    @unittest.skipUnless(os.name == "posix", "POSIX installer integration")
    def test_homebrew_install_marks_runtime_and_manual_reinstall_clears_owner(self):
        helper = test_installer_modes.InstallerModeTests()
        with tempfile.TemporaryDirectory() as tmp:
            env, runtime, _ = helper.installer_environment(Path(tmp), "Darwin")
            env["TOKEN_METER_PACKAGE_MANAGER"] = "homebrew"
            result = subprocess.run(["bash", str(ROOT / "scripts/install"), "--backend-only"],
                                    capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((runtime / "PACKAGE_MANAGER").is_file())
            self.assertEqual((runtime / "PACKAGE_MANAGER").read_text(), "homebrew\n")
            self.assertFalse((runtime / "SOURCE_CHECKOUT").exists())
            (runtime / "RELEASE_VERSION").write_text("0.1.0\n")
            del env["TOKEN_METER_PACKAGE_MANAGER"]
            result = subprocess.run(["bash", str(ROOT / "scripts/install"), "--backend-only"],
                                    capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((runtime / "PACKAGE_MANAGER").exists())
            self.assertFalse((runtime / "RELEASE_VERSION").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX package refresh integration")
    def test_homebrew_refresh_only_updates_owned_runtime_and_preserves_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            helper = root / "scripts/package-homebrew"
            helper.write_bytes((ROOT / "scripts/package-homebrew").read_bytes())
            install = root / "scripts/install"
            install.write_text('#!/bin/bash\nprintf "%s %s" "$TOKEN_METER_PACKAGE_MANAGER" "$*"\n')
            install.chmod(0o755)
            runtime = root / "runtime"
            runtime.mkdir()
            env = {**os.environ, "TOKEN_METER_INSTALL_ROOT": str(runtime)}
            for manager in (None, "scoop", "homebrew"):
                if manager:
                    (runtime / "PACKAGE_MANAGER").write_text(manager + "\n")
                (runtime / "INSTALL_MODE").write_text("backend-only\n")
                result = subprocess.run(["bash", str(helper), "refresh"], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "homebrew --backend-only" if manager == "homebrew" else "")


class ReleasePackageTests(unittest.TestCase):
    def build(self, directory, version="0.1.0", repository="splunk/token-meter"):
        return subprocess.run([sys.executable, str(ROOT / "scripts/package-release.py"),
                               "--version", version, "--repository", repository,
                               "--output", str(directory)], capture_output=True, text=True)

    def test_release_artifacts_are_reproducible_and_manifests_pin_their_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a", Path(tmp) / "b"
            result = self.build(first)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.build(second)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("token-meter-0.1.0.tar.gz", "token-meter-0.1.0.zip",
                         "token-meter.rb", "token-meter.json", "SHA256SUMS"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            manifest = json.loads((first / "token-meter.json").read_text())
            self.assertEqual(manifest["version"], "0.1.0")
            self.assertEqual(manifest["hash"], hashlib.sha256(
                (first / "token-meter-0.1.0.zip").read_bytes()).hexdigest())
            self.assertIn("/releases/download/v0.1.0/", manifest["url"])
            self.assertEqual(set(manifest["depends"]), {"git", "python"})
            self.assertIn("$global", "\n".join(manifest["pre_install"]))
            self.assertNotIn("skip", manifest["hash"])
            formula = (first / "token-meter.rb").read_text()
            self.assertIn(hashlib.sha256(
                (first / "token-meter-0.1.0.tar.gz").read_bytes()).hexdigest(), formula)
            with zipfile.ZipFile(first / "token-meter-0.1.0.zip") as archive:
                self.assertIn("token-meter-0.1.0/scripts/install-windows.ps1", archive.namelist())
                self.assertEqual(archive.read("token-meter-0.1.0/RELEASE_VERSION"), b"0.1.0\n")
                self.assertFalse(any("__pycache__" in name or "/.git/" in name
                                     for name in archive.namelist()))
            with tarfile.open(first / "token-meter-0.1.0.tar.gz") as archive:
                self.assertTrue(archive.getmember(
                    "token-meter-0.1.0/scripts/install").mode & 0o111)

    def test_release_builder_rejects_version_and_repository_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version, repo in (("../../escape", "splunk/token-meter"),
                                  ("0.1.0\nmalicious", "splunk/token-meter"),
                                  ("0.1.0", "owner/repo\nmalicious")):
                with self.subTest(version=version, repo=repo):
                    result = self.build(Path(tmp) / "out", version, repo)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((Path(tmp) / "out").exists())

    def test_winget_manifest_uses_the_real_installer_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            installer = directory / "token-meter-0.1.0-windows-setup.exe"
            installer.write_bytes(b"MZtest-installer-fixture")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/package-release.py"),
                "--version", "0.1.0", "--output", str(directory / "out"),
                "--winget-installer", str(installer),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((directory / "out/winget/Splunk.TokenMeter.yaml").read_text())
            self.assertEqual(manifest["Scope"], "user")
            self.assertEqual(manifest["InstallerType"], "inno")
            entry = manifest["Installers"][0]
            self.assertEqual(entry["InstallerSha256"], hashlib.sha256(installer.read_bytes()).hexdigest())
            self.assertEqual(entry["Architecture"], "x64")
            self.assertEqual({item["PackageIdentifier"] for item in
                              manifest["Dependencies"]["PackageDependencies"]},
                             {"Git.MinGit", "Python.Python.3.14"})


class ReleasePublishTests(unittest.TestCase):
    def publisher(self):
        spec = importlib.util.spec_from_file_location(
            "publish_package_assets", ROOT / "scripts/publish-package-assets.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_partial_upload_retry_checks_existing_bytes_and_uploads_only_missing(self):
        publisher = self.publisher()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing, missing = root / "source.zip", root / "installer.exe"
            existing.write_bytes(b"published archive")
            missing.write_bytes(b"missing installer")
            uploads = []

            def gh(arguments):
                if arguments[:2] == ["release", "view"]:
                    return json.dumps({"assets": [{"name": existing.name}]})
                if arguments[:2] == ["release", "download"]:
                    destination = Path(arguments[arguments.index("--dir") + 1])
                    (destination / existing.name).write_bytes(existing.read_bytes())
                    return ""
                if arguments[:2] == ["release", "upload"]:
                    uploads.append(Path(arguments[3]).name)
                    return ""
                self.fail(arguments)

            with mock.patch.object(publisher, "run_gh", side_effect=gh):
                publisher.publish_assets("splunk/token-meter", "v0.1.0", [existing, missing])
            self.assertEqual(uploads, [missing.name])

    def test_existing_asset_mismatch_fails_before_uploading_anything(self):
        publisher = self.publisher()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing, existing = root / "source.zip", root / "installer.exe"
            missing.write_bytes(b"archive")
            existing.write_bytes(b"changed installer")
            uploads = []

            def gh(arguments):
                if arguments[:2] == ["release", "view"]:
                    return json.dumps({"assets": [{"name": existing.name}]})
                if arguments[:2] == ["release", "download"]:
                    destination = Path(arguments[arguments.index("--dir") + 1])
                    (destination / existing.name).write_bytes(b"already published installer")
                    return ""
                uploads.append(arguments)
                return ""

            with mock.patch.object(publisher, "run_gh", side_effect=gh):
                with self.assertRaisesRegex(ValueError, "differs"):
                    publisher.publish_assets("splunk/token-meter", "v0.1.0", [missing, existing])
            self.assertEqual(uploads, [])


if __name__ == "__main__":
    unittest.main()
