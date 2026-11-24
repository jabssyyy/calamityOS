"""Extract reviewable source spans from the typed committee brief, offline."""
from contextlib import closing
import re
import sqlite3

EXAMPLE = """Andhra Pradesh drought relief - illustrative committee brief
Committee reference date: 2026-10-01.
The moratorium is 12 months. The moderate tier permits 36 months for repayment.
The severe tier permits 60 months for repayment.
Source: scenario compiled from the project's secondary summary of the 6 October meeting."""

FIELDS = {
    "Committee reference date": (r"reference date\s*[:=]?\s*(\d{4}-\d{2}-\d{2})", "2026-10-01"),
    "Moratorium": (r"moratorium\s*(?:of|is|:)?\s*(\d+)\s*months?", "12"),
    "Moderate tier cap": (r"moderate[^.\n\d]{0,50}(\d+)\s*months?", "36"),
    "Severe tier cap": (r"severe[^.\n\d]{0,50}(\d+)\s*months?", "60"),
}


def extract(body):
    fields = []
    for label, (pattern, expected) in FIELDS.items():
        hits = list(re.finditer(pattern, body, re.I))
        hit = hits[0] if len(hits) == 1 else None
        value = hit.group(1) if hit else None
        fields.append(dict(label=label, value=value, expected=expected,
                           span=list(hit.span()) if hit else None,
                           quote=hit.group() if hit else None,
                           status="Matched" if value == expected else "Review"))
    return fields


class Evidence:
    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS evidence (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT, maker TEXT, checker TEXT)")

    def current(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT body,maker,checker FROM evidence WHERE id=1").fetchone()
        body, maker, checker = row or (EXAMPLE, "", "")
        return dict(body=body, maker=maker, checker=checker, fields=extract(body))

    def save(self, body, maker, checker):
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= 16000:
            raise ValueError("Enter a committee brief of 1 to 16,000 characters.")
        if not maker.strip() or not checker.strip() or maker.strip().casefold() == checker.strip().casefold():
            raise ValueError("The source reviewer must differ from the maker.")
        if any(f["status"] != "Matched" for f in extract(body)):
            raise ValueError("Resolve missing, conflicting or unsupported terms before attaching this brief to the AP rule pack.")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO evidence VALUES (1,?,?,?)", (body, maker.strip(), checker.strip()))
        return self.current()

    def reset(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM evidence")

