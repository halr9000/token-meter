[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [string]$Compiler = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must be a stable MAJOR.MINOR.PATCH number."
}
$SourceRoot = [IO.Path]::GetFullPath($SourceRoot)
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
if ((Get-Content -LiteralPath (Join-Path $SourceRoot "RELEASE_VERSION") -Raw).Trim() -ne $Version) {
    throw "Build from the version-matched source release archive."
}
if (-not $Compiler) {
    $Compiler = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path -LiteralPath $Compiler -PathType Leaf)) {
    throw "Install Inno Setup 6 or supply -Compiler with the ISCC.exe path."
}
$Definition = Join-Path $PSScriptRoot "..\packaging\winget\token-meter.iss"
& $Compiler "/DAppVersion=$Version" "/DSourceRoot=$SourceRoot" "/DOutputRoot=$OutputRoot" $Definition
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}
