param([switch]$SkipLaunch)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceExe = Join-Path $Root "CodexKittyPet.exe"
$InstallDir = Join-Path $env:LOCALAPPDATA "CodexKittyPet\app"
$TargetExe = Join-Path $InstallDir "CodexKittyPet.exe"

if (-not (Test-Path -LiteralPath $SourceExe)) {
    throw "CodexKittyPet.exe was not found next to install.ps1. Download and extract the release ZIP first."
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -LiteralPath $SourceExe -Destination $TargetExe -Force

$Shell = New-Object -ComObject WScript.Shell
$StartupShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "Codex Kitty Pet.lnk"
$StartShortcutDirectory = [Environment]::GetFolderPath("Desktop")
if (-not (Test-Path -LiteralPath $StartShortcutDirectory)) {
    $StartShortcutDirectory = [Environment]::GetFolderPath("Programs")
}

foreach ($ShortcutPath in @($StartupShortcut, (Join-Path $StartShortcutDirectory "Start Codex Kitty Pet.lnk"))) {
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetExe
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.IconLocation = "$TargetExe,0"
    $Shortcut.Description = "Codex Kitty Desktop Pet"
    $Shortcut.Save()
}

if (-not $SkipLaunch) {
    Start-Process -FilePath $TargetExe -WorkingDirectory $InstallDir
}

Write-Output "Codex Kitty Pet installed for the current user."
