"""Build a Spark session wired for ESRI GeoAnalytics Engine (GAE).

This replaces the AWS Glue notebook's %extra_jars / %extra_py_files / %%configure
cells and the hardcoded geoanalytics.auth(...) call. The exact same Spark
configuration is applied whether you run locally (Docker) or in Glue, so the ST_*
functions and geoanalytics.tools behave identically.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession

# ./gae_libs relative to the project root (parent of this file's parent).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GAE_LIBS = _PROJECT_ROOT / "gae_libs"


def _gae_jar_paths() -> str:
    jar = os.environ.get("GAE_JAR", "geoanalytics_2.12-2.0.0.jar")
    natives = os.environ.get("GAE_NATIVES_JAR", "geoanalytics-natives_2.12-2.0.0.jar")
    paths = [_GAE_LIBS / jar, _GAE_LIBS / natives]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "GAE jars not found: %s\nRun `bash scripts/fetch_gae_libs.sh` first."
            % ", ".join(missing)
        )
    return ",".join(str(p) for p in paths)


def _add_gae_python_zip() -> None:
    """Put the geoanalytics python package on sys.path for the driver."""
    zip_name = os.environ.get("GAE_PY_ZIP", "geoanalytics-2.0.0.zip")
    zip_path = _GAE_LIBS / zip_name
    if zip_path.exists() and str(zip_path) not in sys.path:
        sys.path.insert(0, str(zip_path))


def _fix_windows_defaults() -> None:
    """Work around two PySpark-on-Windows issues that don't show up in Glue/Docker.

    1. Spark's RPC layer builds a URL from the machine hostname; a hostname with
       an underscore (e.g. "Swapna_hari") is an invalid URL and SparkContext
       init crashes immediately. Forcing SPARK_LOCAL_IP sidesteps hostname
       resolution entirely.
    2. PySpark launches worker subprocesses by resolving "python"/"python3" on
       PATH. If that resolves to a different interpreter than the one running
       the driver (e.g. a Windows Store Python stub ahead of this env on PATH),
       the driver<->worker pickle protocol mismatches and the socket pipe
       between them dies with "Connection reset". Pinning PYSPARK_PYTHON /
       PYSPARK_DRIVER_PYTHON to sys.executable guarantees they match.
    """
    if os.name != "nt":
        return
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)


# Run at import time, not inside build_spark(): other modules (transform.py,
# io_glue.py) do a top-level `from geoanalytics.sql import functions as ST`.
# conftest.py/job.py import bootstrap_spark before those modules, so this must
# put the GAE zip on sys.path here — waiting until build_spark() runs is too
# late, since transform.py would already have failed to import by then.
_add_gae_python_zip()


def build_spark(app_name: str = "gae-local-dev", enable_glue_catalog: bool = False) -> SparkSession:
    """Create a GAE-enabled SparkSession.

    enable_glue_catalog=True registers the AWS Glue Data Catalog as the Hive
    metastore so `spark.sql("SELECT * FROM db.table")` resolves catalog tables
    (needs Glue/Lake Formation read perms on your AWS role). Leave False for
    fixture-only local tests.
    """
    _fix_windows_defaults()

    builder = (
        SparkSession.builder.appName(app_name)
        # --- GAE plugin registration (mirrors the notebook's %%configure) ---
        .config("spark.jars", _gae_jar_paths())
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.kryo.registrator", "com.esri.geoanalytics.KryoRegistrator")
        .config("spark.plugins", "com.esri.geoanalytics.Plugin")
    )

    if enable_glue_catalog:
        builder = builder.config(
            "spark.hadoop.hive.metastore.client.factory.class",
            "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
        ).enableHiveSupport()

    spark = builder.getOrCreate()
    return spark


def authenticate_gae() -> None:
    """Authenticate the GAE license from environment variables.

    Local: values come from .env. In Glue: fetch from AWS Secrets Manager and
    set the env vars, or call geoanalytics.auth(...) directly there.
    """
    import geoanalytics  # imported after the zip is on sys.path

    username = os.environ.get("GAE_USERNAME")
    password = os.environ.get("GAE_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "GAE_USERNAME / GAE_PASSWORD not set. Copy .env.example to .env and fill them in."
        )
    geoanalytics.auth(username=username, password=password)


def start(app_name: str = "gae-local-dev", enable_glue_catalog: bool = False) -> SparkSession:
    """Convenience: build the session AND authenticate GAE."""
    spark = build_spark(app_name, enable_glue_catalog=enable_glue_catalog)
    authenticate_gae()
    return spark
