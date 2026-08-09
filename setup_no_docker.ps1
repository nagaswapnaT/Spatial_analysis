<#
.SYNOPSIS
  No-Docker / no-admin-rights environment setup for gae-local-dev.

  For laptops where Docker Desktop can't be installed (needs admin rights to
  enable WSL2/Hyper-V). This installs a per-user Miniconda (no admin prompt),
  creates an env with Python 3.11 + Java 17 + PySpark 3.5.4 (matching Glue 5.0
  as closely as a non-container setup can), and fetches the GAE libraries via
  boto3 instead of the AWS CLI (whose installer also needs admin rights).

  This covers Tier 1's fast pytest loop on local fixtures. For anything that
  needs real S3/Glue Catalog data, use Tier 2 (Glue Interactive Sessions) from
  the README instead — it's a pip-installable Jupyter kernel that runs against
  the real AWS backend, so it needs no Docker and no admin rights either.

.EXAMPLE
  .\setup_no_docker.ps1
  .\setup_no_docker.ps1 -SkipLibs -SkipVerify
#>
[CmdletBinding()]
param(
  [switch]$SkipVerify,
  [switch]$SkipLibs
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Info($m) { Write-Host "==> $m" -ForegroundColor Blue }
function Ok($m)   { Write-Host "  ok $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !! $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "  xx $m" -ForegroundColor Red; exit 1 }

$CondaRoot = Join-Path $HOME "Miniconda3-gae"
$EnvName   = "gae-local-dev"
$EnvPrefix = Join-Path $CondaRoot "envs\$EnvName"

# --- Step 1: .env -------------------------------------------------------------
Info "Step 1/5  Ensuring .env exists"
if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Ok "created .env from .env.example"
  Warn "Edit .env now: set GAE_USERNAME / GAE_PASSWORD / AWS_PROFILE, then re-run: .\setup_no_docker.ps1"
  exit 0
}
Ok ".env present"
if (Select-String -Path .env -Pattern '^GAE_PASSWORD=changeme' -Quiet) {
  Die "GAE_PASSWORD is still the placeholder 'changeme'. Edit .env, then re-run."
}

# --- Step 2: per-user Miniconda (no admin rights needed) ---------------------
Info "Step 2/5  Ensuring a per-user Python 3.11 + Java 17 runtime"
$condaExe = Join-Path $CondaRoot "Scripts\conda.exe"
if (-not (Test-Path $condaExe)) {
  Warn "Miniconda not found at $CondaRoot - downloading the per-user installer"
  $installer = Join-Path $env:TEMP "Miniconda3-latest-Windows-x86_64.exe"
  Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe" -OutFile $installer
  # /InstallationType=JustMe -> per-user install, no admin elevation prompt.
  # /AddToPath=0 keeps it from touching your global PATH / other Python tools.
  Start-Process -FilePath $installer -ArgumentList @(
    "/InstallationType=JustMe", "/AddToPath=0", "/RegisterPython=0", "/S", "/D=$CondaRoot"
  ) -Wait
  if (-not (Test-Path $condaExe)) {
    Die "Miniconda install did not complete. Try running the installer manually: $installer"
  }
  Ok "Miniconda installed to $CondaRoot"
} else {
  Ok "Miniconda already present at $CondaRoot"
}

# Newer conda requires accepting Anaconda's Terms of Service for the "defaults"
# channels before any solve touches them, even if environment.yml only lists
# conda-forge. Accept non-interactively here so a fresh install doesn't fail;
# harmless no-op on conda versions without this requirement.
foreach ($ch in @("main", "r", "msys2")) {
  & $condaExe tos accept --override-channels --channel "https://repo.anaconda.com/pkgs/$ch" 2>$null | Out-Null
}

# --- Step 3: create/update the conda environment ------------------------------
Info "Step 3/5  Creating the '$EnvName' environment (python 3.11, openjdk 17, pyspark 3.5.4)"
$envList = & $condaExe env list
if ($envList -match [regex]::Escape($EnvName)) {
  & $condaExe env update -p $EnvPrefix -f environment.yml --prune
} else {
  & $condaExe env create -p $EnvPrefix -f environment.yml
}
if (-not $?) { Die "conda env create/update failed - see output above." }
Ok "environment ready at $EnvPrefix"

$envPython = Join-Path $EnvPrefix "python.exe"

# conda-forge's openjdk normally sets JAVA_HOME on `conda activate`, but we
# invoke python.exe directly (no activation), so set it explicitly.
$env:JAVA_HOME = Join-Path $EnvPrefix "Library"
$env:PATH = "$($env:JAVA_HOME)\bin;$env:PATH"
$env:PYTHONPATH = (Get-Location).Path

# --- Step 4: fetch GAE libraries (boto3, no AWS CLI needed) ------------------
Info "Step 4/5  Fetching GAE libraries"
if ($SkipLibs) {
  Warn "skipped (-SkipLibs)"
} else {
  & $envPython scripts\fetch_gae_libs.py
  if (-not $?) { Die "fetch_gae_libs.py failed - see output above." }
}

# --- Step 5: verify -----------------------------------------------------------
Info "Step 5/5  Verifying Spark + GAE plugin + license"
if ($SkipVerify) {
  Warn "skipped (-SkipVerify)"
} else {
  & $envPython scripts\verify_setup.py
  if (-not $?) {
    Warn "Verification failed. If the error mentions NativeIO / winutils / UnsatisfiedLinkError,"
    Warn "see the 'No Docker' section of README.md for the winutils.exe fix."
    Die "see output above."
  }
}

Write-Host ""
Ok "Setup complete - no Docker, no admin rights used."
Write-Host "In a new terminal, load the environment first:"
Write-Host "  . .\activate_no_docker.ps1"
Write-Host "  & `$py -m pytest -q"
Write-Host "  & `$py -m src.job --local"
