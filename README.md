<p align="center">
  <img src="images/token-meter-header.png" alt="Token Meter — local-first observability for AI coding agents" width="900">
</p>

<p align="center">
  <a href="https://www.splunk.com/en_us/blog/artificial-intelligence/token-meter-a-live-cost-meter-for-your-coding-agents.html">📝 Launch blog</a>
  · <a href="https://splunk.github.io/token-meter/">🌐 Website</a>
  · <a href="https://www.google.com/search?q=site%3Asplunk.com+tokenomics">📚 Learn Tokenomics</a>
</p>

Token Meter is an open-source, local-first usage and cost dashboard for AI
coding agents. It shows token usage, estimated cost, context pressure, time, and
tool activity for **Claude, Codex, Cursor, OpenCode, Kiro, and Pi** in one place.

- **Local only.** Python standard library, no API keys, no telemetry.
- **Honest numbers.** Estimates are labelled; missing evidence stays unavailable, never zero.

## Quick Start

### macOS or Linux

```bash
git clone https://github.com/splunk/token-meter.git
./token-meter/scripts/install
```

This starts the local server and native companion, and enables automatic
startup. Add `--backend-only` to skip the menu-bar/tray companion.

### Windows

> **Beta:** the Windows extension is still in beta.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command '$p=Join-Path $env:TEMP "token-meter-bootstrap.ps1"; try { Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/splunk/token-meter/main/scripts/bootstrap-windows.ps1" -OutFile $p; & $p } finally { Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue }'
```

The bootstrap uses WinGet (App Installer) to add any missing Git and Python,
with no administrator access. From a checkout, run `.\scripts\install-windows.cmd`.
Add `-BackendOnly` (`& $p -BackendOnly`) to skip the notification-area companion.

Uninstall:
`powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Token Meter\runtime\scripts\uninstall-windows.ps1"`

### Open the dashboard

