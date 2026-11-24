"""SQLite-backed, deterministic relief workflow for the synthetic AP portfolio."""
import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from . import domain
from .intake import EXAMPLE, extract
from .mock_core import add_months


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(canonical(data).encode()).hexdigest()


def check_schedule(approved, booked, limits=None):
    """Compare the actual core schedule with the frozen simulation and policy limits."""
    diff = []

    def difference(field, expected, actual):
        diff.append({"field": field, "approved": expected, "booked": actual})

    for key in sorted(set(approved) | set(booked)):
        if key != "rows" and approved.get(key) != booked.get(key):
            difference(key, approved.get(key), booked.get(key))
    expected, actual = approved.get("rows", []), booked.get("rows", [])
    if not isinstance(actual, list):
        difference("rows", "payment schedule", actual)
        return diff
    if len(expected) != len(actual):
        difference("instalment_count", len(expected), len(actual))
    for number, (left, right) in enumerate(zip(expected, actual), 1):
        if not isinstance(right, dict):
            difference("instalment %d" % number, left, right)
            continue
        for key in sorted(set(left) | set(right)):
            if left.get(key) != right.get(key):
                difference("instalment %d · %s" % (number, key), left.get(key), right.get(key))
    if limits:
        for key in ("moratorium_months", "tenor", "extra_interest"):
            value = booked.get(key)
            if key in limits and isinstance(value, (float, int)) and value > limits[key]:
                difference("policy · " + key, limits[key], value)
        if "deadline" in limits and str(booked.get("effective", "")) > limits["deadline"]:
            difference("implementation deadline", limits["deadline"], booked["effective"])
        holiday_end = add_months(date.fromisoformat(approved["effective"]), approved["moratorium_months"])
        for row in actual:
            if isinstance(row, dict) and str(row.get("due", "")) < holiday_end.isoformat():
                difference("payment inside moratorium", holiday_end.isoformat(), row.get("due"))
    return diff


def signers(payload):
    maker, checker = (str(payload.get(k) or "").strip() for k in ("maker", "checker"))
    if not maker or not checker or maker.casefold() == checker.casefold():
        raise ValueError("Choose two different officers for maker and checker.")
    if max(len(maker), len(checker)) > 80:
        raise ValueError("Officer names must be 80 characters or fewer.")
    return maker, checker


