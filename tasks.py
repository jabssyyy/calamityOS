"""Run the offline CalamityOS demo, repeatable walkthrough or tests."""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # Also support the portable Windows Python runtime.
from calamityos.app import Application, serve


def walkthrough(database):
    app = Application(database)
    data = app.dashboard()
    assert data["metrics"]["total"] == 300
    assert len({r["eligible"] for r in data["readings"]}) > 1
    flow = data["workflow"]
    ready = [p["id"] for p in flow["plans"] if p["status"] == "NOTIFIED"]
    first = next(p for p in flow["plans"] if p["status"] == "VERIFIED")
    assert any(p["status"] == "OBJECTED" and not p["txn_ref"] for p in flow["plans"])
    def act(name, plan, **args):
        snapshot = app.action(dict(action=name, plan_id=plan, **args))["workflow"]
        return next(p for p in snapshot["plans"] if p["id"] == plan), snapshot
    pending, _ = act("book", ready[0], fault="missing_event")
    assert pending["status"] == "PENDING_EVENT"
    verified, _ = act("reconcile", ready[0])
    assert verified["status"] == "VERIFIED"
    cancelled, _ = act("opt_out", first["id"])
    assert cancelled["status"] == "CANCELLED_VERIFIED" and cancelled["posted_provision"] == 0
    bad, flow = act("book", ready[1], fault="shifted_date")
    assert bad["status"] == "MISMATCH" and bad["diff"] and flow["paused"] and flow["chain_valid"]
    return {"borrowers":data["metrics"]["total"],"readings":[r["eligible"] for r in data["readings"]],
            "recovered":verified["status"],"opt_out":cancelled["status"],"fault":bad["status"],
            "audit_tip":flow["ledger"][-1]["hash"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="ui", choices=["ui","demo","test"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--db", type=Path, default=ROOT/"local-state"/"relief.sqlite")
    args = parser.parse_args()
    if args.command == "ui":
        serve(Application(args.db), args.port, args.open)
    elif args.command == "demo":
        with tempfile.TemporaryDirectory() as temp:
            runs = [walkthrough(Path(temp)/f"run-{n}.sqlite") for n in range(3)]
        assert runs[0] == runs[1] == runs[2]
        print("Three identical clean runs.\n"+json.dumps(runs[0], indent=2))
    else:
        suite = unittest.defaultTestLoader.discover(str(ROOT/"calamityos"),top_level_dir=str(ROOT))
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
            raise SystemExit(1)


if __name__ == "__main__":
    main()
