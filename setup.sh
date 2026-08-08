#!/usr/bin/env bash
# One-command environment setup for gae-local-dev (macOS / Linux / Git Bash / WSL).
#
#   bash setup.sh                 full setup: preflight -> .env -> build -> libs -> verify
#   bash setup.sh --rebuild       force a clean docker image rebuild
#   bash setup.sh --skip-verify   skip the final GAE license/plugin smoke test
#   bash setup.sh --skip-libs     skip fetching GAE jars from S3
#
# Safe to re-run: every step is idempotent.
set -euo pipefail

cd "$(dirname "$0")"

REBUILD=0; SKIP_VERIFY=0; SKIP_LIBS=0
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    --skip-verify) SKIP_VERIFY=1 ;;
    --skip-libs) SKIP_LIBS=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m  ok\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m  !!\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31m  xx\033[0m %s\n' "$*" >&2; exit 1; }

# --- pick a `docker compose` invocation --------------------------------------
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC=""
fi

# --- Step 1: preflight --------------------------------------------------------
info "Step 1/5  Checking prerequisites"
command -v docker >/dev/null 2>&1 || die "Docker not found. Install Docker Desktop and retry."
docker info >/dev/null 2>&1 || die "Docker daemon not running. Start Docker Desktop and retry."
[ -n "$DC" ] || die "docker compose not found. Update Docker Desktop."
ok "docker + compose present"
if command -v aws >/dev/null 2>&1; then
  ok "aws cli present"
else
  warn "aws cli not found — needed to fetch GAE libs and reach S3/Catalog."
fi

# --- Step 2: .env -------------------------------------------------------------
info "Step 2/5  Ensuring .env exists"
if [ ! -f .env ]; then
  cp .env.example .env
  ok "created .env from .env.example"
  warn "Edit .env now: set GAE_USERNAME / GAE_PASSWORD / AWS_PROFILE, then re-run: bash setup.sh"
  exit 0
fi
ok ".env present"
if grep -q '^GAE_PASSWORD=changeme' .env; then
  die "GAE_PASSWORD is still the placeholder 'changeme'. Edit .env, then re-run."
fi

# --- Step 3: build image ------------------------------------------------------
info "Step 3/5  Building the Glue 5.0 dev image"
if [ "$REBUILD" -eq 1 ]; then
  $DC build --no-cache gae
else
  $DC build gae
fi
ok "image built"

# --- Step 4: fetch GAE libraries ---------------------------------------------
info "Step 4/5  Fetching GAE libraries"
if [ "$SKIP_LIBS" -eq 1 ]; then
  warn "skipped (--skip-libs)"
else
  # shellcheck disable=SC1091
  set -a; source .env; set +a
  jar="gae_libs/${GAE_JAR:-geoanalytics_2.12-2.0.0.jar}"
  if [ -f "$jar" ]; then
    ok "GAE libs already present in gae_libs/"
  elif command -v aws >/dev/null 2>&1; then
    bash scripts/fetch_gae_libs.sh
    ok "GAE libs downloaded"
  else
    die "aws cli required to fetch GAE libs. Install it, or place the jars/zip in gae_libs/ manually, then re-run."
  fi
fi

# --- Step 5: verify -----------------------------------------------------------
info "Step 5/5  Verifying Spark + GAE plugin + license"
if [ "$SKIP_VERIFY" -eq 1 ]; then
  warn "skipped (--skip-verify)"
else
  $DC run --rm gae python scripts/verify_setup.py
fi

echo
ok "Setup complete."
echo "Next:"
echo "  Fast test loop : $DC run --rm gae pytest -q"
echo "  Jupyter Lab    : $DC up gae-lab   (http://localhost:8888)"
echo "  Run the job    : $DC run --rm gae python -m src.job --local"
