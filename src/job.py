"""End-to-end road-call hotspot job — the piece Glue runs.

Modes:
  --local    read the local WKT/CSV fixtures (no AWS, no license needed for I/O;
             GAE license still required for the ST_* join)
  --catalog  read from the real Glue Data Catalog + S3 shapefile
  --csv      read the road-call CSV from S3 instead of the catalog

Run in the container, e.g.:
  docker compose run --rm gae python -m src.job --local
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from src import bootstrap_spark, io_glue, transform

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = _PROJECT_ROOT / "tests" / "fixtures"

# Census-tract attribute columns carried through the aggregation (from the notebook).
TRACT_COLS = [
    "STATE_ABBR", "STATE_FIPS", "COUNTY_FIP", "STCOFIPS",
    "TRACT_FIPS", "FIPS", "POPULATION", "POP_SQMI", "POPULATI_1", "POP20_SQMI",
]


def _load_local(spark):
    """Build point + tract DataFrames from local fixtures (WKT for tracts)."""
    from pyspark.sql.functions import expr

    rc = spark.read.csv(str(_FIXTURES / "roadcalls_sample.csv"), header=True)
    points = transform.add_point_geometry(rc, "longitude", "latitude", 4326)

    tracts = spark.read.csv(str(_FIXTURES / "census_tract_sample.csv"), header=True)
    tracts = tracts.withColumn("geometry", expr("ST_GeomFromText(wkt, 4326)"))
    return points, tracts


def main() -> None:
    parser = argparse.ArgumentParser(description="Road-call hotspot by census tract")
    parser.add_argument("--local", action="store_true", help="use local fixtures")
    parser.add_argument("--catalog", action="store_true", help="read road calls from Glue Catalog")
    parser.add_argument("--csv", action="store_true", help="read road calls from S3 CSV")
    parser.add_argument("--write", action="store_true", help="write outputs to S3/catalog")
    args = parser.parse_args()

    use_catalog = args.catalog or args.csv
    spark = bootstrap_spark.start("roadcall-hotspots", enable_glue_catalog=use_catalog)

    if args.local or not use_catalog:
        points, tracts = _load_local(spark)
    else:
        if args.csv:
            rc = io_glue.read_roadcalls_from_csv(spark, os.environ["ROADCALL_CSV_S3"])
            points = transform.add_point_geometry(rc, "longitude", "latitude", 4326)
        else:
            from awsglue.context import GlueContext  # only available on Glue backend

            gc = GlueContext(spark.sparkContext)
            rc = io_glue.read_roadcalls_from_catalog(
                gc, os.environ["CATALOG_DATABASE"], os.environ["CATALOG_TABLE"]
            )
            points = transform.add_point_geometry(rc, "longitude", "latitude", 4326)
        tracts = io_glue.read_census_tracts_shapefile(spark, os.environ["CENSUS_TRACT_S3"])

    result = transform.roadcalls_per_tract(points, tracts, TRACT_COLS)

    print("=== road calls per tract ===")
    result.drop("geometry").show(truncate=False)
    print("tracts with road calls:", result.count())

    if args.write:
        io_glue.write_geoparquet(result, os.environ["OUTPUT_S3"])
        print("wrote geoparquet ->", os.environ["OUTPUT_S3"])

    spark.stop()


if __name__ == "__main__":
    main()
