"""
REAL Regrid FeatureServer responses captured live (via browser automation
routed through the user's own network, since fs.regrid.com is unreachable
from this sandbox directly) for a set of known ground-truth locations.

These are used as a regression test fixture for the classification rule in
classify.py -- NOT mock/synthetic data. Each entry is the actual `attributes`
object Regrid returned for a point-in-polygon query at that coordinate, plus
a human-assigned expected label based on what is actually at that location.

expected_truck: True  -> parcel should be flagged as having trucks/truck parking
expected_truck: False -> parcel should NOT be flagged
expected_truck: None  -> genuinely ambiguous / low-confidence ground truth;
                         excluded from pass/fail scoring, kept for reference
"""

FIXTURES = [
    {
        "label": "Iowa 80 Truckstop, Walcott IA (world's largest truck stop)",
        "expected_truck": True,
        "attributes": {
            "parcelnumb": "923033001", "zoning": "C-3", "zoning_type": "Commercial",
            "zoning_subtype": "Special Commercial", "struct": None,
            "owner": "IOWA 80 TRUCKSTOP INC", "address": "755 W IOWA 80 RD",
            "county": "scott", "state2": "IA", "ll_gisacre": 10.49548,
            "usps_vacancy": "N", "lbcs_activity": "2000", "lbcs_function": "2000",
            "lbcs_structure": "2000", "lbcs_site": "6000",
        },
    },
    {
        "label": "Single-family home, Naperville IL",
        "expected_truck": False,
        "attributes": {
            "parcelnumb": "0725213004", "zoning": "R1A", "zoning_type": "Residential",
            "zoning_subtype": "Single Family", "struct": None,
            "owner": "SCHERER, ADAM & BROOKE", "address": "1052 ALDER LN",
            "county": "dupage", "state2": "IL", "ll_gisacre": None,
            "usps_vacancy": "N", "lbcs_activity": "1100", "lbcs_function": "1100",
            "lbcs_structure": "1000", "lbcs_site": "6000",
        },
    },
    {
        "label": "Reston Town Center (retail/mixed-use, planned zoning)",
        "expected_truck": False,
        "attributes": {
            "parcelnumb": "0173 10 0008B", "zoning": "PRC", "zoning_type": "Planned",
            "zoning_subtype": "Planned", "struct": None,
            "owner": "RESTON TOWN CENTER PROPERTY LLC", "address": "1818 DISCOVERY ST",
            "county": "fairfax", "state2": "VA", "ll_gisacre": None,
            "usps_vacancy": "N", "lbcs_activity": "2300", "lbcs_function": None,
            "lbcs_structure": "2100", "lbcs_site": "6000",
        },
    },
    {
        "label": "FedEx Express World Hub parcel, Indianapolis Intl Airport",
        "expected_truck": True,
        "attributes": {
            "parcelnumb": "2000474", "zoning": "SU46", "zoning_type": "Special",
            "zoning_subtype": "Special", "struct": None,
            "owner": "INDIANAPOLIS AIRPORT AUTHORITY, INDPLS INTERNATL AIRPORT",
            "address": "7800 COL H WEIR COOK MEM DR", "county": "marion", "state2": "IN",
            "ll_gisacre": 658.88546, "usps_vacancy": "N",
            "lbcs_activity": "4000", "lbcs_function": "6200",
            "lbcs_structure": "4000", "lbcs_site": "6000",
        },
    },
    {
        "label": "Kentucky DOT parcel adjacent to UPS Worldport, Louisville",
        "expected_truck": None,  # ambiguous: DOT/airport ROW land, not itself an operating trucking use
        "attributes": {
            "parcelnumb": "063000710000", "zoning": "EZ1", "zoning_type": "Special",
            "zoning_subtype": "Special", "struct": None,
            "owner": "COMMONWEALTH OF KENTUCKY DEPARTMENT", "address": "6600 GRADE LN",
            "county": "jefferson", "state2": "KY", "ll_gisacre": 3.78824,
            "usps_vacancy": None, "lbcs_activity": None, "lbcs_function": None,
            "lbcs_structure": None, "lbcs_site": None,
        },
    },
    {
        "label": "Empty state-highway ROW near Walmart HQ, Bentonville AR",
        "expected_truck": False,
        "attributes": {
            "parcelnumb": "01-99999-999", "zoning": None, "zoning_type": None,
            "zoning_subtype": None, "struct": None, "owner": None, "address": None,
            "county": "benton", "state2": "AR", "ll_gisacre": 117.62049,
            "usps_vacancy": None, "lbcs_activity": None, "lbcs_function": None,
            "lbcs_structure": None, "lbcs_site": None,
        },
    },
    {
        "label": "960 Innovation Way, Fall River MA (industrial park near Amazon BOS7 FC)",
        "expected_truck": True,
        "attributes": {
            "parcelnumb": "W-19-0186", "zoning": "IP", "zoning_type": "Industrial",
            "zoning_subtype": "Industrial", "struct": None,
            "owner": "FALL RIVER INNOVATION SOLAR HOLDINGS LLC",
            "address": "960 INNOVATION WAY", "county": "bristol", "state2": "MA",
            "ll_gisacre": 35.07192, "usps_vacancy": None,
            "lbcs_activity": "4332", "lbcs_function": "4310",
            "lbcs_structure": "6400", "lbcs_site": "6000",
        },
    },
    {
        "label": "875 Innovation Way, Fall River MA (vacant industrial lot)",
        "expected_truck": True,
        "attributes": {
            "parcelnumb": "W-19-0189", "zoning": "IP", "zoning_type": "Industrial",
            "zoning_subtype": "Industrial", "struct": False,
            "owner": "VMD INDUSTRIAL FR LLC", "address": "875 INNOVATION WAY",
            "county": "bristol", "state2": "MA", "ll_gisacre": 23.3582,
            "usps_vacancy": "Y", "lbcs_activity": "3900", "lbcs_function": None,
            "lbcs_structure": None, "lbcs_site": "1000",
        },
    },
    {
        "label": "Browning Ferris Industries waste facility, Airport Rd, Fall River MA",
        "expected_truck": True,
        "attributes": {
            "parcelnumb": "Z-03-0033", "zoning": "IP", "zoning_type": "Industrial",
            "zoning_subtype": "Industrial", "struct": False,
            "owner": "BROWNING FERRIS INDUSTRIES INC", "address": "AIRPORT RD",
            "county": "bristol", "state2": "MA", "ll_gisacre": 201.61353,
            "usps_vacancy": None, "lbcs_activity": "3900", "lbcs_function": None,
            "lbcs_structure": None, "lbcs_site": "1000",
        },
    },
]
