"""
Client(s) for looking up the parcel that contains a given lat/lon point via
Regrid's ArcGIS FeatureServer REST API.

LiveRegridClient
    Makes real HTTP calls. Requires network access to fs.regrid.com.
    THIS SANDBOX CANNOT REACH THAT HOST (outbound egress is allowlisted to a
    small set of domains and does not include fs.regrid.com -- confirmed by
    testing: direct curl/requests calls get a 403 from the egress proxy).
    Run this client on a machine/server that has normal internet access --
    we confirmed via browser automation on the user's own machine that
    fs.regrid.com is reachable and returns correct data from there.

MockRegridClient
    Stands in for LiveRegridClient during local development/testing in this
    sandbox. Returns real captured attribute payloads for known coordinates
    (see real_fixtures.py) and plausible-but-fake attributes for everything
    else, so the surrounding pipeline (chunking, concurrency, retries,
    checkpointing, output writing) can be fully built and tested without
    ever touching the real API.
"""

import json
import time
import random
import threading
import urllib.parse as up

try:
    import requests
except ImportError:  # requests may not be installed in every environment
    requests = None


class RegridQueryError(Exception):
    pass


class LiveRegridClient:
    def __init__(self, query_url, timeout=15, max_retries=4, backoff_base=1.5,
                 min_interval=0.0, out_fields=None):
        """
        query_url: the Regrid FeatureServer /query URL (includes the
                   embedded access token in the path -- treat as a secret).
        min_interval: minimum seconds between requests (simple client-side
                   rate limit; set based on your Regrid plan's rate limit).
        out_fields: list of field names to request; defaults to the fields
                   the classifier uses.
        """
        if requests is None:
            raise RuntimeError("The 'requests' package is required for LiveRegridClient "
                                "(pip install requests).")
        self.query_url = query_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.min_interval = min_interval
        self.out_fields = out_fields or [
            "address", "owner", "parcelnumb", "zoning", "zoning_type",
            "zoning_subtype", "lbcs_activity", "lbcs_function", "lbcs_site",
            "lbcs_structure", "struct", "county", "state2", "usps_vacancy",
            "ll_gisacre",
        ]
        self._session = requests.Session()
        self._last_call = 0.0
        self._throttle_lock = threading.Lock()

    def _throttle(self):
        """Thread-safe global rate limit across all worker threads sharing
        this client -- so --workers N and --min-interval together give you
        a predictable, global requests/sec ceiling regardless of N."""
        if self.min_interval <= 0:
            return
        with self._throttle_lock:
            elapsed = time.monotonic() - self._last_call
            wait = self.min_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def query_point(self, lat, lon):
        """Return the Regrid `attributes` dict for the parcel containing
        (lat, lon), or None if no parcel is found there."""
        geom = json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}})
        params = {
            "f": "json",
            "geometry": geom,
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": ",".join(self.out_fields),
            "returnGeometry": "false",
        }

        last_exc = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self._session.get(self.query_url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    raise RegridQueryError("rate limited (429)")
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise RegridQueryError(str(data["error"]))
                feats = data.get("features", [])
                if not feats:
                    return None
                return feats[0].get("attributes", {})
            except Exception as exc:  # noqa: BLE001 -- want to retry on anything transient
                last_exc = exc
                sleep_for = (self.backoff_base ** attempt) + random.uniform(0, 0.5)
                time.sleep(sleep_for)
        raise RegridQueryError(f"failed after {self.max_retries} attempts: {last_exc}")


class MockRegridClient:
    """Local stand-in for testing the pipeline without real network access."""

    def __init__(self, tolerance_deg=0.05):
        from .real_fixtures import FIXTURES
        # known coordinates pulled from generate_mock_data.py's KNOWN_POINTS
        self._known = [
            (41.5772, -90.7477, FIXTURES[0]["attributes"]),   # Iowa 80 (approx)
            (34.0633, -117.6509, {  # Pilot/truck stop-ish synthetic (Ontario CA slot)
                "owner": "PILOT TRAVEL CENTER LLC", "address": "SAMPLE TRUCK STOP RD",
                "zoning_type": "Commercial", "zoning_subtype": "Special Commercial",
                "lbcs_activity": "2000", "county": "san bernardino", "state2": "CA",
            }),
            (39.7684, -86.1581, FIXTURES[3]["attributes"]),   # FedEx hub-ish
            (41.7015, -71.1550, FIXTURES[6]["attributes"]),   # Amazon FC industrial park-ish
            (36.3729, -94.2088, FIXTURES[5]["attributes"]),   # Walmart HQ area (empty ROW)
            (41.7508, -88.1535, FIXTURES[1]["attributes"]),   # Naperville residential
            (38.9586, -77.3570, FIXTURES[2]["attributes"]),   # Reston Town Center
        ]
        self.tolerance_deg = tolerance_deg
        self._rng = random.Random(1234)

    def query_point(self, lat, lon):
        for klat, klon, attrs in self._known:
            if abs(lat - klat) < self.tolerance_deg and abs(lon - klon) < self.tolerance_deg:
                return attrs

        # synthetic fallback: mostly residential/commercial, a modest fraction
        # industrial, occasionally nothing found -- for pipeline load-testing only.
        r = self._rng.random()
        if r < 0.08:
            return None
        if r < 0.15:
            return {
                "owner": "GENERIC LOGISTICS WAREHOUSE LLC", "address": "100 DEPOT ST",
                "zoning_type": "Industrial", "zoning_subtype": "Industrial",
                "lbcs_activity": "3900", "county": "mock", "state2": "XX",
            }
        if r < 0.55:
            return {
                "owner": "JOHN Q PUBLIC", "address": "1 MAIN ST",
                "zoning_type": "Residential", "zoning_subtype": "Single Family",
                "lbcs_activity": "1100", "county": "mock", "state2": "XX",
            }
        return {
            "owner": "LOCAL RETAIL PLAZA LLC", "address": "200 COMMERCE AVE",
            "zoning_type": "Commercial", "zoning_subtype": "General Commercial",
            "lbcs_activity": "2000", "county": "mock", "state2": "XX",
        }
