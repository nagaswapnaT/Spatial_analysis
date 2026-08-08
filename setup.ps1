<#
.SYNOPSIS
  One-command environment setup for gae-local-dev (Windows / PowerShell).

.EXAMPLE
  .\setup.ps1                 Full setup: preflight -> .env -> build -> libs -> verify
  .\setup.ps1 -Rebuild        Force a clean docker image rebuild
  .\setup.ps1 -SkipVerify     Skip the final GAE license/plugin smoke test
  .\setup.ps1 -SkipLibs       Skip fetching GAE jars from S3

  Safe to re-run: every step is idempotent.
#>
[CmdletBinding()]
param(
  [switch]$Rebuild,
  [switch]$SkipVerify,
  [switch]$SkipLibs
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Info($m) { Write-Host "==> $m" -ForegroundColor Blue }
function Ok($m)   { Write-Host "  ok $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !! $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "  xx $m" -ForegroundColor Red; exit 1 }

# --- pick a `docker compose` invocation --------------------------------------
$DC = $null
docker compose version *> $null
if ($?) { $DC = @("docker", "compose") }
elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) { $DC = @("docker-compose") }

function Compose { param([Parameter(ValueFromRemainingArguments)]$Args) & $DC[0] $DC[1..($DC.Count-1)] @Args }

# --- Step 1: preflight --------------------------------------------------------
Info "Step 1/5  Checking prerequisites"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Die "Docker not found. Install Docker Desktop and retry." }
docker info *> $null
if (-not $?) { Die "Docker daemon not running. Start Docker Desktop and retry." }
if (-not $DC) { Die "docker compose not found. Update Docker Desktop." }
Ok "docker + compose present"
if (Get-Command aws -ErrorAction SilentlyContinue) { Ok "aws cli present" }
else { Warn "aws cli not found - needed to fetch GAE libs and reach S3/Catalog." }

# --- Step 2: .env -------------------------------------------------------------
Info "Step 2/5  Ensuring .env exists"
if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Ok "created .env from .env.example"
  Warn "Edit .env now: set GAE_USERNAME / GAE_PASSWORD / AWS_PROFILE, then re-run: .\setup.ps1"
  exit 0
}
Ok ".env present"
if (Select-String -Path .env -Pattern '^GAE_PASSWORD=changeme' -Quiet) {
  Die "GAE_PASSWORD is still the placeholder 'changeme'. Edit .env, then re-run."
}

# --- Step 3: build image ------------------------------------------------------
Info "Step 3/5  Building the Glue 5.0 dev image"
if ($Rebuild) { Compose build --no-cache gae } else { Compose build gae }
if (-not $?) { Die "docker build failed." }
Ok "image built"

# --- Step 4: fetch GAE libraries ---------------------------------------------
Info "Step 4/5  Fetching GAE libraries"
if ($SkipLibs) {
  Warn "skipped (-SkipLibs)"
} else {
  # Read the GAE settings from .env (with defaults).
  $env = @{}
  Get-Content .env | Where-Object { $_ -match '^\s*([^#=]+)=(.*)$' } | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { $env[$Matches[1].Trim()] = $Matches[2].Trim() }
  }
  $s3     = if ($env.GAE_LIB_S3_URI) { $env.GAE_LIB_S3_URI.TrimEnd('/') } else { Die "GAE_LIB_S3_URI missing from .env" }
  $files  = @(
    if ($env.GAE_JAR)         { $env.GAE_JAR }         else { "geoanalytics_2.12-2.0.0.jar" }
    if ($env.GAE_NATIVES_JAR) { $env.GAE_NATIVES_JAR } else { "geoanalytics-natives_2.12-2.0.0.jar" }
    if ($env.GAE_PY_ZIP)      { $env.GAE_PY_ZIP }      else { "geoanalytics-2.0.0.zip" }
  )
  $jarPath = Join-Path "gae_libs" $files[0]

  if (Test-Path $jarPath) {
    Ok "GAE libs already present in gae_libs\"
  } elseif (Get-Command aws -ErrorAction SilentlyContinue) {
    New-Item -ItemType Directory -Force -Path gae_libs | Out-Null
    foreach ($f in $files) {
      Write-Host "  - $f"
      aws s3 cp "$s3/$f" "gae_libs/$f"
      if (-not $?) { Die "aws s3 cp failed for $f" }
    }
    Ok "GAE libs downloaded"
  } else {
    Die "aws cli required to fetch GAE libs. Install it, or place the jars/zip in gae_libs\ manually, then re-run."
  }
}

# --- Step 5: verify -----------------------------------------------------------
Info "Step 5/5  Verifying Spark + GAE plugin + license"
if ($SkipVerify) {
  Warn "skipped (-SkipVerify)"
} else {
  Compose run --rm gae python scripts/verify_setup.py
  if (-not $?) { Die "verification failed - see output above." }
}

Write-Host ""
Ok "Setup complete."
Write-Host "Next:"
Write-Host "  Fast test loop : docker compose run --rm gae pytest -q"
Write-Host "  Jupyter Lab    : docker compose up gae-lab   (http://localhost:8888)"
Write-Host "  Run the job    : docker compose run --rm gae python -m src.job --local"
