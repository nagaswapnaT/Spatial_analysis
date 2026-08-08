"""Smoke test: prove the container can run Spark + GAE before you write code.

  docker compose run --rm gae python scripts/verify_setup.py

Checks, in order:
  1. SPARK OK        - Spark session starts with the GAE plugin registered
  2. GAE PLUGIN OK   - the ST_* SQL functions are available (a real spatial op runs)
  3. GAE AUTH OK     - the license authenticates from .env
  4. CATALOG OK      - (optional) the Glue Data Catalog is reachable

Exit code is non-zero if any required check fails.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import bootstrap_spark  # noqa: E402


def main() -> int:
    # 1. Spark + plugin
    try:
        spark = bootstrap_spark.build_spark("verify-setup")
        print("SPARK OK")
    except Exception as e:  # noqa: BLE001
        print("SPARK FAILED:", e)
        return 1

    # 2. GAE plugin / ST_* functions
    try:
        bootstrap_spark.authenticate_gae()
        print("GAE AUTH OK")
    except Exception as e:  # noqa: BLE001
        print("GAE AUTH FAILED:", e)
        print("  -> usually the license server is unreachable from your network.")
        return 1

    try:
        row = spark.sql(
            "SELECT ST_Distance(ST_Point(0,0), ST_Point(3,4)) AS d"
        ).collect()[0]
        assert abs(row["d"] - 5.0) < 1e-6, row["d"]
        print("GAE PLUGIN OK (ST_Distance = %.1f)" % row["d"])
    except Exception as e:  # noqa: BLE001
        print("GAE PLUGIN FAILED:", e)
        print("  -> check the jar paths in gae_libs/ match GAE_JAR / GAE_NATIVES_JAR.")
        return 1

    # 3. Optional: Glue Catalog reachability
    db = os.environ.get("CATALOG_DATABASE")
    if db:
        try:
            cat = bootstrap_spark.build_spark("verify-catalog", enable_glue_catalog=True)
            cat.sql(f"SHOW TABLES IN {db}").show(5, truncate=False)
            print("CATALOG OK")
        except Exception as e:  # noqa: BLE001
            print("CATALOG SKIPPED/FAILED (non-fatal):", e)

    spark.stop()
    print("\nAll required checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
