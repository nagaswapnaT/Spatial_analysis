# gae-local-dev

A **standalone local development environment** for ESRI GeoAnalytics Engine (GAE)
+ AWS Glue Data Catalog / S3 data-lake code — so you can develop new spatial
requirements with a real IDE, a debugger, autocomplete, and `pytest`, instead of
the AWS Glue console notebook.

It mirrors **AWS Glue 5.0** exactly (Spark 3.5.4 / Python 3.11 / Scala 2.12), so
code written here ports 1:1 back into a Glue job.

This project is a self-contained copy of the pattern behind the
`job-cx-maintenance_hotspot_analysis` Glue notebook (road-call hotspots by census
tract), refactored into testable pieces.

---

## What you get

| Problem in the Glue console | Fixed here |
|---|---|
| No autocomplete / no type help | Real interpreter in VS Code |
| No breakpoints / debugger | `debugpy` in the container |
| No unit tests | `pytest` on tiny local fixtures |
| Slow session restart loop | Sub-second edits on sampled data |
| GAE config copied into every notebook | One `bootstrap_spark.py` |
| License password hardcoded in a cell | Read from `.env` / Secrets Manager |

Two tiers of development:

- **Tier 1 (this project, ~90% of work):** local Docker container matching Glue
  5.0. Fast loop on sampled data; can also reach real S3 + Glue Catalog with your
  mounted AWS credentials.
