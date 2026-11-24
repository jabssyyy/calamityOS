import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from calamityos.booking import Workflow
from calamityos.domain import dashboard


class BookingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name) / "demo.db"
        self.w = Workflow(self.store)

    def action(self, name, plan_id="PL-0002", **fields):
        state = self.w.action(name, dict(fields, plan_id=plan_id))
        return next(p for p in state["plans"] if p["id"] == plan_id)

    def test_notice_objection_and_distinct_officers(self):
        with self.assertRaises(ValueError):
            self.action("approve", "PL-0006", maker=" Maya ", checker="maya")
        self.action("approve", "PL-0006", maker="Maya", checker="Dev")
        plan = self.action("notify", "PL-0006")
        self.assertIn(format(plan["approved"]["extra_interest"], ",.2f"), plan["notice"])
        self.assertIn(plan["objection_deadline"], plan["notice"])
        with self.assertRaises(ValueError):
            self.action("book", "PL-0006")
        self.action("advance", days=2)
        self.assertEqual(self.action("object", "PL-0006")["status"], "OBJECTED")
        with self.assertRaises(ValueError):
            self.action("book", "PL-0006")

    def test_mismatch_pauses_and_reports_diff(self):
        plan = self.action("book", fault="shifted_date")
        self.assertEqual(plan["status"], "MISMATCH")
        self.assertTrue(plan["diff"])
        self.assertTrue(self.w.snapshot()["paused"])
        with self.assertRaises(ValueError):
            self.action("book", "PL-0003")
        self.assertTrue(self.w.snapshot()["chain_valid"])

    def test_missing_event_readback_and_cancel(self):
        self.assertEqual(self.action("book", fault="missing_event")["status"], "PENDING_EVENT")
        plan = self.action("reconcile")
        self.assertEqual(plan["status"], "VERIFIED")
        self.assertGreater(plan["posted_provision"], 0)
        original_ref = plan["txn_ref"]
        self.action("advance", days=82)
        self.assertGreater(self.w.snapshot()["plans"][1]["catch_up"], 0)
        plan = self.action("opt_out")
        self.assertNotEqual(original_ref, plan["cancel_ref"])
        self.assertEqual(plan["posted_provision"], 0)
        self.assertEqual(plan["status"], "CANCELLED_VERIFIED")

    def test_duplicate_request_and_timeout_recovery(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            calls = [pool.submit(self.action, "book", fault="timeout_after_commit") for _ in range(2)]
            refs = [call.result()["txn_ref"] for call in calls]
        self.assertEqual(refs[0], refs[1])
        state = Workflow(self.store).snapshot()
        self.assertEqual(sum(e["kind"] == "BOOK" and e["plan_id"] == "PL-0002" for e in state["ledger"]), 1)

    def test_reading_version_and_deadline(self):
        self.w.action("reading", dict(maker="Maker", checker="Checker", reading="reference", day_count="include_first"))
        with self.assertRaises(ValueError):
            self.action("approve", "PL-0006", maker="M", checker="C")
        old = self.w.snapshot()["plans"][5]
        row = next(b for b in dashboard("reference")["borrowers"] if b["id"] == old["borrower_id"])
        if row["bookable"]:
            p = self.action("draft", "PL-0006", borrower=row)
            self.assertEqual(p["rule_version"], 2)
            self.assertEqual(p["deadline"], "2027-02-13")
        self.action("advance", days=87)
        with self.assertRaises(ValueError):
            self.action("opt_out", "PL-0001")

    def test_reset_and_tamper_check(self):
        self.action("book", fault="wrong_amount")
        self.assertFalse(self.w.action("reset")["paused"])
        self.assertEqual(self.action("book")["status"], "VERIFIED")
        with closing(sqlite3.connect(str(self.store))) as db, db:
            data = json.loads(db.execute("SELECT data FROM workspace").fetchone()[0])
            data["ledger"][1]["message"] = "altered"
            db.execute("UPDATE workspace SET data=?", (json.dumps(data),))
        self.assertFalse(self.w.snapshot()["chain_valid"])

    def test_batch_stops_at_first_difference_and_replays_receipt(self):
        request = dict(operation="book",plan_ids=["PL-0002","PL-0003"],
                       fault_plan_id="PL-0002",fault="shifted_date")
        state = self.w.action("batch",request)
        self.assertEqual(state["batch_result"]["remaining"], ["PL-0003"])
        self.assertEqual(state["plans"][2]["status"], "NOTIFIED")
        self.assertFalse(state["plans"][2]["txn_ref"])
        self.assertEqual(self.w.action("batch",request)["ledger"],state["ledger"])

    def test_crop_conversion_and_bullet_restoration(self):
        plan = next(p for p in self.w.snapshot()["plans"] if p.get("relief_type")=="CONVERSION")
        pid=plan["id"]
        self.assertEqual(len(plan["original"]["rows"]),1)
        self.action("approve",pid,maker="M",checker="C")
        self.assertIn("term loan",self.action("notify",pid)["notice"])
        self.action("advance",days=3)
        booked=self.action("book",pid)
        self.assertTrue(booked["term_arrangement"])
        self.assertEqual(booked["status"],"VERIFIED")
        self.assertEqual(self.action("opt_out",pid)["status"],"CANCELLED_VERIFIED")


if __name__ == "__main__":
    unittest.main()
