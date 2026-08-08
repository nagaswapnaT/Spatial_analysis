"""Shared pytest fixtures: a session-scoped GAE-enabled Spark session and the
local sample DataFrames. These run entirely on local fixtures — no AWS needed —
but the GAE license (GAE_USERNAME / GAE_PASSWORD in .env) is required because the
ST_* functions are what we're testing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src import bootstrap_spark, transform

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def spark():
    session = bootstrap_spark.start("pytest-gae")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def points(spark):
    rc = spark.read.csv(str(_FIXTURES / "roadcalls_sample.csv"), header=True)
    return transform.add_point_geometry(rc, "longitude", "latitude", 4326)


@pytest.fixture(scope="session")
def tracts(spark):
    from pyspark.sql.functions import expr

    df = spark.read.csv(str(_FIXTURES / "census_tract_sample.csv"), header=True)
    # Build geometry from WKT via the registered GAE SQL function. If your GAE
    # version names it differently, adjust the function name here only.
    return df.withColumn("geometry", expr("ST_GeomFromText(wkt, 4326)"))
