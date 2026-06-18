param(
    [string]$Python = "C:\App\Anaconda\python.exe",
    [switch]$SkipDemo,
    [switch]$SkipFullLabs,
    [switch]$SkipBrowser
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Command
    Write-Host "OK: $Name"
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

$platformFiles = @(
    ".\labs\fintech-platform\platform_api_app.py",
    ".\labs\fintech-platform\platform_api_service.py",
    ".\labs\fintech-platform\platform_async_service.py",
    ".\labs\fintech-platform\fintech_platform.py",
    ".\labs\fintech-platform\demo.py"
)

Invoke-Step "Compile fintech-platform entry files" {
    & $Python -B -m py_compile @platformFiles
}

if ($SkipBrowser) {
    Invoke-Step "Run fintech-platform tests without browser regression" {
        & $Python -B -m pytest -p no:cacheprovider ".\labs\fintech-platform" --ignore=".\labs\fintech-platform\test_platform_ui_playwright.py" -q
    }
} else {
    Invoke-Step "Run fintech-platform tests" {
        & $Python -B -m pytest -p no:cacheprovider ".\labs\fintech-platform" -q
    }
}

if (-not $SkipDemo) {
    Invoke-Step "Run fintech-platform demo" {
        & $Python -B ".\labs\fintech-platform\demo.py"
    }
}

if (-not $SkipFullLabs) {
    if ($SkipBrowser) {
        Invoke-Step "Run all labs tests without browser regression" {
            & $Python -B -m pytest -p no:cacheprovider ".\labs" --ignore=".\labs\fintech-platform\test_platform_ui_playwright.py" -q
        }
    } else {
        Invoke-Step "Run all labs tests" {
            & $Python -B -m pytest -p no:cacheprovider ".\labs" -q
        }
    }
}

Write-Host ""
Write-Host "Verification completed."
