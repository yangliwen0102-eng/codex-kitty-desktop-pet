param(
    [string]$Python = "python",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$OriginalPath = $env:PATH
$Python = (Get-Command $Python -ErrorAction Stop).Source
# Avoid bundling incompatible system DLL lookalikes from unrelated tools.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"
$Release = Join-Path $Root "release"
$TempBuildRoot = Join-Path ([IO.Path]::GetTempPath()) "CodexKittyPet-build"
$TempDist = Join-Path $TempBuildRoot "dist"
$TempWork = Join-Path $TempBuildRoot "work"
$TempSpec = Join-Path $TempBuildRoot "spec"
$TempSource = Join-Path $TempBuildRoot "source"

foreach ($Path in @($Dist, $Release)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}
if (Test-Path -LiteralPath $TempBuildRoot) {
    Remove-Item -LiteralPath $TempBuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $TempDist, $TempWork, $TempSpec, $TempSource | Out-Null

Push-Location $Root
try {
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }

    Copy-Item -Recurse codex_pet, assets $TempSource
    Copy-Item run_pet.pyw $TempSource
    Push-Location $TempSource
    try {
        & $Python -m PyInstaller --noconfirm --clean --windowed --onefile `
            --name CodexKittyPet `
            --distpath $TempDist `
            --workpath $TempWork `
            --specpath $TempSpec `
            --add-data "$TempSource\assets\generated\asset-manifest.json;assets\generated" `
            --add-data "$TempSource\assets\generated\frames;assets\generated\frames" `
            --add-data "$TempSource\assets\pixel;assets\pixel" `
            run_pet.pyw
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    }
    finally {
        Pop-Location
    }

    Copy-Item (Join-Path $TempDist "CodexKittyPet.exe") $Dist

    $Check = Start-Process -FilePath (Join-Path $Dist "CodexKittyPet.exe") `
        -ArgumentList "--check" -WindowStyle Hidden -Wait -PassThru
    if ($Check.ExitCode -ne 0) { throw "Packaged runtime check failed." }

    $Stage = Join-Path $Release "CodexKittyPet-v$Version-win64"
    New-Item -ItemType Directory -Force -Path $Stage | Out-Null
    Copy-Item (Join-Path $Dist "CodexKittyPet.exe") $Stage
    Copy-Item README.md, LICENSE, ASSET_LICENSE.md, install.ps1, uninstall.ps1 $Stage
    Compress-Archive -Path (Join-Path $Stage "*") `
        -DestinationPath (Join-Path $Release "CodexKittyPet-v$Version-win64.zip") -Force
}
finally {
    Pop-Location
    $env:PATH = $OriginalPath
}

Write-Output "Release package: $Release\CodexKittyPet-v$Version-win64.zip"
