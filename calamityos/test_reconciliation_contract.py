"""Black-box faults authored against the public repayment schedule contract."""
import copy
import unittest
from .booking import check_schedule
from .intake import EXAMPLE, extract


class ReconciliationContracts(unittest.TestCase):
    def setUp(self):
        self.approved = dict(emi=1000, extra_interest=210, original_emi=900,
            moratorium_months=12, tenor=2, effective="2026-11-20", first_due="2027-12-20",
            rows=[dict(due="2027-12-20", amount=1000),dict(due="2028-01-20",amount=1000)])
        self.limits = dict(moratorium_months=12, tenor=36, deadline="2027-02-14", extra_interest=210)

    def test_unchanged_schedule(self):
        self.assertFalse(check_schedule(self.approved, copy.deepcopy(self.approved), self.limits))

    def test_each_booking_fault_leaves_a_difference(self):
        for field, value in [
            ("emi", 1001), ("extra_interest", 211), ("tenor", 37), ("moratorium_months", 13),
            ("first_due", "2027-11-01"), ("effective","2027-03-01"),
            ("rows", []), ("rows", self.approved["rows"] * 2),
            ("rows", list(reversed(self.approved["rows"]))),
            ("rows", [*self.approved["rows"][:1], dict(due="2028-01-20",amount=999.99)]),
        ]:
            with self.subTest(field=field, value=value):
                booked = dict(copy.deepcopy(self.approved), **{field:value})
                self.assertTrue(check_schedule(self.approved, booked, self.limits))

    def test_unresolved_source_term(self):
        self.assertEqual([f["status"] for f in extract(EXAMPLE)], ["Matched"]*4)
        for body in (EXAMPLE.replace("12 months","15 months"), EXAMPLE + " Moratorium is 12 months."):
            self.assertEqual(extract(body)[1]["status"], "Review")