Go to [http://127.0.0.1:8722](http://127.0.0.1:8722), start an agent run, and
pick it under **Sessions**. Requirements, updates, uninstall, and
troubleshooting are in the [User guide](specs/USER_GUIDE.md).

## Platforms

| Platform | Status | Companion |
| --- | --- | --- |
| macOS | Supported | Menu bar |
| Linux | Supported | AppIndicator tray |
| Windows | Beta | Notification area |

Runtimes: Claude Code and Desktop (Agent/Cowork), Codex CLI and desktop, Cursor
Agent/Composer, OpenCode, Kiro, and Pi. Only sessions stored locally are visible.

## Package managers (experimental)

The repository includes a macOS Homebrew formula, a Scoop manifest generator,
and a per-user Windows installer with WinGet manifest generation. These are
publication candidates; maintainers choose which Windows channels to support.
They are not yet listed in the Splunk tap or public Windows package indexes.
Use the [package testing guide](specs/PACKAGE_MANAGERS.md) to test them locally.

After the formula is published in `splunk/homebrew-tap`, install it with
`brew install --HEAD splunk/tap/token-meter` until a stable release is available,
then run `token-meter install` (or `token-meter install --backend-only`).
Update with `brew upgrade token-meter`, then re-run `token-meter install` to
stage and restart the upgraded version (preserving backend-only mode). Stop it with `token-meter uninstall` before
`brew uninstall token-meter`. Staged runtime files and settings are retained.

For a published Scoop manifest, the chosen bucket supplies `scoop install
token-meter`, `scoop update token-meter`, and `scoop uninstall token-meter`.
For a published WinGet manifest, use `winget install --id Splunk.TokenMeter
--exact --scope user`, `winget upgrade --id Splunk.TokenMeter --exact`, and
`winget uninstall --id Splunk.TokenMeter --exact`. Both Windows packages use the
existing per-user server, notification-area companion, and login startup entry.
Their uninstall hooks remove the owned runtime while retaining application
settings and agent evidence. Windows package execution requires Windows testing.

Package-managed installs disable the built-in Git updater and show the appropriate
upgrade command in Settings. Reinstalling from a normal checkout returns update
ownership to the Git installer without changing your saved update preferences.

## Features

### Follow a session

Live cost, tokens, context pressure, output pace, tool calls, session budgets,
and child-agent activity on one page.

<p align="center">
  <img src="images/dashboard.png" alt="Token Meter session detail with live cost, token, context, and execution metrics" width="900">
</p>

### Understand spend

Compare any period across platforms, projects, runtimes, and sessions to find
the runs worth inspecting.

<p align="center">
  <img src="images/spend.png" alt="Token Meter Spend page with selected-period totals, stacked daily runtime costs, highest-cost logs, and platform split" width="900">
</p>

### Check efficiency

| Signal | Meaning | Better |
| --- | --- | --- |
| **Output / $** | Output tokens per dollar | Higher |
| **Reasoning ratio** | Reasoning share of output | Lower or stable |
| **Context load** | Input tokens per output token | Lower |
| **Cache hit ratio** | Cache-read share of input | Higher |

<p align="center">
  <img src="images/efficiency.png" alt="Token Meter Efficiency page with output per dollar, reasoning ratio, context load, and cache hit ratio" width="900">
</p>

### Inspect tools and skills

Spot high-output, failing, repeated, or unused tools and skill packs.

<p align="center">
  <img src="images/tool-analytics.png" alt="Token Meter capability evidence and skill-pack review" width="900">
</p>

### Git

Pairs local pushes with spend to show code changed per project and day, using
local `git` only. A mechanical signal, not a productivity score.

<p align="center">
  <img src="images/git.png" alt="Token Meter Git page showing pushed lines, spend per 1K lines, push yield, coverage, and daily code changes" width="900">
</p>

### Subagents

Track spend, cost per run, and volume for each named child-agent role, and
drill into individual runs from **Sessions → Subagents**.

### Budgets, settings, and MCP

Set monthly and per-session budgets, edit model pricing, and connect Codex or
Claude to the local MCP: eight read-only evidence tools (`check`, `usage`,
`budget`, `capabilities`, `sessions`, `trace`, `stats`, `schema`) plus two
session-budget setters that require `confirm: true`. Traces are allowlisted
structure and numbers, not raw trace content. See the
[User guide](specs/USER_GUIDE.md#ask-from-codex-or-claude) for details.

<p align="center">
  <img src="images/mcp.png" alt="Token Meter Settings view for local agent connections" width="900">
</p>

### Menu bar and tray

See the current run without opening the dashboard. Updates are checked every
10 minutes and installed automatically by default for checkout installations.
Package-managed installations use their package manager for updates.

<p align="center">
  <img src="images/menu-bar-widget.png" alt="Token Meter macOS menu bar companion" width="420">
</p>

## Privacy

- The dashboard binds to `127.0.0.1`. Do not expose it publicly.
- Traces, prompts, responses, paths, and analytics never leave your machine.
- The MCP returns derived numbers only. Agents you connect may send them to their model provider.
- Costs are estimates. Codex uses public API rates, which can differ from subscription billing.

Full details: [User guide](specs/USER_GUIDE.md#data-and-evidence) ·
[Security policy](specs/SECURITY.md).

## Documentation

| Document | Covers |
| --- | --- |
| [User guide](specs/USER_GUIDE.md) | Setup, daily use, MCP, updates, troubleshooting |
| [Security](specs/SECURITY.md) | Privacy boundaries, vulnerability reporting |
| [Architecture](specs/ARCHITECTURE.md) | Components, data flow, extension contracts |
| [Contributing](specs/CONTRIBUTING.md) | Issues, pull requests, validation |
| [Package managers](specs/PACKAGE_MANAGERS.md) | Experimental Homebrew, Scoop, WinGet, release packaging, and test instructions |
| [Product](specs/PRODUCT.md) · [Design](specs/DESIGN.md) | Product and experience decisions |

## License

MIT. See [LICENSE](LICENSE).
