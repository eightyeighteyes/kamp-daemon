# Build the now-playing-helper.exe (Windows SMTC bridge).
#
# Windows analog of native/build-native.sh. Compiles the Rust crate at
# native/now-playing-helper-win/ and copies the release binary into
# resources/ so electron-builder packages it via extraResources.
#
# Usage (from the kamp_ui/ directory or from native/):
#   pwsh native/build-native.ps1
#
# Requires: a Rust toolchain on PATH with MSVC linker access (CI uses
# `dtolnay/rust-toolchain@stable` on windows-latest, which has VS Build
# Tools preinstalled).

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Always run from kamp_ui/ so paths resolve regardless of invocation cwd.
$kampUi = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $kampUi

$crateDir = "native/now-playing-helper-win"
$exeName = "now-playing-helper.exe"
$outDir = "resources"

Write-Host "[now-playing] Building $crateDir (cargo release)..."
Push-Location $crateDir
try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) {
        throw "cargo build failed (exit $LASTEXITCODE)"
    }
}
finally {
    Pop-Location
}

$built = Join-Path $crateDir "target/release/$exeName"
if (-not (Test-Path $built)) {
    throw "Expected build artifact not found: $built"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$dest = Join-Path $outDir $exeName
Copy-Item -Force $built $dest

$size = "{0:N0}" -f (Get-Item $dest).Length
Write-Host "[now-playing] Binary: $dest ($size bytes)"

# Smoke-test the binary so we don't silently ship a corrupt build. The helper
# is a long-running process driven by stdin, so we can't run it with --version;
# instead, verify it starts and exits cleanly when stdin is closed immediately.
Write-Host "[now-playing] Smoke test: spawn with closed stdin..."
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = (Resolve-Path $dest).Path
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$proc = [System.Diagnostics.Process]::Start($psi)
$proc.StandardInput.Close()
if (-not $proc.WaitForExit(5000)) {
    $proc.Kill()
    throw "Helper did not exit within 5s after stdin close"
}
if ($proc.ExitCode -ne 0) {
    $err = $proc.StandardError.ReadToEnd()
    throw "Helper exited with code $($proc.ExitCode). stderr: $err"
}
Write-Host "[now-playing] Smoke test OK"
Write-Host "[now-playing] Done"
