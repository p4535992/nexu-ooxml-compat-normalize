param(
    [Parameter(Mandatory = $true)]
    [string]$QuarkusJar,

    [Parameter(Mandatory = $true)]
    [string]$CoreJar,

    [string]$Destination = "quarkus/target/jpackage",
    [string]$AppVersion = "0.4.0"
)

$ErrorActionPreference = "Stop"

$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDirectory "..\..")).Path
$QuarkusJar = [System.IO.Path]::GetFullPath($QuarkusJar)
$CoreJar = [System.IO.Path]::GetFullPath($CoreJar)
$Destination = [System.IO.Path]::GetFullPath($Destination)

$Jpackage = Join-Path $env:JAVA_HOME "bin\jpackage.exe"
$Jlink = Join-Path $env:JAVA_HOME "bin\jlink.exe"
$AppName = "OOXML-Compat-Normalize-Quarkus"
$InputDirectory = Join-Path $Destination "input"
$RuntimeImage = Join-Path $Destination "runtime-image"
$AppImage = Join-Path $Destination $AppName
$PortableArchive = Join-Path $Destination "OOXML-Compat-Normalize-java-portable-win-x64.zip"
$InstallerName = "OOXML-Compat-Normalize-java-quarkus-installer-win-x64.exe"
$InstallerTarget = Join-Path $Destination $InstallerName
$UpgradeUuid = "c9151607-860b-4a4f-96a1-cc9d03179060"

if (-not (Test-Path -LiteralPath $Jpackage -PathType Leaf)) {
    throw "jpackage.exe not found under JAVA_HOME: $Jpackage"
}
if (-not (Test-Path -LiteralPath $Jlink -PathType Leaf)) {
    throw "jlink.exe not found under JAVA_HOME: $Jlink"
}
if (-not (Test-Path -LiteralPath $QuarkusJar -PathType Leaf)) {
    throw "Quarkus JAR not found: $QuarkusJar"
}
if (-not (Test-Path -LiteralPath $CoreJar -PathType Leaf)) {
    throw "Core JAR not found: $CoreJar"
}

if (Test-Path -LiteralPath $Destination) {
    Remove-Item -LiteralPath $Destination -Recurse -Force
}
New-Item -ItemType Directory -Path $InputDirectory | Out-Null

$QuarkusName = "OOXML-Compat-Normalize-java-quarkus.jar"
$CoreName = "OOXML-Compat-Normalize-java-core.jar"
Copy-Item -LiteralPath $QuarkusJar -Destination (Join-Path $InputDirectory $QuarkusName)
Copy-Item -LiteralPath $CoreJar -Destination (Join-Path $InputDirectory $CoreName)

& $Jlink `
    --add-modules ALL-MODULE-PATH `
    --strip-debug `
    --no-header-files `
    --no-man-pages `
    --compress=2 `
    --output $RuntimeImage
if ($LASTEXITCODE -ne 0) {
    throw "jlink failed with exit code $LASTEXITCODE"
}

$ImageArguments = @(
    "--type", "app-image",
    "--name", $AppName,
    "--app-version", $AppVersion,
    "--vendor", "OOXML Compat Normalize",
    "--description", "Local OOXML normalization service",
    "--dest", $Destination,
    "--input", $InputDirectory,
    "--main-jar", $QuarkusName,
    "--runtime-image", $RuntimeImage
)

& $Jpackage @ImageArguments
if ($LASTEXITCODE -ne 0) {
    throw "jpackage app-image failed with exit code $LASTEXITCODE"
}

Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE") -Destination (Join-Path $AppImage "LICENSE")
Copy-Item -LiteralPath (Join-Path $ProjectRoot "THIRD_PARTY_NOTICES.md") -Destination (Join-Path $AppImage "THIRD_PARTY_NOTICES.md")
Copy-Item -LiteralPath (Join-Path $ProjectRoot "THIRD_PARTY_LICENSES.md") -Destination (Join-Path $AppImage "THIRD_PARTY_LICENSES.md")
Copy-Item -LiteralPath (Join-Path $ScriptDirectory "LOGS.txt") -Destination (Join-Path $AppImage "LOGS.txt")

$CoreLauncher = Join-Path $AppImage "ooxml-normalize.cmd"
@'
@echo off
"%~dp0runtime\bin\java.exe" -jar "%~dp0app\OOXML-Compat-Normalize-java-core.jar" %*
'@ | Set-Content -LiteralPath $CoreLauncher -Encoding ASCII

$OpenUi = Join-Path $AppImage "open-ui.cmd"
@'
@echo off
start "" "http://127.0.0.1:8080/"
'@ | Set-Content -LiteralPath $OpenUi -Encoding ASCII

if (-not (Test-Path -LiteralPath (Join-Path $AppImage "$AppName.exe") -PathType Leaf)) {
    throw "jpackage launcher $AppName.exe is missing from app image"
}
if (-not (Test-Path -LiteralPath $CoreLauncher -PathType Leaf)) {
    throw "Core CLI launcher is missing from app image"
}
if (-not (Test-Path -LiteralPath (Join-Path $AppImage "LOGS.txt") -PathType Leaf)) {
    throw "LOGS.txt is missing from app image"
}

if (Test-Path -LiteralPath $PortableArchive) {
    Remove-Item -LiteralPath $PortableArchive -Force
}
Compress-Archive -Path $AppImage -DestinationPath $PortableArchive -CompressionLevel Optimal

$InstallerArguments = @(
    "--type", "exe",
    "--name", $AppName,
    "--app-version", $AppVersion,
    "--vendor", "OOXML Compat Normalize",
    "--description", "Local OOXML normalization service",
    "--dest", $Destination,
    "--app-image", $AppImage,
    "--license-file", (Join-Path $ProjectRoot "LICENSE"),
    "--win-menu",
    "--win-menu-group", "OOXML Compat Normalize",
    "--win-shortcut",
    "--win-dir-chooser",
    "--win-per-user-install",
    "--win-upgrade-uuid", $UpgradeUuid
)

& $Jpackage @InstallerArguments
if ($LASTEXITCODE -ne 0) {
    throw "jpackage EXE generation failed with exit code $LASTEXITCODE"
}

$GeneratedInstaller = Get-ChildItem -LiteralPath $Destination -Filter "*.exe" -File |
    Where-Object { $_.FullName -ne (Join-Path $AppImage "$AppName.exe") } |
    Select-Object -First 1
if (-not $GeneratedInstaller) {
    throw "jpackage did not create a Windows installer EXE"
}
if (Test-Path -LiteralPath $InstallerTarget) {
    Remove-Item -LiteralPath $InstallerTarget -Force
}
Move-Item -LiteralPath $GeneratedInstaller.FullName -Destination $InstallerTarget

Write-Host "Application image: $AppImage"
Write-Host "Portable archive: $PortableArchive"
Write-Host "Windows installer: $InstallerTarget"
Write-Host "Primary launcher: $(Join-Path $AppImage "$AppName.exe")"
Write-Host "Diagnostic log guide: $(Join-Path $AppImage 'LOGS.txt')"
