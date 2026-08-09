<#
.SYNOPSIS
  Load the Tier 0 (no-Docker) environment into the current PowerShell session.

  Sets $py to the conda env's python.exe and wires JAVA_HOME/PATH so that
  interpreter can find Java. (PYSPARK_PYTHON, PYSPARK_DRIVER_PYTHON, and
  SPARK_LOCAL_IP are set automatically by src/bootstrap_spark.py itself, so
  they don't need to be set here.)

.EXAMPLE
  . .\activate_no_docker.ps1
  & $py -m pytest -q
  & $py -m src.job --local
#>
$CondaRoot = Join-Path $HOME "Miniconda3-gae"
$EnvPrefix = Join-Path $CondaRoot "envs\gae-local-dev"

if (-not (Test-Path (Join-Path $EnvPrefix "python.exe"))) {
  Write-Host "Environment not found at $EnvPrefix - run .\setup_no_docker.ps1 first." -ForegroundColor Red
  return
}

$env:JAVA_HOME = Join-Path $EnvPrefix "Library"
$env:PATH = "$($env:JAVA_HOME)\bin;$env:PATH"
$env:PYTHONPATH = $PSScriptRoot
$py = Join-Path $EnvPrefix "python.exe"

Write-Host "Tier 0 environment active. `$py = $py" -ForegroundColor Green
