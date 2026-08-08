#!/usr/bin/env bash
# Download the ESRI GeoAnalytics Engine jars + python zip from S3 into ./gae_libs.
# Run once on the work laptop after `cp .env.example .env`.
#
#   bash scripts/fetch_gae_libs.sh
#
# Requires AWS CLI v2 configured with access to the GAE_LIB_S3_URI bucket.
set -euo pipefail

# Load .env if present so GAE_LIB_S3_URI / file names are available.
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

: "${GAE_LIB_S3_URI:?set GAE_LIB_S3_URI in .env}"
: "${GAE_JAR:=geoanalytics_2.12-2.0.0.jar}"
: "${GAE_NATIVES_JAR:=geoanalytics-natives_2.12-2.0.0.jar}"
: "${GAE_PY_ZIP:=geoanalytics-2.0.0.zip}"

DEST="gae_libs"
mkdir -p "$DEST"

echo "Fetching GAE libraries from ${GAE_LIB_S3_URI} -> ${DEST}/"
for f in "$GAE_JAR" "$GAE_NATIVES_JAR" "$GAE_PY_ZIP"; do
  echo "  - $f"
  aws s3 cp "${GAE_LIB_S3_URI%/}/$f" "${DEST}/$f"
done

echo "Done. Contents of ${DEST}/:"
ls -la "$DEST"
