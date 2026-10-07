# Package manager candidates

Tracks [Homebrew #71](https://github.com/splunk/token-meter/issues/71),
[Scoop #72](https://github.com/splunk/token-meter/issues/72), and
[WinGet #73](https://github.com/splunk/token-meter/issues/73). Scoop and WinGet
are alternatives for maintainer selection; preparing both does not commit the
project to publishing both. Windows execution is a separate acceptance gate.

## Ownership and lifecycle

The package definitions reuse the existing manifest-driven installers. They stage
the runtime in the normal per-user location and write an allowlisted
`PACKAGE_MANAGER` marker before starting the service. Package-managed installs
skip the managed Git checkout and do not fetch, pull, or use the Git updater.
Dashboard update controls are disabled with the package manager's upgrade command.
Saved checkout-install update preferences are preserved. A normal checkout
reinstall clears ownership and restores those preferences.

Homebrew initially installs source into its Cellar. `token-meter install`
activates the existing LaunchAgents. After upgrade/reinstall, run `token-meter install`
again to stage and restart that version; it preserves backend-only mode. This explicit
activation is outside Homebrew's isolated post-install sandbox. Run `token-meter uninstall` before `brew uninstall` to stop
the services; the staged runtime and settings are retained for recovery.
The initial formula targets macOS; Linux Homebrew is outside this candidate.

Scoop uses Git/Python dependencies from Scoop and the existing current-user Run
entry. The manifest rejects global installs. Updates leave the old runtime intact
until the transactional installer stages and replaces it, preserving backend-only
mode. Its uninstall hook executes only during `scoop uninstall`, and removes the
runtime only when Scoop still owns it. WinGet uses an Inno Setup executable with
`PrivilegesRequired=lowest`, installs its source under the current user's Programs
directory, and uses the same helper with `winget` ownership. Its initial manifest
targets Windows x64; ARM64 and x86 require separate target evidence and artifacts.
Both uninstall paths preserve settings and coding-agent evidence outside the runtime,
check process/startup ownership, and reject reparse points before removing the runtime.
Package installs fail when declared prerequisites are absent; they do not fall back
to a different package manager to install them.

## Build local release artifacts

From the candidate checkout with Python 3.14:

```bash
python3 scripts/package-release.py --version 0.0.0 --output /tmp/token-meter-packages
```

`0.0.0` is a local test version, not a published release. Outputs are a deterministic
manifest-owned `.tar.gz` and `.zip`, `SHA256SUMS`, a checksum-pinned `token-meter.rb`,
and `token-meter.json`. Each archive contains `RELEASE_VERSION`. No settings,
traces, Git metadata, or generated caches are part of the manifest. The builder
excludes Python caches and Finder metadata and rejects logs or build directories
in manifest-owned trees. Keep its output outside the checkout.
The HEAD-only formula is `packaging/homebrew/token-meter.rb`; copy it to the Splunk
tap's flat root as `token-meter.rb` for an initial upstream HEAD package.

## Test Homebrew on macOS

Use a local tap so unpublished source can be installed. Generate the local package
above, then create the tap and replace only its test URL:

```bash
brew tap-new --no-git token-meter/local
cp /tmp/token-meter-packages/token-meter.rb "$(brew --repository token-meter/local)/Formula/token-meter.rb"
python3 - <<'PY'
import subprocess
from pathlib import Path
tap = Path(subprocess.check_output(['brew', '--repository', 'token-meter/local'], text=True).strip())
formula = tap / 'Formula/token-meter.rb'
contents = formula.read_text().replace(
    'https://github.com/splunk/token-meter/releases/download/v0.0.0/token-meter-0.0.0.tar.gz',
    'file:///tmp/token-meter-packages/token-meter-0.0.0.tar.gz')
formula.write_text(contents)
PY
brew install --build-from-source token-meter/local/token-meter
brew test token-meter/local/token-meter
token-meter install
curl -fsS http://127.0.0.1:8722/health
curl -fsS http://127.0.0.1:8722/menubar
curl -fsS http://127.0.0.1:8722/updates/status
brew reinstall token-meter/local/token-meter
token-meter install
```

Verify both LaunchAgents, the visible companion, dashboard at 1440 and 1024 pixels,
and manifest parity between the formula's `libexec` and staged runtime. Update status
must have `enabled=false`, `auto_install=false`, `available=false`, and
`can_update=false`, with a `brew upgrade token-meter` instruction. Reinstall must
refresh the runtime and preserve its install mode. To exercise an actual version
upgrade, build a second local version, change the tap URL and checksum together,
then run `brew upgrade token-meter/local/token-meter` followed by `token-meter install`
and verify parity again.
Do not run `brew upgrade` before the second descriptor exists.

Clean up with `token-meter uninstall`, `brew uninstall token-meter/local/token-meter`,
and `brew untap token-meter/local`. Restore a checkout installation with
`./scripts/install` and recheck both endpoints/services. Preserve existing settings.

## Test Scoop on Windows

Use a disposable Windows user or record the previous installation so it can be
restored afterward. Obtain the complete candidate checkout and transfer the generated
archive and descriptor. Install Scoop through its normal user setup, then:

```powershell
scoop install git python
$packages = Join-Path $env:TEMP 'token-meter-packages'
# Put token-meter-0.0.0.zip and token-meter.json in $packages.
# Serve the folder locally; keep this running in a second terminal:
python -m http.server 8765 --bind 127.0.0.1 --directory $packages
```

In the first terminal:

```powershell
$packages = Join-Path $env:TEMP 'token-meter-packages'
$manifest = Get-Content (Join-Path $packages 'token-meter.json') -Raw | ConvertFrom-Json
$manifest.url = 'http://127.0.0.1:8765/token-meter-0.0.0.zip'
$manifest | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $packages 'token-meter.json') -Encoding UTF8
scoop install (Join-Path $packages 'token-meter.json')
Invoke-RestMethod http://127.0.0.1:8722/health
Invoke-RestMethod http://127.0.0.1:8722/menubar
Invoke-RestMethod http://127.0.0.1:8722/updates/status
Get-Content "$env:LOCALAPPDATA\Token Meter\runtime\PACKAGE_MANAGER"
powershell.exe -NoLogo -NoProfile -File "$env:LOCALAPPDATA\Token Meter\runtime\scripts\run-tray.ps1" -SmokeTest
```

The archive hash remains unchanged after replacing the local test URL. Expect marker
`scoop`, ready endpoints, a working notification icon, and disabled Git updating.
Verify the HKCU Run entry and logout/login startup. Test full and backend-only modes;
verify package refresh preserves the latter. Run `python -m token_meter.packaging
parity` from the extracted archive against the staged runtime and source manifest.
Parse every candidate PowerShell script on Windows with `[scriptblock]::Create`.

For the update test, generate a second version and descriptor, point its URL to the
local server, replace the installed local manifest file, and run `scoop update
token-meter`. If using a test bucket, commit both manifest revisions to that bucket
and run `scoop update; scoop update token-meter`. Confirm the new release version,
byte parity, preserved settings, one server, and one startup entry. A published
bucket follows the same steps without the local URL replacement.

Run `scoop uninstall token-meter`. Confirm server/tray stop, HKCU startup removal,
runtime removal, preserved settings, and preserved Git/Python dependencies. Negative
tests: global install must fail; after a manual reinstall, Scoop uninstall must leave
the manual runtime/startup alone; a reparse point must prevent recursive deletion.

## Test WinGet on Windows

Install Python, Git, and Inno Setup 6 using the Windows tools you normally use.
Generate the source archive and extract it, then build from the checkout:

```powershell
$packages = Join-Path $env:TEMP 'token-meter-packages'
Expand-Archive (Join-Path $packages 'token-meter-0.0.0.zip') (Join-Path $packages 'source')
.\scripts\build-windows-installer.ps1 -Version 0.0.0 -SourceRoot (Join-Path $packages 'source\token-meter-0.0.0') -OutputRoot $packages
python .\scripts\package-release.py --version 0.0.0 --output $packages --winget-installer (Join-Path $packages 'token-meter-0.0.0-windows-setup.exe')
winget validate --manifest (Join-Path $packages 'winget')
```

Enable local manifests for development with `winget settings --enable LocalManifestFiles`
(this WinGet development setting may require an administrator), or test the executable
directly on a standard user account. Package installation itself must not elevate.
For the manifest test, serve `$packages` over localhost as above, replace
`Installers[0].InstallerUrl` in `winget/Splunk.TokenMeter.yaml` with the local
installer URL without changing its hash, then run:

```powershell
winget install --manifest (Join-Path $packages 'winget') --scope user
Invoke-RestMethod http://127.0.0.1:8722/health
Invoke-RestMethod http://127.0.0.1:8722/menubar
Invoke-RestMethod http://127.0.0.1:8722/updates/status
winget list --id Splunk.TokenMeter --exact
winget uninstall --id Splunk.TokenMeter --exact
```

Expect marker `winget` and a `winget upgrade --id Splunk.TokenMeter --exact`
instruction. Repeat startup, tray, parity, preservation, and ownership tests from
Scoop. Build a second version and install its local manifest to test Inno's in-place
upgrade. The public `winget upgrade --id Splunk.TokenMeter --exact` resolution step
requires both versions in a maintainer-selected source; local-manifest upgrade alone
does not prove public catalog behavior. WinGet community review and installer signing
are publication gates, not evidence available from macOS source tests.

## Maintainer release and publication

Choose a stable `vMAJOR.MINOR.PATCH` tag and publish its GitHub release only after
the platform gates pass. `package-release.yml` builds source archives, compiles
the Windows installer on a Windows runner, generates all descriptors and checksums,
and uploads them to that release. The runner must supply Inno Setup 6. Manual workflow
runs accept an existing tag and upload Actions artifacts only; they do not publish
a release or update package repositories. Publication first downloads existing
same-name assets and verifies their SHA256 against the build, then uploads only
missing assets. Matching assets are retained; differing bytes stop publication
before any missing upload. After a partial upload, rerun failed jobs using the
original Actions artifact. Rebuilding an Inno executable can produce different
bytes; use the original artifact rather than overwriting a published installer.

Configure `HOMEBREW_TAP_REPOSITORY=splunk/homebrew-tap` and, only if Scoop is selected,
`SCOOP_BUCKET_REPOSITORY=<chosen owner/repository>`. Add a narrowly scoped
`PACKAGE_REPOSITORY_TOKEN` with branch push and pull-request permissions on those
repositories. The workflow creates version-specific update PRs, never merges them,
and skips publication when configuration is absent. The tap uses `token-meter.rb`
at its flat root; Scoop uses `bucket/token-meter.json`. Select the bucket and inspect
its contribution policy before enabling that job. No official Scoop bucket is assumed.
WinGet submission remains a maintainer action: inspect and submit the generated
manifest through `wingetcreate` or a PR to `microsoft/winget-pkgs` after Windows
validation. The proposed `Splunk.TokenMeter` identifier and publisher need approval.

Primary specifications: [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook),
[Scoop manifests](https://github.com/ScoopInstaller/Scoop/wiki/App-Manifests), and
[WinGet manifests](https://learn.microsoft.com/en-us/windows/package-manager/package/manifest).