- **Tier 2 (validation before shipping):** run the *same* `src/` code through
  **Glue Interactive Sessions** from VS Code (`aws-glue-sessions` kernel) to
  confirm catalog/scale behavior on the real backend. See
  [Tier 2](#tier-2--validate-on-real-glue) below.

---

## Prerequisites on the work laptop

1. **Docker Desktop** (WSL2 backend on Windows). Confirm: `docker run hello-world`.
2. **VS Code** + extensions: *Dev Containers*, *Python*, *Jupyter*.
3. **AWS CLI v2**, configured with a profile that can read the S3 buckets and the
   Glue Catalog you use (`aws configure sso` or `aws configure`). Confirm:
   `aws sts get-caller-identity`.
4. Network access to the ESRI GAE license server (see
   [Step 4](#step-4-verify-the-gae-license-do-this-first) — this is the one thing
   that can block you, so test it early).

> **Windows note:** run everything *inside* the Linux container, not on Windows
> directly. GAE ships native libraries built for Linux; the container removes all
> Windows/native-lib headaches and is what makes the code match Glue.

---

## Quick start (automated)

After copying the folder to the laptop and installing the prerequisites, one
script does Steps 2–7 for you:

```powershell
# Windows / PowerShell
.\setup.ps1
```
```bash
# macOS / Linux / Git Bash / WSL
bash setup.sh
```

It runs preflight checks, creates `.env` (then stops so you can fill in
credentials — re-run when done), builds the Glue 5.0 image, fetches the GAE libs
from S3, and runs the license/plugin smoke test. It is idempotent, so re-run it
any time. Flags: `-Rebuild`/`--rebuild`, `-SkipLibs`/`--skip-libs`,
`-SkipVerify`/`--skip-verify`.

The manual steps below explain what the script does, for troubleshooting.

## Step-by-step replication (manual)

### Step 1. Copy the project onto the work laptop

Copy this whole `gae-local-dev/` folder to the laptop (zip it, or `git clone` if
you push it to a repo). Open it in VS Code.

### Step 2. Fill in secrets and config

```bash
cp .env.example .env
```

Edit `.env` and set:

- `GAE_USERNAME` / `GAE_PASSWORD` — your GAE license credentials.
  **Do not commit `.env`** (it is git-ignored). On real Glue, pull these from AWS
  Secrets Manager instead (see [Secrets](#handling-the-gae-license-securely)).
- `AWS_PROFILE` / `AWS_REGION` — the profile that can read your S3 + catalog.
- `GAE_LIB_S3_URI` — the S3 prefix holding the GAE jars/zip
  (default points at `s3://pske-prd-customerexperienceadhoc/maintenance/gae_lib/`).

### Step 3. Fetch the GAE libraries once

The GAE jars and Python zip are not redistributable, so we download them from your
S3 bucket into `./gae_libs/` (git-ignored):

```bash
bash scripts/fetch_gae_libs.sh
```

This pulls:
- `geoanalytics_2.12-2.0.0.jar`
- `geoanalytics-natives_2.12-2.0.0.jar`
- `geoanalytics-2.0.0.zip`

### Step 4. Verify the GAE license (do this FIRST)

Before writing any code, prove the container can start Spark, load the GAE plugin,
and authenticate. This is the highest-risk step — get it green before anything
else.

```bash
docker compose run --rm gae python scripts/verify_setup.py
```

Expected: `SPARK OK`, `GAE PLUGIN OK`, `GAE AUTH OK`. If auth fails, it is almost
always the license server being unreachable from your network — sort that with
your GIS admin before proceeding (offline license file is the fallback).

### Step 5. Run the unit tests (the fast loop)

No AWS or license needed for these — they run the pure spatial logic on tiny WKT
fixtures in `tests/fixtures/`:

```bash
docker compose run --rm gae pytest -q
```

This is your inner development loop: edit `src/transform.py`, save, re-run in
under a second. Add a new requirement as a new pure function + a new test.

### Step 6. Open an interactive shell / notebook

For exploration with the real backend (S3 + catalog via your mounted creds):

```bash
# Jupyter Lab in the container, reachable at http://localhost:8888
docker compose up gae-lab
```

A starter notebook is provided at `notebooks/explore.ipynb`, pre-wired to the
same `src/` code — it starts on the local fixtures and shows how to flip to the
real catalog.

Or a plain Python REPL / run a script:

```bash
docker compose run --rm gae python -m src.job --local     # runs on fixtures
docker compose run --rm gae python -m src.job --catalog   # runs on real Glue Catalog + S3
```

### Step 7. Develop a new requirement

1. Add a pure transform in `src/transform.py` (takes DataFrames, returns a
   DataFrame; no Glue/S3 imports). Example: buffer analysis, dwell time, a
   different aggregation.
2. Add a fixture + test in `tests/`. Iterate with Step 5.
3. Wire the I/O in `src/io_glue.py` and `src/job.py`.
4. Validate on real Glue (Tier 2) and copy `src/` into your Glue job.

---

## Project layout

```
gae-local-dev/
├── README.md                 <- you are here
├── .env.example              <- copy to .env, fill in
├── .gitignore
├── Dockerfile                <- Glue 5.0 base + dev tooling
├── compose.yaml              <- services: gae (run/test), gae-lab (Jupyter)
├── requirements-dev.txt
├── scripts/
│   ├── fetch_gae_libs.sh     <- download GAE jars/zip from S3 (once)
│   └── verify_setup.py       <- Spark + GAE plugin + auth + catalog smoke test
├── src/
│   ├── bootstrap_spark.py    <- SparkSession w/ GAE config (replaces %%configure)
│   ├── io_glue.py            <- catalog/S3 reads + writes (the swappable plumbing)
│   ├── transform.py          <- PURE ST_* spatial logic (testable anywhere)
│   └── job.py                <- wires it together; this is what Glue runs
├── tests/
│   ├── conftest.py           <- session-scoped Spark fixture
│   ├── fixtures/
│   │   ├── roadcalls_sample.csv
│   │   └── census_tract_sample.csv   (WKT polygons, git-friendly)
│   └── test_transform.py
└── gae_libs/                 <- (git-ignored) GAE jars land here
```

The key idea is the **`transform.py` / `io_glue.py` split**: analytics is pure and
runs identically local or in Glue; only the thin I/O layer differs. That is what
makes the same code testable locally *and* deployable to Glue unchanged.

---

## Mapping back to the original Glue notebook

| Notebook cell | Where it lives now |
|---|---|
| `%extra_jars` / `%extra_py_files` / `%%configure` | `src/bootstrap_spark.py` |
| `geoanalytics.auth(...)` (hardcoded) | `bootstrap_spark.py`, reads `.env` |
| `create_dynamic_frame.from_catalog(...)` | `io_glue.read_roadcalls_from_catalog` |
| `spark.read.csv(... s3 ...)` | `io_glue.read_roadcalls_from_csv` |
| `spark.read.format("shapefile")` | `io_glue.read_census_tracts_shapefile` |
| `ST.make_point` / `ST.srid` | `transform.add_point_geometry` |
| `ST_Intersects` join + `COUNT` group-by | `transform.roadcalls_per_tract` |
| `write.format("geoparquet")` / `saveAsTable` | `io_glue.write_*` |

---

## Debugging with breakpoints

Two ways, easiest first.

**A. Dev Container (recommended).** In VS Code, run **Dev Containers: Reopen in
Container** (`.devcontainer/devcontainer.json` opens VS Code *inside* the Glue
5.0 container). Now the interpreter, Spark, and GAE are the real ones. Set a
breakpoint in `src/transform.py`, open the Run & Debug panel, and pick one of
the ready-made configs in `.vscode/launch.json`:

- **Debug: pytest (current file)** — breakpoint-driven test run
- **Debug: all tests**
- **Debug: job.py --local**

Press F5.

**B. Remote attach (no Dev Container).** Launch the process under `debugpy` in
the container with port 5678 published, then attach with the **Attach: debugpy in
container (port 5678)** config:

```bash
docker compose run --rm -p 5678:5678 gae \
  python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m src.job --local
```

## Tier 2 — validate on real Glue

When you need to confirm behavior on the actual Glue backend without the browser
console:

```bash
pip install --upgrade "aws-glue-sessions"
jupyter kernelspec install --user "$(python -c 'import site;print(site.getsitepackages()[0])')/aws_glue_interactive_sessions_kernel/glue_pyspark"
```

Then in VS Code, open a notebook, pick the **Glue PySpark** kernel, and paste the
same `%extra_jars` / `%%configure` / `geoanalytics.auth` bootstrap the original
notebook used. Import your `src/transform.py` functions and run them against the
real catalog. Same editor, real backend.

---

## Handling the GAE license securely

The original notebook had `geoanalytics.auth(username="PTL_GAE", password="...")`
committed in plaintext. Here:

- **Local:** credentials come from `.env` (git-ignored), read by
  `bootstrap_spark.py`.
- **In Glue:** store them in **AWS Secrets Manager** and fetch at runtime:

  ```python
  import boto3, json
  sec = json.loads(boto3.client("secretsmanager").get_secret_value(
      SecretId="gae/license")["SecretString"])
  geoanalytics.auth(username=sec["username"], password=sec["password"])
  ```

Since the old password is already in git history, **rotate it**.

---

## Troubleshooting

- **`ST_Intersects not found` / no ST functions:** the GAE plugin didn't load —
  check the jar paths in `bootstrap_spark.py` match files in `./gae_libs/`.
- **`GAE AUTH failed`:** license server unreachable from your network, or wrong
  creds in `.env`. Test from Step 4 in isolation.
- **Catalog reads fail locally:** your AWS role lacks Glue/Lake Formation read
  perms. Fallback: read the table's underlying S3 path directly with
  `spark.read.parquet(...)`.
- **Out of memory on big reads:** you're on a laptop — always develop on a sampled
  subset (`.limit(...)` or a date filter). Full-scale runs belong in Glue.
