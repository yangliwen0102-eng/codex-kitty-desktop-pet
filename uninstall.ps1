param([switch]$RemoveSettings)

$ErrorActionPreference = "Stop"
$DataDir = Join-Path $env:LOCALAPPDATA "CodexKittyPet"
$PidPath = Join-Path $DataDir "pet.pid"

if (Test-Path -LiteralPath $PidPath) {
    $PetPid = [int](Get-Content -Raw -LiteralPath $PidPath)
    Stop-Process -Id $PetPid -Force -ErrorAction SilentlyContinue
}

$Shortcuts = @(
    (Join-Path ([Environment]::GetFolderPath("Startup")) "Codex Kitty Pet.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Start Codex Kitty Pet.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "Start Codex Kitty Pet.lnk")
)
foreach ($ShortcutPath in $Shortcuts) {
    Remove-Item -LiteralPath $ShortcutPath -Force -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath (Join-Path $DataDir "app") -Recurse -Force -ErrorAction SilentlyContinue
if ($RemoveSettings) {
    Remove-Item -LiteralPath $DataDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "Codex Kitty Pet uninstalled."
