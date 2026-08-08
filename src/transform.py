"""Pure spatial transforms — the actual analytics.

These functions take DataFrames and return DataFrames. They import ONLY GAE SQL
functions, never Glue or S3. That is what makes them:
  * testable locally on tiny fixtures (see tests/test_transform.py), and
  * deployable to Glue unchanged.

Add new spatial requirements here as new pure functions.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from geoanalytics.sql import functions as ST


def add_point_geometry(
    df: DataFrame,
    lon_col: str = "longitude",
    lat_col: str = "latitude",
    srid: int = 4326,
) -> DataFrame:
    """Add a `geometry` point column from lon/lat columns, tagged with an SRID.

    Mirrors the notebook's ST.make_point + ST.srid pair.
    """
    df = df.withColumn("geometry", ST.make_point(x=lon_col, y=lat_col))
    df = df.withColumn("geometry", ST.srid("geometry", srid))
    return df


def roadcalls_per_tract(
    points: DataFrame,
    tracts: DataFrame,
    tract_cols: list[str],
    call_id_col: str = "call_num",
) -> DataFrame:
    """Spatially join road-call points to census tracts and count per tract.

    Reproduces the notebook's ST_Intersects join + COUNT group-by. `points` and
    `tracts` must each already have a `geometry` column in the same SRID.
    Returns tract attributes + `roadcall_count` + `geometry`.
    """
    spark = SparkSession.getActiveSession()
    if spark is None:
        raise RuntimeError("No active SparkSession; call bootstrap_spark.start() first.")

    points.createOrReplaceTempView("_rc_points")
    tracts.createOrReplaceTempView("_rc_tracts")

    select_cols = ",\n           ".join(f"A.{c}" for c in tract_cols)
    group_cols = ",\n           ".join(f"A.{c}" for c in tract_cols)

    return spark.sql(
        f"""
        SELECT /*+ BROADCAST(A) */
           {select_cols},
           COUNT(B.{call_id_col}) AS roadcall_count,
           A.geometry
        FROM _rc_tracts A
        INNER JOIN _rc_points B
            ON ST_Intersects(A.geometry, B.geometry)
        GROUP BY
           {group_cols},
           A.geometry
        """
    )
