"""
Heuristic classifier: does a Regrid parcel record indicate the presence of
trucks / truck parking on that parcel?

IMPORTANT — what this can and can't tell you
----------------------------------------------
Regrid's parcel attributes do not contain a direct "trucks parked here" flag.
There is no field in the schema (checked live against
https://.../premium/FeatureServer/0) that says so explicitly. What we have
is land-use signal: zoning, zoning_type, zoning_subtype, and LBCS
(Land Based Classification Standards) codes (lbcs_activity/function/
structure/site), plus free-text owner/address/struct fields.

This classifier is therefore a PROXY, not a certainty:
  - A parcel zoned/coded industrial or transportation-related is LIKELY to
    have trucks on it, but "likely" is doing real work in that sentence.
  - A truck stop chain (Iowa 80, Pilot, Flying J, TA, Petro, Love's, ...) is
    reliably identifiable by owner-name keyword, but is classified by LBCS
    as generic "Retail" (2000) -- LBCS codes ALONE would miss it entirely.
    This was confirmed against a live Regrid response for the actual
    Iowa 80 Truckstop parcel (see real_fixtures.py).
  - Confirmed live against real data: industrial-zoned parcels near a real
    Amazon fulfillment center (Fall River, MA) carry lbcs_activity codes in
    the 3900 / 4300-series range and zoning_type "Industrial".
  - For full certainty ("is a truck physically parked there right now"),
    only aerial/satellite imagery analysis can confirm it. This classifier
    flags CANDIDATE parcels; treat the output as a prioritization signal for
    1,000,000 prospects, not a guarantee.

Rule tiers (in order of confidence)
------------------------------------
1. STRONG keyword match on owner/address/struct text against a curated list
   of truck-stop chains and trucking/logistics terminology.
2. Zoning is explicitly Industrial (zoning_type) -- covers warehouses,
   distribution centers, freight yards, manufacturing (all of which
   routinely have truck traffic/parking).
3. LBCS activity/function code falls in a transportation/warehousing/
   industrial range (4000-4999 transportation/utilities, 3000-3999
   manufacturing & wholesale trade) -- catches cases zoning text misses.
4. Zoning subtype "Special Commercial" combined with a weak keyword hit
   (e.g. "fuel", "travel", "plaza") -- lower confidence, many gas stations
   fall here without truck parking.

Anything not matching any tier is NOT flagged.
"""

import re

# --- Tier 1: known truck-stop / trucking / logistics operators & terms ------
TRUCK_KEYWORDS = [
    r"\bTRUCK\s*STOP\b", r"\bTRUCKSTOP\b", r"\bTRUCKING\b", r"\bTRUCK\s*TERMINAL\b",
    r"\bFREIGHT\b", r"\bLOGISTICS\b", r"\bDISTRIBUTION\s*CENTER\b", r"\bDISTRIBUTION\b",
    r"\bWAREHOUS", r"\bTRANSLOAD\b", r"\bINTERMODAL\b", r"\bCARRIER\b",
    r"\bTRAVEL\s*CENTER\b", r"\bTRAVEL\s*PLAZA\b", r"\bTRAVEL\s*STOP\b",
    r"\bWEIGH\s*STATION\b", r"\bTRUCK\s*WASH\b", r"\bTRAILER\b", r"\bFLEET\b",
    r"\bTRANSPORT(ATION)?\b", r"\bTERMINAL\b",
    # named chains / major carriers
    r"\bPILOT\b", r"\bFLYING\s*J\b", r"\bLOVE'?S\b", r"\bPETRO\b", r"\bTA\s*TRAVEL\b",
    r"\bIOWA\s*80\b", r"\bCAT\s*SCALE\b",
    r"\bSCHNEIDER\b", r"\bWERNER\b", r"\bSWIFT\s*TRANSPORT", r"\bJ\.?B\.?\s*HUNT\b",
    r"\bOLD\s*DOMINION\b", r"\bYRC\b", r"\bESTES\b", r"\bSAIA\b", r"\bXPO\b",
    r"\bFEDEX\s*(GROUND|FREIGHT)?\b", r"\bUPS\b", r"\bUSPS\b",
    r"\bPRIME\s*INC\b", r"\bLANDSTAR\b", r"\bKNIGHT[- ]SWIFT\b",
]
_TRUCK_KEYWORD_RE = re.compile("|".join(TRUCK_KEYWORDS), re.IGNORECASE)

