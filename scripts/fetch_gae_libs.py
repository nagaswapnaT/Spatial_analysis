"""Download GAE jars/zip from S3 using boto3 — no AWS CLI install required.

The bash version (fetch_gae_libs.sh) shells out to the `aws` CLI, whose Windows
installer needs admin rights. boto3 reads the exact same ~/.aws/credentials,
~/.aws/config, and SSO cache the CLI does, and installs as a plain pip package
into your user environment, so this does the same job with no admin step.

  python scripts/fetch_gae_libs.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a simple KEY=VALUE .env file, if present."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    _load_dotenv(root / ".env")

    s3_uri = os.environ.get("GAE_LIB_S3_URI")
    if not s3_uri:
        print("GAE_LIB_S3_URI not set. Copy .env.example to .env and fill it in.", file=sys.stderr)
        return 1

    files = [
        os.environ.get("GAE_JAR", "geoanalytics_2.12-2.0.0.jar"),
        os.environ.get("GAE_NATIVES_JAR", "geoanalytics-natives_2.12-2.0.0.jar"),
        os.environ.get("GAE_PY_ZIP", "geoanalytics-2.0.0.zip"),
    ]

    parsed = urlparse(s3_uri)
    bucket = parsed.netloc
    prefix = parsed.path.strip("/")

    dest = root / "gae_libs"
    dest.mkdir(exist_ok=True)

    profile = os.environ.get("AWS_PROFILE")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    s3 = session.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    print(f"Fetching GAE libraries from {s3_uri} -> {dest}/")
    for name in files:
        key = f"{prefix}/{name}" if prefix else name
        out_path = dest / name
        print(f"  - {name}")
        s3.download_file(bucket, key, str(out_path))

    print("Done. Contents of gae_libs/:")
    for p in sorted(dest.iterdir()):
        print(" ", p.name, f"({p.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
