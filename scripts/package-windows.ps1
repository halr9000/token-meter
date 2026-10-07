[CmdletBinding()]
param(
    [ValidateSet("install", "uninstall")]
    [string]$Action = "install",
    [ValidateSet("scoop", "winget")]
    [string]$PackageManager = "scoop"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RuntimeRoot = Join-Path $env:LOCALAPPDATA "Token Meter\runtime"

if ($Action -eq "install") {
    $Arguments = @{ PackageManager = $PackageManager; InstallRoot = $RuntimeRoot }
    $ModePath = Join-Path $RuntimeRoot "INSTALL_MODE"
    if ((Test-Path -LiteralPath $ModePath -PathType Leaf) -and
        (Get-Content -LiteralPath $ModePath -Raw).Trim() -eq "backend-only") {
        $Arguments.BackendOnly = $true
    }
    & (Join-Path $PSScriptRoot "install-windows.ps1") @Arguments
    return
}

$Marker = Join-Path $RuntimeRoot "PACKAGE_MANAGER"
if (-not (Test-Path -LiteralPath $Marker -PathType Leaf) -or
    (Get-Content -LiteralPath $Marker -Raw).Trim() -ne $PackageManager) {
    Write-Host "This runtime is not managed by $PackageManager; it was left unchanged."
    return
}
# Resolve fixed per-user paths and refuse junctions before recursive removal.
if ((Get-Item -LiteralPath $RuntimeRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw "The package runtime is a reparse point; it was left unchanged."
}
if (Get-ChildItem -LiteralPath $RuntimeRoot -Recurse -Force |
    Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
    Select-Object -First 1) {
    throw "The package runtime contains a reparse point; it was left unchanged."
}
& (Join-Path $RuntimeRoot "scripts\uninstall-windows.ps1") -InstallRoot $RuntimeRoot
Remove-Item -LiteralPath $RuntimeRoot -Recurse -Force
# Application settings and coding-agent evidence live outside RuntimeRoot.