# weaker keywords -- only count with other supporting signal
WEAK_KEYWORDS = [r"\bFUEL\b", r"\bTRAVEL\b", r"\bPLAZA\b", r"\bGAS\b", r"\bSTATION\b"]
_WEAK_KEYWORD_RE = re.compile("|".join(WEAK_KEYWORDS), re.IGNORECASE)

# --- Tier 2: zoning_type values treated as industrial ----------------------
INDUSTRIAL_ZONING_TYPES = {"industrial", "manufacturing", "warehouse"}

# --- Tier 3: LBCS activity/function codes -----------------------------------
# LBCS top-level function/activity buckets:
#   3000-3999 = Manufacturing & Wholesale Trade (includes warehousing/storage)
#   4000-4999 = Transportation, Communication, Information, Utilities
# Empirically confirmed live: lbcs_activity 3900 (industrial misc.), 4332 and
# lbcs_function 4310 (warehousing/transportation) at real industrial parcels;
# lbcs_activity 4000 at a major air-freight hub parcel.
def _in_industrial_or_transport_range(code):
    if not code:
        return False
    try:
        n = int(str(code)[:4])
    except ValueError:
        return False
    return 3000 <= n <= 4999


def classify_parcel(attrs: dict) -> dict:
    """
    attrs: the Regrid `attributes` dict for one parcel (may have missing/None
           fields -- real data is frequently sparse, as seen live).

    Returns a dict:
      {
        "truck_flag": bool,
        "confidence": "high" | "medium" | "low",
        "reasons": [str, ...],   # human-readable evidence, for audit/QA
      }
    """
    attrs = attrs or {}
    reasons = []

    text_fields = " ".join(
        str(attrs.get(f) or "") for f in ("owner", "address", "struct", "zoning_subtype")
    )

    strong_kw = _TRUCK_KEYWORD_RE.search(text_fields)
    if strong_kw:
        reasons.append(f"keyword match: '{strong_kw.group(0)}' in owner/address/struct")

    zoning_type = (attrs.get("zoning_type") or "").strip().lower()
    is_industrial_zoning = zoning_type in INDUSTRIAL_ZONING_TYPES
    if is_industrial_zoning:
        reasons.append(f"zoning_type = '{attrs.get('zoning_type')}'")

    lbcs_hit = None
    for f in ("lbcs_activity", "lbcs_function", "lbcs_structure"):
        code = attrs.get(f)
        if _in_industrial_or_transport_range(code):
            lbcs_hit = (f, code)
            reasons.append(f"{f} = {code} (industrial/transportation range)")
            break

    weak_kw = _WEAK_KEYWORD_RE.search(text_fields)
    zoning_subtype = (attrs.get("zoning_subtype") or "").strip().lower()
    special_commercial = "special commercial" in zoning_subtype

    # --- decision logic ---
    if strong_kw:
        confidence = "high" if (is_industrial_zoning or lbcs_hit) else "medium"
        return {"truck_flag": True, "confidence": confidence, "reasons": reasons}

    if is_industrial_zoning or lbcs_hit:
        confidence = "high" if (is_industrial_zoning and lbcs_hit) else "medium"
        return {"truck_flag": True, "confidence": confidence, "reasons": reasons}

    if special_commercial and weak_kw:
        reasons.append(f"zoning_subtype='Special Commercial' + weak keyword '{weak_kw.group(0)}'")
        return {"truck_flag": True, "confidence": "low", "reasons": reasons}

    return {"truck_flag": False, "confidence": "high", "reasons": ["no truck/logistics signal found"]}
