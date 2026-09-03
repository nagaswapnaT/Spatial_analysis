# Regrid Parcel Enrichment

This directory contains the Regrid parcel enrichment pipeline integrated into the Spatial Analysis project. It flags prospect locations as truck/truck-parking candidates using Regrid parcel data (zoning, LBCS codes, owner/address text).

## Project Structure

```
src/
  classify.py           — Heuristic parcel classifier (zoning, keywords, LBCS codes)
  regrid_client.py      — Regrid API client (LiveRegridClient) and test mock (MockRegridClient)
  real_fixtures.py      — Real Regrid API responses for 9 known locations (test data)

notebooks/
  regrid_enrichment.ipynb  — Main enrichment pipeline notebook (mock mode + live mode)

requirements-regrid.txt   — Python dependencies for regrid workflow
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements-regrid.txt
```

### 2. Get Mock Data

Copy `mock_prospect_points.parquet` from the truck_parcel_pipeline project into the project root:

```bash
cp /path/to/truck_parcel_pipeline/mock_prospect_points.parquet .
```

### 3. Run Notebook (Mock Mode - No Network)

Open `notebooks/regrid_enrichment.ipynb` and run all cells. Mock mode requires no internet access and produces synthetic results for testing.

### 4. Switch to Real Regrid API

1. **Get your Regrid API URL** from the Regrid dashboard
2. **Set the environment variable:**
   ```bash
   export REGRID_QUERY_URL="https://fs.regrid.com/<your-token>/rest/services/premium/FeatureServer/0/query"
   ```
3. **Update the notebook configuration cell:**
   ```python
   USE_MOCK = False
   MIN_INTERVAL_SECS = 0.3  # Adjust based on your Regrid plan
   LIMIT_ROWS = 100  # Start small
   ```
4. **Run the notebook** and monitor for rate-limit errors (429)

## Classification Rules

The `classify_parcel()` function flags parcels as truck/logistics-likely based on:

### Tier 1: Strong Keywords (High Confidence)
- Owner/address text matches truck stop chains (Pilot, Love's, TA Travel, Iowa 80, etc.)
- Text contains "TRUCK", "LOGISTICS", "DISTRIBUTION", "FREIGHT", "WAREHOUSE", "TERMINAL", etc.

### Tier 2: Industrial Zoning (Medium-High Confidence)
- `zoning_type` = "Industrial", "Manufacturing", "Warehouse"
- Associated with heavy vehicle traffic/parking

### Tier 3: LBCS Codes (Medium-High Confidence)
- LBCS activity/function codes in:
  - 3000-3999: Manufacturing & Wholesale Trade (warehousing, storage)
  - 4000-4999: Transportation, Utilities (freight, logistics)

### Tier 4: Special Commercial + Weak Keywords (Low Confidence)
- `zoning_subtype` = "Special Commercial" + text contains "fuel", "travel", "plaza"
- Common in truck stops/travel plazas but also many gas stations

## Rate Limiting

Regrid API has per-plan rate limits. Adjust `MIN_INTERVAL_SECS` based on your plan:

| Plan | Rate | Recommended Interval | Time for 1M |
|------|------|----------------------|------------|
| Starter | 1 req/sec | 1.0 | ~11.5 days |
| Growth | 5 req/sec | 0.2–0.3 | ~2–2.3 days |
| Professional | 10 req/sec | 0.1–0.15 | ~1–1.2 days |
| Enterprise | Negotiated | 0.05+ | Hours–days |

**If you see 429 "Too Many Requests" errors**: Increase `MIN_INTERVAL_SECS` in the configuration cell.

## Running at Scale (1M+ prospects)

For production runs with 1M+ prospects, use the command-line pipeline from truck_parcel_pipeline instead of the notebook:

```bash
export REGRID_QUERY_URL="https://fs.regrid.com/<token>/..."
python3 pipeline.py \
    --input prospects.parquet \
    --output enriched.csv \
    --id-col point_id --lat-col lat --lon-col lon \
    --workers 8 --min-interval 0.125
```

This is much faster due to parallel workers and better rate-limit handling.

## Files Reference

### `classify.py`
- `classify_parcel(attrs: dict) -> dict` — Main classification function
  - Input: Regrid parcel attributes dict (may have nulls)
  - Output: `{truck_flag: bool, confidence: "high"|"medium"|"low", reasons: [str, ...]}`

### `regrid_client.py`
- `LiveRegridClient(query_url, min_interval=0.2, max_retries=4, backoff_base=1.5)` — Real API
- `MockRegridClient(tolerance_deg=0.05)` — Local test mock
- Both have `query_point(lat, lon) -> attributes_dict or None`

### `real_fixtures.py`
- `FIXTURES` — 9 real Regrid API responses for known ground-truth locations
  - Used by `MockRegridClient` for known test points
  - Used by regression tests

## Troubleshooting

### "Input not found: mock_prospect_points.parquet"
Copy the file from truck_parcel_pipeline project:
```bash
cp /path/to/truck_parcel_pipeline/mock_prospect_points.parquet .
```

### "429 Too Many Requests" errors (rate limited)
Increase `MIN_INTERVAL_SECS` in the configuration cell. Example:
- Current: `0.2` (5 req/sec)
- Try: `0.3` (3.3 req/sec)
- Re-run notebook with same input file to resume

### "Connection timeout" or "403 Forbidden"
- Check your Regrid API URL (from dashboard)
- Test with `curl`: `curl "https://fs.regrid.com/<token>/..." -G --data-urlencode "..."`
- Note: This sandbox's egress cannot reach Regrid; run from your own machine or a server with normal internet

### Large dataset OOM
Stream processing: Set `LIMIT_ROWS` to process in smaller batches, or reduce `--workers` if running the CLI pipeline.

## Output Format

The enrichment pipeline writes CSV with columns:
```
point_id, lat, lon, truck_flag, confidence, reasons,
parcel_owner, parcel_address, parcel_zoning_type, parcel_zoning_subtype,
county, state, error
```

Example row:
```
12345,41.5772,-90.7477,True,high,"keyword match: 'TRUCK STOP' in owner/address/struct; zoning_type = 'Commercial'",IOWA 80 TRUCKSTOP INC,755 W IOWA 80 RD,Commercial,Special Commercial,scott,IA,
```

## Further Reading

- [Regrid API Documentation](https://regrid.com/docs/api)
- [LBCS Code Reference](https://www.planning.org/lbcs)
- `classify.py` module docstring for full classifier reasoning
- `real_fixtures.py` for known ground-truth test cases
