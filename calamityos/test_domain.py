import unittest
from datetime import date

from calamityos import domain


class ReliefRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = domain.dashboard()

    def test_sizing_reference(self):
        options = domain.plan_options(500000, 10, 36, "Severe")
        self.assertEqual((options[0]["emi"], options[0]["extra_interest"]), (17746.95, 58080.94))
        self.assertEqual((options[1]["months"], options[1]["emi"], options[1]["extra_interest"]),
                         (41, 15891.82, 70755.44))

    def test_tier_and_zero_rate(self):
        options = domain.plan_options(36000, 0, 36, "Moderate")
        self.assertEqual(options[1]["months"], 36)
        self.assertEqual(options[1]["emi"], 1000)
        self.assertEqual(options[1]["extra_interest"], 0)

    def test_bullet_converts_into_term_instead_of_emi_holiday(self):
        candidate = self.book["borrowers"][1]
        self.assertTrue(candidate["bookable"])
        self.assertEqual(candidate["relief_type"], "CONVERSION")
        self.assertEqual(candidate["facilities"][0]["months"], 12)
        self.assertIsNone(candidate["plans"][0]["original_emi"])
        severe = domain.conversion_options(500000, 10, 12, "Severe")
        self.assertEqual(severe[0]["original_maturity_due"], 550000)
        self.assertEqual([p["months"] for p in severe], [36, 60])
        self.assertEqual(severe[0]["emi"], 17746.95)
        self.assertGreater(severe[1]["extra_interest"], severe[0]["extra_interest"])
        self.assertEqual(len(domain.conversion_options(500000, 10, 12, "Moderate")), 1)

    def test_every_facility_on_test_date(self):
        row = self.book["borrowers"][1]
        self.assertEqual((row["id"], row["status"]), ("AP-0002", "Eligible"))
        status, code, reason = domain._decision(row, "declaration")
        self.assertEqual((status, code), ("Ineligible", "DPD_GT_30"))
        self.assertIn(row["facilities"][1]["id"], reason)
        self.assertIn("1 above", reason)

    def test_unknown_snapshot_requires_review(self):
        status, code, _ = domain._decision(self.book["borrowers"][10], "occurrence")
        self.assertEqual((status, code), ("Review", "SNAPSHOT_MISSING"))

    def test_comparisons_match_individual_outcomes(self):
        metrics = self.book["metrics"]
        self.assertEqual(metrics["total"], 300)
        self.assertEqual(sum(metrics[key] for key in ("eligible", "ineligible", "review")), 300)
        counts = []
        for reading in self.book["readings"]:
            expected = domain.dashboard(reading["id"])
            self.assertEqual(reading["eligible"], expected["metrics"]["eligible"])
            self.assertEqual(reading["provision"], expected["metrics"]["provision"])
            counts.append(reading["eligible"])
            changed = {r["id"] for r, s in zip(self.book["borrowers"], expected["borrowers"])
                       if r["status"] != s["status"]}
            self.assertSetEqual(changed, {b["id"] for b in reading["flips"]})
        self.assertEqual(len(set(counts)), 3)

    def test_route_deadlines_and_saturday(self):
        clock = self.book["clock"]
        self.assertEqual(clock["deadline"], "2027-02-14")
        self.assertEqual(clock["last_safe_business_day"], "2027-02-12")
        self.assertEqual(clock["milestones"][1]["date"], "2026-11-16")
        self.assertEqual(domain.dashboard(day_count="include_first")["clock"]["deadline"], "2027-02-13")
        self.assertEqual(domain.last_safe_business_day(date(2027,2,13)), date(2027,2,12))

    def test_provision_and_repayment(self):
        self.assertEqual(domain.additional_provision(1000000), 50000)
        self.assertEqual(domain.additional_provision(1000000, 980000), 20000)
        self.assertFalse(domain.write_back_due(1000000, 199999))
        self.assertTrue(domain.write_back_due(1000000, 200000))
        self.assertFalse(domain.write_back_due(1000000, 200000, slipped=True))

    def test_policy_impact(self):
        repeat, base = self.book["policy_readings"]
        default, alternate = repeat["options"]
        self.assertGreater(repeat["cohort"], 0)
        self.assertEqual(default["cash_basis_count"], repeat["cohort"])
        self.assertEqual(alternate["cash_basis_count"], 0)
        self.assertEqual(default["provision"], 2 * alternate["provision"])
        self.assertEqual(alternate["affected_count"], repeat["cohort"])
        affected = {b["id"] for b in self.book["borrowers"] if b["bookable"] and len(b["facilities"]) > 1}
        self.assertSetEqual(set(base["options"][1]["affected_ids"]), affected)
        self.assertLess(base["options"][1]["delta"], 0)

    def test_writeback_tracker(self):
        records = [b["prudential"] for b in self.book["borrowers"]]
        ready = [b for b in records if b["write_back_due"]]
        self.assertTrue(ready)
        for item in ready:
            self.assertGreaterEqual(item["repaid"], item["repayment_target"])
            self.assertFalse(item["slipped"] or item["restructured_again"])


if __name__ == "__main__":
    unittest.main()