class Workflow:
    def __init__(self, db_path):
        self.path = Path(db_path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.core_path = self.path.with_name(self.path.name + ".core")
        with closing(sqlite3.connect(str(self.path), timeout=30)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY, data TEXT)")
            if not db.execute("SELECT 1 FROM workspace WHERE id=1").fetchone():
                db.execute("INSERT INTO workspace VALUES (1,?)", (canonical(self._seed(1)),))

    def _core(self, method, **args):
        call = subprocess.run([sys.executable, str(Path(__file__).with_name("mock_core.py")), str(self.core_path)],
                              input=canonical({"method": method, "args": args}).encode(),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        if call.returncode == 75 and method in ("confirm", "convert"):
            result = self._core("read", key=args["key"])
            if result:
                return result
        if call.returncode:
            raise RuntimeError("The mock lending core could not complete " + method)
        return json.loads(call.stdout)

    @staticmethod
    def _log(state, kind, plan, message):
        entries = state["ledger"]
        entry = {"seq": len(entries) + 1, "day": state["as_of"], "kind": kind, "plan_id": plan,
                 "message": message, "prev_hash": entries[-1]["hash"] if entries else "0" * 64}
        entries.append(dict(entry, hash=digest(entry)))

    def _seed(self, generation):
        state = {"as_of": "2026-11-16", "generation": generation, "plans": [], "ledger": [],
                 "paused": False, "kill_switch": False, "settings":
                 {"reading": "occurrence", "day_count": "exclude_first", "maker": "A. Rao",
                  "checker": "L. Devi", "version": 1}}
        self._log(state, "RULE_APPROVED", "", "Illustrative AP rule v1 approved by A. Rao and L. Devi.")
        book = domain.dashboard()
        batch = [b for b in book["borrowers"] if b["bookable"] and b["facilities"][0]["repayment"] == "EMI"][:6]
        for i, borrower in enumerate(batch):
            p = self._draft(state, borrower, "A")
            if i < 5:
                self._change(state, "approve", {"plan_id": p["id"], "maker": "A. Rao", "checker": "L. Devi"})
            if i < 4:
                self._change(state, "notify", {"plan_id": p["id"]})
            if i == 3:
                self._change(state, "object", {"plan_id": p["id"]})
        state["as_of"] = "2026-11-20"
        self._change(state, "book", {"plan_id": state["plans"][0]["id"]})
        crop = next((b for b in book["borrowers"] if b["bookable"] and b["facilities"][0]["repayment"] == "BULLET"), None)
        if crop:
            self._draft(state, crop, "A")
        return state

    def _draft(self, s, borrower, option, source_record=None):
        if not borrower or not borrower["bookable"]:
            raise ValueError("Select an eligible facility that supports automatic relief.")
        if borrower.get("reading") != s["settings"]["reading"]:
            raise ValueError("The eligibility reading changed. Reload this borrower.")
        selected = next((v for v in borrower["plans"] if v["id"] == option), None)
        if not selected:
            raise ValueError("Choose a simulation option for this facility.")
        existing = next((p for p in s["plans"] if p["facility_id"] == borrower["facility_id"]), None)
        if existing and existing["status"] != "DRAFT":
            raise ValueError("This facility already has a signed plan.")
        version = existing["plan_version"] + 1 if existing else 1
        settings = s["settings"]
        loan = borrower["facilities"][0]
        approved = self._core("simulate", loan=loan, tenor=selected["months"],
                              holiday=selected["moratorium"], effective=s["as_of"])
        original = self._core("simulate", loan=loan, tenor=loan["months"], holiday=0, effective=s["as_of"])
        if abs(approved["emi"] - selected["emi"]) > 1 or abs(approved["extra_interest"] - selected["extra_interest"]) > 1:
            raise ValueError("Simulation differs from the sizing estimate by more than one rupee.")
        day = date.fromisoformat(domain.ANCHORS["declaration"][1])
        deadline = day + timedelta(days=135 - int(settings["day_count"] == "include_first"))
        p = {"id": existing["id"] if existing else "PL-%04d" % (len(s["plans"]) + 1),
             "borrower_id": borrower["id"], "name": borrower["name"], "facility_id": loan["id"],
             "status": "DRAFT", "approved": approved, "original": original, "booked": None, "notice": "",
             "objection_deadline": None, "provision": borrower["provision"], "posted_provision": 0,
             "txn_ref": "", "diff": [], "option": option, "deadline": deadline.isoformat(),
             "reading": settings["reading"], "day_count": settings["day_count"], "rule_version": settings["version"],
             "plan_version": version, "snapshot_hash": borrower["snapshot_hash"], "rule_maker": settings["maker"],
             "rule_checker": settings["checker"], "maker": "", "checker": "", "approved_hash": "",
             "source": "AP scenario excerpt · committee terms and RBI 124J / 124N",
             "source_record": source_record or {"maker": settings["maker"], "checker": settings["checker"],
                                                "fields": extract(EXAMPLE), "source": "Seeded illustrative AP brief"},
             "reason_codes": list(borrower["reason_codes"]),
             "relief_type": "CONVERSION" if loan["repayment"] == "BULLET" else "RESCHEDULE",
             "tier_cap": 60 if borrower["tier"].lower() == "severe" else 36}
        p["source_excerpt"] = next((f["quote"] for f in p["source_record"]["fields"] if f["label"] == "Moratorium"), "")
        if existing:
            s["plans"][s["plans"].index(existing)] = p
        else:
            s["plans"].append(p)
        self._log(s, "SIMULATED", p["id"], "Mock simulation %s for %s under rule v%s." %
                  (option, loan["id"], settings["version"]))
        return p

    def _verify(self, s, p, result):
        p["booked"] = result["booked"]
        limits = {"tenor": p["tier_cap"], "moratorium_months": 12, "deadline": p["deadline"],
                  "extra_interest": p["approved"]["extra_interest"]}
        p["diff"] = check_schedule(p["approved"], p["booked"], limits)
        if digest(p["approved"]) != p["approved_hash"]:
            p["diff"].append({"field": "approval hash", "approved": p["approved_hash"], "booked": digest(p["approved"])})
        p["status"] = "MISMATCH" if p["diff"] else "VERIFIED"
        if p["diff"]:
            s["paused"] = True
        else:
            p["posted_provision"] = p["provision"]
        self._log(s, p["status"], p["id"], "Batch paused after a schedule difference." if p["diff"]
                  else "Core schedule matches the signed simulation · " + p["txn_ref"])

    def _batch(self, s, request):
        op = request.get("operation")
        required = {"approve": "DRAFT", "notify": "APPROVED", "book": "NOTIFIED"}
        if op not in required:
            raise ValueError("Select approve, notify or book.")
        ids = request.get("plan_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("Select one or more distinct plans for the batch.")
        by_id = {p["id"]: p for p in s["plans"]}
        if any(i not in by_id for i in ids):
            raise ValueError("The selection includes an unknown plan.")
        sign = dict(zip(("maker", "checker"), signers(request))) if op == "approve" else {}
        fault, target = request.get("fault") or "", request.get("fault_plan_id")
        if fault and (op != "book" or target not in ids or fault not in
                      ("shifted_date", "wrong_amount", "missing_event", "timeout_after_commit")):
            raise ValueError("Choose a supported fault and a selected booking plan.")
        if target and not fault:
            raise ValueError("Select a fault for the demonstration.")
        receipt = digest([op, [(i, by_id[i]["plan_version"]) for i in ids], sign, fault, target])
        history = s.setdefault("batch_receipts", {})
        result = history.get(receipt)
        if result and not result.get("error"):
            s["batch_result"] = result
            return
        done = result["processed"][:] if result else []
        remaining = [i for i in ids if i not in done]
        # Validate the whole selection before sending any instruction to the core.
        if op == "book" and (s["paused"] or s["kill_switch"]):
            raise ValueError("New bookings are paused.")
        for i in remaining:
            p = by_id[i]
            if p["status"] != required[op]:
                raise ValueError("%s is %s. %s requires %s." % (i, p["status"], op, required[op]))
            if op == "approve" and (p["rule_version"] != s["settings"]["version"] or s["as_of"] > p["deadline"]):
                raise ValueError("%s requires a current rule and an open implementation window." % i)
            if op == "book" and not p["objection_deadline"] < s["as_of"] <= p["deadline"]:
                raise ValueError("%s is outside its booking window." % i)
        result = {"operation": op, "processed": done, "stopped_at": None, "remaining": [], "error": None}
        for index, i in enumerate(remaining):
            try:
                self._change(s, op, dict(sign, plan_id=i, fault=fault if i == target else ""))
            except (RuntimeError, subprocess.TimeoutExpired, OSError) as error:
                result.update(stopped_at=i, remaining=remaining[index:], error=str(error))
                break
            done.append(i)
            if op == "book" and by_id[i]["status"] == "MISMATCH":
                result.update(stopped_at=i, remaining=remaining[index + 1:])
                break
        self._log(s, "BATCH", "", "%s processed %s of %s selected plans." % (op.capitalize(), len(done), len(ids)))
        history[receipt] = s["batch_result"] = result

    @staticmethod
    def _catchup(p, as_of):
        original = p.get("original")
        if original:
            return round(sum(row["amount"] for row in original["rows"] if row["due"] <= as_of), 2)
        start, today = date.fromisoformat(p["approved"]["effective"]), date.fromisoformat(as_of)
        months = sum(add_months(start, n) <= today for n in range(1, p["approved"]["moratorium_months"] + 1))
        return round(p["approved"]["original_emi"] * months, 2)

    def _change(self, s, name, payload):
        if name == "advance":
            days = int(payload.get("days", 3))
            if not 1 <= days <= 365:
                raise ValueError("Advance between 1 and 365 days.")
            s["as_of"] = (date.fromisoformat(s["as_of"]) + timedelta(days=days)).isoformat()
            self._log(s, "CLOCK", "", "Replay advanced by %s days." % days)
            return
        if name == "reading":
            maker, checker = signers(payload)
            reading = payload.get("reading", s["settings"]["reading"])
            convention = payload.get("day_count", s["settings"]["day_count"])
            if reading not in domain.ANCHORS or convention not in ("exclude_first", "include_first"):
                raise ValueError("Unknown reading or day-count convention.")
            s["settings"] = dict(reading=reading, day_count=convention, maker=maker, checker=checker,
                                 version=s["settings"]["version"] + 1)
            self._log(s, "RULE_APPROVED", "", "%s and %s signed %s / %s." % (maker, checker, reading, convention))
            return
        if name == "draft":
            self._draft(s, payload.get("borrower"), payload.get("option", "A"), payload.get("source_record"))
            return
        if name == "batch":
            self._batch(s, payload)
            return
        if name == "kill_switch":
            if not isinstance(payload.get("enabled"), bool):
                raise ValueError("Set the switch to true or false.")
            s["kill_switch"] = payload["enabled"]
            self._log(s, "SWITCH", "", "New bookings " + ("disabled." if s["kill_switch"] else "enabled."))
            return
        p = next((item for item in s["plans"] if item["id"] == payload.get("plan_id")), None)
        if not p:
            raise ValueError("Select a valid plan.")
        status = p["status"]
        if name == "book" and status in ("VERIFIED", "MISMATCH", "PENDING_EVENT"):
            return
        allowed = {"approve": "DRAFT", "notify": "APPROVED", "object": "NOTIFIED",
                   "book": "NOTIFIED", "reconcile": "PENDING_EVENT", "opt_out": "VERIFIED"}
        if allowed.get(name) != status:
            raise ValueError("This action is unavailable while the plan is " + status + ".")
        key = "%s:AP-DR-2026:%s:%s:%s" % (s["generation"], p["facility_id"], p["rule_version"], p["plan_version"])
        if name == "approve":
            if s["as_of"] > p["deadline"]:
                raise ValueError("The relief implementation window has closed.")
            if p["rule_version"] != s["settings"]["version"]:
                raise ValueError("Draft the plan under the newly approved reading first.")
            p["maker"], p["checker"] = signers(payload)
            p["approved_hash"] = digest(p["approved"])
            p["status"] = "APPROVED"
            self._log(s, "APPROVED", p["id"], "%s prepared the plan. %s approved it." % (p["maker"], p["checker"]))
        if name == "notify":
            p["objection_deadline"] = (date.fromisoformat(s["as_of"]) + timedelta(days=2)).isoformat()
            p["notice"] = ("Your payments pause for {moratorium_months} months. Your revised instalment is "
                           "₹{emi:,.2f} for {tenor} months, with ₹{extra_interest:,.2f} additional interest. "
                           "This may show as restructured on your credit report. Contact your branch to object "
                           "through {objection} or opt out after booking through {deadline}.").format(
                               **p["approved"], objection=p["objection_deadline"], deadline=p["deadline"])
            if p.get("relief_type") == "CONVERSION":
                p["notice"] = "Your crop loan will be converted to a term loan. " + p["notice"]
            p["status"] = "NOTIFIED"
            self._log(s, "NOTICE", p["id"], "Simulated notice delivered. Objection window ends " + p["objection_deadline"] + ".")
        if name == "object":
            if s["as_of"] > p["objection_deadline"]:
                raise ValueError("The pre-booking objection window has closed.")
            p["status"] = "OBJECTED"
            self._log(s, "OBJECTION", p["id"], "Borrower objected. Facility removed from the booking batch.")
        if name == "book":
            if s["paused"] or s["kill_switch"]:
                raise ValueError("Booking paused. Inspect the ledger or reset the demo.")
            if s["as_of"] <= p["objection_deadline"] or s["as_of"] > p["deadline"]:
                raise ValueError("Book after the objection window closes and by the implementation deadline.")
            fault = payload.get("fault") or ""
            if fault not in ("", "wrong_amount", "shifted_date", "missing_event", "timeout_after_commit"):
                raise ValueError("Choose a supported mock fault.")
            operation = "convert" if p.get("relief_type") == "CONVERSION" else "confirm"
            result = self._core(operation, key=key, approved=p["approved"], original=p["original"], fault=fault)
            p["txn_ref"] = result["transactionReference"]
            p["term_arrangement"] = result.get("term_arrangement")
            message = "Crop loan converted to mock term arrangement " + p["term_arrangement"] if p["term_arrangement"] else "Payment holiday confirmed on mock core"
            self._log(s, "BOOK", p["id"], message + " · " + p["txn_ref"])
            if "scheduleUpdated" not in result["events"]:
                p["status"] = "PENDING_EVENT"
                self._log(s, "PENDING_EVENT", p["id"], "Schedule event missing. Read-back available.")
            else:
                self._verify(s, p, result)
        if name == "reconcile":
            result = self._core("read", key=key)
            if not result or result["transactionReference"] != p["txn_ref"]:
                raise ValueError("Core schedule unavailable for this transaction. Retry read-back.")
            result["booked"] = self._core("schedule", key=key)
            if result["booked"] is None:
                raise ValueError("Core schedule unavailable for this transaction. Retry read-back.")
            self._verify(s, p, result)
        if name == "opt_out":
            if s["as_of"] > p["deadline"]:
                raise ValueError("The opt-out deadline has passed.")
            result = self._core("cancel", key=key + ":cancel", original_key=key)
            if not result["reversalIndicator"] or result["reverses"] != p["txn_ref"]:
                raise ValueError("Core reversal did not match the booking.")
            if self._core("schedule", key=key) != p["original"]:
                raise ValueError("Original schedule restoration has not been verified.")
            p.update(status="CANCELLED_VERIFIED", posted_provision=0, cancel_ref=result["transactionReference"])
            self._log(s, "CANCEL", p["id"], "Opt-out verified · %s reverses %s. Provision reversed." %
                      (p["cancel_ref"], p["txn_ref"]))

    def _view(self, s):
        previous = "0" * 64
        valid = True
        for i, entry in enumerate(s["ledger"], 1):
            hashed = {k: v for k, v in entry.items() if k != "hash"}
            valid = valid and entry["seq"] == i and entry["prev_hash"] == previous and entry["hash"] == digest(hashed)
            previous = entry["hash"]
        s["chain_valid"] = valid
        for p in s["plans"]:
            p["catch_up"] = self._catchup(p, s["as_of"])
        return s

    def snapshot(self):
        with closing(sqlite3.connect(str(self.path), timeout=30)) as db:
            s = json.loads(db.execute("SELECT data FROM workspace WHERE id=1").fetchone()[0])
        return self._view(s)

    def action(self, name, payload=None):
        with closing(sqlite3.connect(str(self.path), timeout=30)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            s = json.loads(db.execute("SELECT data FROM workspace WHERE id=1").fetchone()[0])
            if name == "reset":
                s = self._seed(s["generation"] + 1)
            else:
                self._change(s, name, payload or {})
            db.execute("UPDATE workspace SET data=? WHERE id=1", (canonical(s),))
        return self._view(s)
