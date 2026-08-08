"""The swappable I/O layer: Glue Catalog / S3 reads and writes.

Everything Glue- or S3-specific lives here so `transform.py` stays pure. In local
fixture tests this module is not used at all — the tests build DataFrames from
local CSVs directly.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession, functions as F


# --- Reads -----------------------------------------------------------------

def read_roadcalls_from_catalog(
    glue_context,
    database: str,
    table: str,
    within_last_year: bool = True,
) -> DataFrame:
    """Read road calls from the Glue Data Catalog (matches the notebook)."""
    dyf = glue_context.create_dynamic_frame.from_catalog(
        database=database, table_name=table
    )
    df = dyf.toDF()
    if within_last_year:
        df = df.where("roadcall_call_dt >= current_timestamp() - interval 1 year")
    return df.filter(F.col("latitude").isNotNull() & F.col("longitude").isNotNull())


def read_roadcalls_from_csv(spark: SparkSession, s3_path: str) -> DataFrame:
    """Read the geocoded road-call CSV from S3."""
    return spark.read.csv(s3_path, header=True)


def read_census_tracts_shapefile(spark: SparkSession, s3_prefix: str, srid: int = 4326) -> DataFrame:
    """Read the census-tract shapefile from S3 and tag its SRID."""
    df = spark.read.format("shapefile").load(s3_prefix)
    from geoanalytics.sql import functions as ST

    return df.withColumn("geometry", ST.srid("geometry", srid))


# --- Writes ----------------------------------------------------------------

def write_geoparquet(df: DataFrame, s3_path: str) -> None:
    """Write results (with geometry) as GeoParquet 1.0.0."""
    (
        df.write.format("geoparquet")
        .mode("overwrite")
        .option("version", "1.0.0")
        .save(s3_path)
    )


def write_parquet_table(df: DataFrame, s3_path: str, table: str, partitions: int = 4) -> None:
    """Write a non-geometry parquet copy and register it as a catalog table."""
    (
        df.drop("geometry")
        .repartition(partitions)
        .write.mode("overwrite")
        .format("parquet")
        .option("path", s3_path)
        .saveAsTable(table)
    )
