$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Rid = "win-x64"
$ValidatorProject = Join-Path $Root "dotnet\OpenXmlSdkValidator\OpenXmlSdkValidator.csproj"

Write-Host "Publishing self-contained Open XML SDK validator..." -ForegroundColor Cyan
& dotnet publish $ValidatorProject `
    -c Release `
    -r $Rid `
    --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:DebugType=None `
    -p:DebugSymbols=false

$Validator = Join-Path $Root "dotnet\OpenXmlSdkValidator\bin\Release\net8.0\$Rid\publish\OpenXmlSdkValidator.exe"
if (-not (Test-Path $Validator)) {
    throw "Validator build not found: $Validator"
}

$Venv = Join-Path $Root ".build-venv"
if (-not (Test-Path $Venv)) {
    py -3 -m venv $Venv
}
$Python = Join-Path $Venv "Scripts\python.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"

& $Python -m pip install --upgrade pip
& $Python -m pip install -e ".[portable]"

$env:OPENXML_VALIDATOR_BIN = $Validator
& $PyInstaller --clean --noconfirm (Join-Path $Root "portable\OOXMLCompatNormalize.spec")

Write-Host ""
Write-Host "Portable executable created:" -ForegroundColor Green
Write-Host (Join-Path $Root "dist\OOXML-Compat-Normalize.exe")
