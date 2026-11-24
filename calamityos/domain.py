"""Deterministic Andhra Pradesh relief scenario. All account records are synthetic."""

import calendar
import hashlib
import json
import math
import random
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache


# These independent demo dates make the impact of a test-date choice inspectable.
ANCHORS = {
    "occurrence": ("Occurrence date", "2026-09-26"),
    "declaration": ("Declaration date", "2026-10-02"),
    "reference": ("Committee reference", "2026-10-01"),
}
AREAS = {
    "Kalyandurg": "Severe", "Rayadurg": "Severe", "Gooty": "Moderate",
    "Uravakonda": "Severe", "Dharmavaram": "Moderate", "Kadiri": "Severe",
    "Tadipatri": "Moderate", "Guntakal": "Moderate",
}
SOURCES = [
    {"title": "RBI · Resolution of Stressed Assets", "label": "Rule reference",
     "excerpt": "124J checks all facilities on the occurrence date, with declaration as fallback when occurrence cannot be ascertained. 124N covers deemed invocation and borrower opt-out.",
     "url": "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=13408&Mode=0"},
    {"title": "RBI · Income recognition and provisioning", "label": "Rule reference",
     "excerpt": "84A–84C cover additional provision, repeat relief and the repayment threshold for write-back.",
     "url": "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx?Id=13409"},
    {"title": "AP special SLBC · 6 October 2026", "label": "Secondary report",
     "excerpt": "Project dossier §12b summarises a 1 October reference date, a 12-month moratorium and repayment caps of 36 or 60 months by severity. Primary minutes are pending.",
     "url": "https://www.thehansindia.com/news/cities/vijayawada/banks-to-ease-loan-burden-of-drought-hit-farmers-1129834"},
    {"title": "AP Gazette 772 · 1 October 2026", "label": "Published declaration",
     "excerpt": "G.O.Ms.No.4 is dated 1 October 2026. The three-date exercise deliberately moves the declaration one day later to demonstrate the effect of a conflicting date.",
     "url": "https://egazette.servantsofknowledge.in/details/in.gazette.andhra_extraordinary.2026-10-01.772/"},
    {"title": "Scenario assumptions", "label": "Illustrative",
     "excerpt": "Occurrence and replay declaration dates, local area tiers, loan records, loss list and approval history are illustrative inputs for the date-sensitivity exercise.",
     "url": None},
]


