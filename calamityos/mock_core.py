"""Offline lending-core simulator. Child process protocol: one JSON request per invocation."""
import calendar
import hashlib
import json
import sqlite3
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def add_months(day, months):
    index = day.year * 12 + day.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def money(amount):
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def instalment(principal, monthly_rate, months):
    if not monthly_rate:
        return principal / months
    return principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def simulate(loan, tenor, holiday, effective):
    principal = Decimal(str(loan["principal"]))
    rate = Decimal(str(loan["rate"])) / 1200
    balance = principal * (1 + rate * holiday)
    bullet = loan.get("repayment") == "BULLET"
    old_emi = None if bullet else instalment(principal, rate, loan["months"])
    original_total = principal * (1 + rate * loan["months"]) if bullet else old_emi * loan["months"]
    new_emi = instalment(balance, rate, tenor)
    start = date.fromisoformat(effective)
    if bullet and holiday == 0:
        maturity = add_months(start, loan["months"]).isoformat()
        return {"emi": None, "extra_interest": 0, "original_emi": None, "moratorium_months": 0,
                "tenor": loan["months"], "effective": effective, "first_due": maturity,
                "rows": [{"due": maturity, "amount": money(original_total)}],
                "repayment": "BULLET", "original_maturity_due": money(original_total)}
    rows = []
    for month in range(1, tenor + 1):
        amount = money(new_emi)
        if month == tenor:
            amount = money(new_emi * tenor - Decimal(str(amount)) * (tenor - 1))
        rows.append({"due": add_months(start, holiday + month).isoformat(), "amount": amount})
    return {"emi": money(new_emi), "extra_interest": money(new_emi * tenor - original_total),
            "repayment": "TERM_CONVERSION" if bullet else "EMI", "original_maturity_due": money(original_total) if bullet else None,
            "original_emi": None if bullet else money(old_emi), "moratorium_months": holiday, "tenor": tenor,
            "effective": effective, "first_due": rows[0]["due"], "rows": rows}


def run(path, method, args):
    with sqlite3.connect(path, timeout=15) as db:
        db.execute("CREATE TABLE IF NOT EXISTS txn (key TEXT PRIMARY KEY, response TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS arrangement (booking_key TEXT PRIMARY KEY, original TEXT, current TEXT)")
        if method == "simulate":
            return simulate(**args)
        key = args["key"]
        if method == "schedule":
            row = db.execute("SELECT current FROM arrangement WHERE booking_key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else None
        old = db.execute("SELECT response FROM txn WHERE key=?", (key,)).fetchone()
        if old or method == "read":
            return json.loads(old[0]) if old else None
        if method not in ("confirm", "convert", "cancel"):
            raise ValueError("Unknown mock operation")
        # Reset generations isolate database writes while replaying the same visible references.
        replay_key = key.partition(":")[2]
        ref = "MOCK-" + hashlib.sha256(replay_key.encode()).hexdigest()[:10].upper()
        if method == "cancel":
            original = db.execute("SELECT response FROM txn WHERE key=?", (args["original_key"],)).fetchone()
            if not original:
                raise ValueError("Original booking missing from mock core")
            restored = db.execute("UPDATE arrangement SET current=original WHERE booking_key=?", (args["original_key"],))
            if restored.rowcount != 1:
                raise ValueError("Original schedule missing from mock core")
            original_txn = json.loads(original[0])
            conversion = original_txn.get("operation") == "CONVERT"
            result = {"transactionReference": ref, "reversalIndicator": True,
                      "reverses": original_txn["transactionReference"],
                      "closed_term_arrangement": original_txn.get("term_arrangement"),
                      "events": ["mockConversionCancelled" if conversion else "paymentHolidayUpdated", "scheduleUpdated"]}
        else:
            booked = args["approved"]
            fault = args.get("fault", "")
            if fault == "shifted_date":
                booked["rows"][0]["due"] = (date.fromisoformat(booked["first_due"]) - timedelta(days=1)).isoformat()
                booked["first_due"] = booked["rows"][0]["due"]
            elif fault == "wrong_amount":
                booked["rows"][0]["amount"] += 100
            elif fault and fault not in ("missing_event", "timeout_after_commit"):
                raise ValueError("Unknown demonstration fault")
            conversion = method == "convert"
            if conversion != (args["original"].get("repayment") == "BULLET"):
                raise ValueError("Mock operation does not match original repayment type")
            result = {"transactionReference": ref, "reversalIndicator": False, "booked": booked,
                      "operation": "CONVERT" if conversion else "RESCHEDULE",
                      "term_arrangement": ref.replace("MOCK-", "TERM-") if conversion else None,
                      "events": [] if fault == "missing_event" else [
                          "mockCropLoanConverted" if conversion else "paymentHolidayUpdated", "scheduleUpdated"]}
            db.execute("INSERT INTO arrangement VALUES (?,?,?)",
                       (key, json.dumps(args["original"]), json.dumps(booked)))
        db.execute("INSERT INTO txn VALUES (?,?)", (key, json.dumps(result)))
        return result


if __name__ == "__main__":
    request = json.loads(sys.stdin.buffer.read())
    response = run(sys.argv[1], request["method"], request["args"])
    if request["method"] in ("confirm", "convert") and request["args"].get("fault") == "timeout_after_commit":
        sys.exit(75)
    sys.stdout.buffer.write(json.dumps(response).encode())
