"""Unit tests for the pure spatial transforms.

These are your fast inner loop: edit src/transform.py, then
`docker compose run --rm gae pytest -q`. No AWS needed; GAE license required.
"""
from __future__ import annotations

from src import transform

TRACT_COLS = [
    "STATE_ABBR", "STATE_FIPS", "COUNTY_FIP", "STCOFIPS",
    "TRACT_FIPS", "FIPS", "POPULATION", "POP_SQMI", "POPULATI_1", "POP20_SQMI",
]


def test_add_point_geometry_sets_srid(points):
    row = points.selectExpr("ST_SRID(geometry) AS srid").first()
    assert row["srid"] == 4326


def test_roadcalls_per_tract_counts(points, tracts):
    result = transform.roadcalls_per_tract(points, tracts, TRACT_COLS)
    counts = {r["FIPS"]: r["roadcall_count"] for r in result.collect()}

    # 3 points fall in the Philadelphia tract, 2 in the Pittsburgh tract,
    # and 1 point (RC006) is outside every tract and must be excluded.
    assert counts["42101000100"] == 3
    assert counts["42003000200"] == 2
    assert sum(counts.values()) == 5


def test_no_null_geometry_in_result(points, tracts):
    result = transform.roadcalls_per_tract(points, tracts, TRACT_COLS)
    nulls = result.filter("geometry IS NULL").count()
    assert nulls == 0