def money(amount):
    return float(Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _payment(balance, rate, months):
    if not rate:
        return balance / months
    return balance * rate / (1 - (1 + rate) ** -months)


def plan_options(principal, rate, months, tier, moratorium=12):
    """Sizing estimates. A booked offer must use its saved core simulation."""
    principal, annual = Decimal(str(principal)), Decimal(str(rate)) / 100
    if months < 1 or principal <= 0 or annual < 0:
        raise ValueError("Invalid repayment terms")
    cap = {"Severe": 60, "Moderate": 36}[tier]
    monthly = annual / 12
    balance = principal * (1 + monthly * moratorium)
    original = _payment(principal, monthly, months)
    tenor = min(months, cap)
    options = []
    for label in ("A", "B"):
        if label == "B":
            while tenor < cap and _payment(balance, monthly, tenor) > original:
                tenor += 1
        emi = _payment(balance, monthly, tenor)
        options.append({"id": label, "months": tenor, "moratorium": moratorium,
                        "emi": money(emi), "original_emi": money(original),
                        "extra_interest": money(emi * tenor - original * months),
                        "cap_reached": tenor == cap, "tenor_cap": cap})
    return options


def additional_provision(outstanding, prior_provision=0):
    debt = Decimal(str(outstanding))
    capacity = max(Decimal(0), debt - Decimal(str(prior_provision)))
    return money(min(debt * Decimal("0.05"), capacity))


def conversion_options(principal, rate, months, tier, moratorium=12):
    """Compare projected term-loan repayments to one original bullet due."""
    principal, annual = Decimal(str(principal)), Decimal(str(rate)) / 100
    if months < 1 or principal <= 0 or annual < 0:
        raise ValueError("Invalid bullet terms")
    original_due = principal * (1 + annual * months / 12)
    balance = principal * (1 + annual * moratorium / 12)
    cap = {"Severe": 60, "Moderate": 36}[tier]
    result = []
    for label, tenor in (("A", 36), ("B", 60)):
        if tenor > cap:
            continue
        emi = _payment(balance, annual / 12, tenor)
        result.append({"id": label, "months": tenor, "moratorium": moratorium, "emi": money(emi),
                       "original_emi": None, "original_maturity_due": money(original_due),
                       "extra_interest": money(emi * tenor - original_due), "cap_reached": tenor == cap,
                       "tenor_cap": cap})
    return result


def write_back_due(outstanding_at_implementation, repaid, slipped=False, restructured_again=False):
    return (not slipped and not restructured_again
            and Decimal(str(repaid)) >= Decimal(str(outstanding_at_implementation)) / 5)


def last_safe_business_day(deadline):
    day = deadline
    while day.weekday() == calendar.SUNDAY or (
            day.weekday() == calendar.SATURDAY and (day.day - 1) // 7 in (1, 3)):
        day -= timedelta(days=1)
    return day


_GIVEN = ("Lakshmi", "Sravani", "Ravi", "Padma", "Nagesh", "Meena", "Anand", "Kavya",
          "Harini", "Suresh", "Saroja", "Mohan", "Vijaya", "Kiran", "Sandhya",
          "Prasad", "Sailaja", "Ramesh", "Devi", "Bharat")
_FAMILY = ("Reddy", "Naidu", "Rao", "Kumar", "Maddala", "Kota", "Palla", "Ganta",
           "Katuri", "Challa", "Meda", "Soma", "Nandi", "Kona", "Dandu")
_PRODUCTS = (("Agricultural term loan", "EMI"), ("Tractor loan", "EMI"),
             ("Crop loan", "BULLET"), ("Farm equipment loan", "EMI"),
             ("Crop credit line", "REVOLVING"))


@lru_cache(maxsize=1)
def _book():
    rng = random.Random(26112026)
    rows = []
    for n in range(1, 301):
        area = list(AREAS)[(n - 1) % len(AREAS)]
        group = n % 20
        if n > 2 and group == 8:
            area = "Outside declared area"
        if n > 2 and group == 9:
            area = "Unresolved location"
        facilities = []
        for j in range(2 if n == 2 or n > 2 and n % 5 < 3 else 1):
            prod, repayment = _PRODUCTS[(n - 1) % len(_PRODUCTS)] if not j else _PRODUCTS[1]
            if n == 2 and not j:
                prod, repayment = _PRODUCTS[2]
            dpd = rng.randint(0, 15)
            values = [dpd, dpd + 4, dpd + 3]
            if n > 2 and group in (3, 4) and not j:
                values = [27, 33, 30 if group == 3 else 31]
            if n > 2 and group == 5 and not j:
                values = [35, 0, 2]
            if n > 2 and group == 6 and not j:
                values = [43, 49, 48]
            if n == 2 and j:
                values = [30, 31, 30]
            snaps = {key: {"date": anchor[1], "dpd": value, "classification":
                            "Substandard" if n > 2 and group == 10 and not j else "Standard"}
                     for (key, anchor), value in zip(ANCHORS.items(), values)}
            if n > 2 and group == 11 and not j:
                snaps.pop("occurrence")
            facilities.append({"id": f"LN-{n:04}-{j+1}", "product": prod, "repayment": repayment,
                               "principal": 500000 if n == 1 else rng.randrange(30, 500) * 1000,
                               "rate": 10 if n == 1 else rng.choice((8, 9, 10, 11)),
                               "months": 36 if n == 1 else rng.choice((24, 30, 36)),
                               "mandal": area, "tier": AREAS.get(area, "Unassigned"),
                               "snapshots": snaps})
            if repayment == "BULLET":
                facilities[-1]["months"] = 12
        rows.append({"id": f"AP-{n:04}", "name": f"{_GIVEN[(n-1) % 20]} {_FAMILY[(n-1)//20]}",
                     "facilities": facilities, "loss_matched": group != 12,
                     "refinance": group == 13, "covered_purpose": group != 14,
                     "old_relief": group == 15, "guarantor": group == 16})
    return rows


def _decision(row, reading):
    first = row["facilities"][0]
    if first["mandal"] == "Unresolved location":
        return "Review", "AREA_UNRESOLVED", "Land location requires confirmation."
    if first["mandal"] not in AREAS:
        return "Ineligible", "AREA_OUT_OF_SCOPE", "Activity is outside the declared area."
    if row["old_relief"]:
        return "Ineligible", "OLD_NORMS", "Existing relief continues under prior norms. No fresh resolution is proposed for this case."
    for facility in row["facilities"]:
        snap = facility["snapshots"].get(reading)
        if not snap:
            return "Review", "SNAPSHOT_MISSING", f"No exact-date snapshot for {facility['id']}."
        if snap["classification"] != "Standard":
            return "Ineligible", "NOT_STANDARD", f"{facility['id']} was classified Substandard."
        if snap["dpd"] > 30:
            return ("Ineligible", "DPD_GT_30", f"{facility['product']} {facility['id']} was "
                    f"{snap['dpd']} days overdue ({snap['dpd'] - 30} above the limit).")
    if row["refinance"]:
        return "Ineligible", "REFINANCE_EXCLUDED", "Refinance portfolio is excluded."
    if not row["covered_purpose"]:
        return "Ineligible", "PURPOSE_NOT_COVERED", "Loan purpose falls outside the event terms."
    if not row["loss_matched"]:
        return "Review", "IMPACT_EVIDENCE_PENDING", "No match in the illustrative loss list."
    if row["guarantor"]:
        return "Eligible", "GUARANTOR_MANUAL_PATH", "Criteria met. Guarantor check requires branch handling."
    return "Eligible", "ALL_CHECKS_PASSED", "Area, all facility snapshots and loss evidence match."


def _row(row, reading):
    status, code, reason = _decision(row, reading)
    first = row["facilities"][0]
    debt = sum(loan["principal"] for loan in row["facilities"])
    eligible = status == "Eligible"
    bookable = eligible and first["repayment"] in ("EMI","BULLET") and not row["guarantor"]
    relief_type = {"EMI":"RESCHEDULE","BULLET":"CONVERSION","REVOLVING":"BRANCH_REFERRAL"}[first["repayment"]]
    sizing = conversion_options if relief_type == "CONVERSION" else plan_options
    snaps = [loan["snapshots"].get(reading) for loan in row["facilities"]]
    digest = hashlib.sha256(json.dumps(snaps, sort_keys=True).encode()).hexdigest()
    # The ledger below is a separate, illustrative servicing snapshot. The
    # default relief simulation never writes an actual accounting entry.
    position = int(row["id"][-4:])
    previous_relief = position % 7 == 0
    repaid = debt * ((position % 5) * 6) // 100 if previous_relief else 0
    slipped = previous_relief and position % 9 == 0
    subsequent = previous_relief and position % 11 == 0
    eligible_write_back = previous_relief and write_back_due(debt, repaid, slipped, subsequent)
    revolving_only = all(f["repayment"] == "REVOLVING" for f in row["facilities"])
    prudential = {"previous_relief": previous_relief, "measurement": "At implementation (illustrative)",
                  "prior_provision": additional_provision(debt) if previous_relief else 0,
                  "repayment_target": money(Decimal(debt) / 5), "repaid": repaid,
                  "slipped": slipped, "restructured_again": subsequent,
                  "write_back_due": eligible_write_back and not revolving_only,
                  "write_back_route": "Branch review of one-year default history" if revolving_only else "20% repayment"}
    return {**row, "reading": reading, "facility_id": first["id"], "product": first["product"],
            "mandal": first["mandal"], "tier": first["tier"], "status": status, "reason": reason,
            "relief_type": relief_type,
            "reason_codes": [code], "outstanding": debt, "bookable": bookable,
            "provision": additional_provision(debt) if eligible else 0,
            "prudential": prudential, "snapshot_hash": digest,
            "max_dpd": max((s["dpd"] for s in snaps if s), default=None),
            "plans": sizing(first["principal"], first["rate"], first["months"], first["tier"])
            if bookable else []}


def milestones_for(declared, day_count):
    if day_count not in ("include_first", "exclude_first"):
        raise ValueError("Unknown day-count setting")
    shift = int(day_count == "include_first")
    return [{"label": label, "day": offset, "date": (declared + timedelta(days=offset-shift)).isoformat()}
            for offset, label in ((15, "Committee meeting"), (45, "Borrower-request invocation"),
                                  (75, "Extended request invocation"), (135, "Implementation and opt-out"))]


def _clock(as_of, day_count, remaining):
    declared = date.fromisoformat(ANCHORS["declaration"][1])
    today = date.fromisoformat(as_of)
    milestones = milestones_for(declared, day_count)
    deadline = date.fromisoformat(milestones[-1]["date"])
    left = (deadline - today).days
    return {"as_of": as_of, "deadline": deadline.isoformat(), "days_left": max(0, left),
            "elapsed": max(0, (today-declared).days), "needed_per_day": math.ceil(remaining/left) if left > 0 else None,
            "remaining_cases": remaining, "last_safe_business_day": last_safe_business_day(deadline).isoformat(),
            "milestones": milestones}


def _policy_readings(borrowers):
    bookable = [b for b in borrowers if b["bookable"]]
    multi = [b for b in bookable if len(b["facilities"]) > 1]
    all_debt = sum(b["provision"] for b in bookable)
    primary_only = sum(additional_provision(b["facilities"][0]["principal"]) for b in bookable)
    # A hypothetical subsequent cyclone overlaps two mandals after drought
    # relief has been implemented. Use first-time drought cases for a clean
    # two-event comparison with identical starting balances on both paths.
    overlap = [b for b in bookable if b["mandal"] in ("Kalyandurg", "Rayadurg")
               and not b["prudential"]["previous_relief"]]
    once = sum(b["provision"] for b in overlap)
    twice = once + sum(additional_provision(b["outstanding"], b["provision"]) for b in overlap)

    def option(key, label, total, default, affected, cash=0):
        return {"id": key, "label": label, "provision": total, "delta": total-default,
                "affected_count": len(affected), "affected_ids": [b["id"] for b in affected],
                "cash_basis_count": cash}

    return [
        {"id": "repeat", "title": "Second calamity", "illustrative": True, "cohort": len(overlap),
         "context": "Illustrative cyclone after drought relief in Kalyandurg and Rayadurg. Compare total provision held across both events for this same cohort.",
         "options": [option("repeat", "Repeat restructuring", twice, twice, [], len(overlap)),
                     option("first", "First instance", once, twice, overlap)]},
        {"id": "provision_base", "title": "Provision base", "illustrative": False, "cohort": len(bookable),
         "context": "Compare additional provision on each bookable case using total borrower debt or only the proposed relief facility.",
         "options": [option("total", "All outstanding debt", all_debt, all_debt, []),
                     option("relieved", "Relieved facility only", primary_only, all_debt, multi)]},
    ]


def dashboard(reading="occurrence", day_count="exclude_first", as_of="2026-11-20"):
    if reading not in ANCHORS or day_count not in ("exclude_first", "include_first"):
        raise ValueError("Unknown date reading")
    borrowers = [_row(row, reading) for row in _book()]
    counts = Counter(row["status"] for row in borrowers)
    readings = []
    for key, (label, date_string) in ANCHORS.items():
        flips = []
        eligible, provision = 0, 0
        for row in borrowers:
            status, code, reason = _decision(row, key)
            if status == "Eligible":
                eligible += 1
                provision += additional_provision(row["outstanding"])
            if status != row["status"]:
                flips.append({"id": row["id"], "name": row["name"], "from_status": row["status"],
                              "to_status": status, "reason": reason if status != "Eligible" else row["reason"],
                              "reason_code": code})
        readings.append({"id": key, "label": label, "date": date_string, "eligible": eligible,
                         "provision": provision, "flips": flips})
    areas = Counter(row["mandal"] for row in borrowers)
    event = {"id": "AP-DR-2026", "title": "Andhra Pradesh drought", "state": "Andhra Pradesh",
             "declared_on": ANCHORS["declaration"][1], "occurrence": ANCHORS["occurrence"][1],
             "reference": ANCHORS["reference"][1], "committee_date": "2026-10-06",
             "mandals": [{"name": name, "tier": tier, "count": areas[name]} for name, tier in AREAS.items()],
             "sources": SOURCES, "rule_version": "AP-2026.1", "illustrative": True}
    metrics = {"total": len(borrowers), "eligible": counts["Eligible"], "review": counts["Review"],
               "ineligible": counts["Ineligible"], "provision": sum(b["provision"] for b in borrowers),
               "bookable": sum(b["bookable"] for b in borrowers)}
    return {"event": event, "reading": reading, "day_count": day_count, "borrowers": borrowers,
            "policy_readings": _policy_readings(borrowers),
            "readings": readings, "metrics": metrics, "clock": _clock(as_of, day_count, metrics["eligible"])}
