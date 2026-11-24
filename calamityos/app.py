"""Loopback-only web server and application boundary for the offline demo."""
import gzip
import json
import math
import mimetypes
from datetime import date, timedelta
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit, parse_qs

from . import domain
from .booking import Workflow
from .intake import Evidence, extract

STATIC = Path(__file__).with_name("static")


class Application:
    def __init__(self, database):
        self.workflow = Workflow(str(database))
        self.evidence = Evidence(str(database))
        self.lock = RLock()
        self.scenario = lru_cache(maxsize=16)(domain.dashboard)

    def dashboard(self, preview=None):
        flow = self.workflow.snapshot()
        settings = flow["settings"]
        data = self.scenario(preview or settings["reading"], settings["day_count"], flow["as_of"])
        clock = dict(data["clock"])
        cutoff = (date.fromisoformat(flow["as_of"]) - timedelta(days=6)).isoformat()
        approvals = {e["plan_id"] for e in flow["ledger"] if e["kind"].upper() in ("APPROVE", "APPROVED") and e["day"] >= cutoff}
        signed = {p["borrower_id"] for p in flow["plans"] if p.get("checker") and p["status"].upper() != "DRAFT"}
        remaining = sum(b["bookable"] and b["id"] not in signed for b in data["borrowers"])
        finish = date.fromisoformat(flow["as_of"]) + timedelta(days=math.ceil(remaining*7/len(approvals))) if approvals else None
        clock.update(remaining_cases=remaining, achieved_per_day=round(len(approvals)/7, 2),
                     projected_finish=finish.isoformat() if finish else None,
                     needed_per_day=math.ceil(remaining/clock["days_left"]) if clock["days_left"] else None)
        return dict(data, workflow=flow, settings=settings, clock=clock)

    def action(self, body):
        name = body.get("action")
        args = dict(body.get("payload", {}), **{k:v for k,v in body.items() if k not in ("action","payload")})
        if name == "draft":
            args.pop("source_record", None)
            current = self.dashboard()
            borrower = next((b for b in current["borrowers"] if b["id"] == args.get("borrower_id")), None)
            if not borrower or not borrower["bookable"]:
                raise ValueError("Only eligible borrowers with supported facilities can enter the booking desk.")
            args.update(borrower=borrower, reading=current["reading"], day_count=current["day_count"],
                        deadline=current["clock"]["deadline"])
            evidence = self.evidence.current()
            if evidence["checker"]:
                args["source_record"] = {k:evidence[k] for k in ("maker","checker","fields")}
        if name == "reset":
            self.evidence.reset()
        self.workflow.action(name, args)
        return self.dashboard()


def serve(app, port, open_browser=False):
    class Handler(BaseHTTPRequestHandler):
        def send_data(self, status, data, media):
            self.send_response(status)
            self.send_header("Content-Type", media)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            if len(data)>4096 and "gzip" in self.headers.get("Accept-Encoding", ""):
                data = gzip.compress(data, compresslevel=2)
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def reply(self, status, value):
            self.send_data(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path.startswith("/api/"):
                try:
                    with app.lock:
                        if url.path == "/api/dashboard":
                            self.reply(200, app.dashboard(parse_qs(url.query).get("reading", [None])[0]))
                        elif url.path == "/api/evidence":
                            self.reply(200, app.evidence.current())
                        else:
                            self.reply(404, {"error":"Unknown resource"})
                except ValueError as exc:
                    self.reply(400, {"error":str(exc)})
                return
            name = url.path.lstrip("/") or "index.html"
            if Path(name).name != name or not (STATIC / name).is_file():
                self.reply(404, {"error":"Unknown resource"})
                return
            path = STATIC / name
            self.send_data(200, path.read_bytes(), mimetypes.guess_type(name)[0] or "application/octet-stream")

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                if origin and urlsplit(origin).netloc != self.server.server_name + ":" + str(self.server.server_port) and urlsplit(origin).netloc != self.headers.get("Host"):
                    raise ValueError("Open this action from the local demo.")
                length = int(self.headers.get("Content-Length", "0"))
                if self.headers.get_content_type() != "application/json" or not 0 < length <= 100000:
                    raise ValueError("Expected a JSON request.")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object.")
                with app.lock:
                    if self.path == "/api/action":
                        result = app.action(body)
                    elif self.path == "/api/evidence/preview":
                        value = body.get("body", "")
                        if not isinstance(value, str) or len(value)>16000:
                            raise ValueError("Brief exceeds the supported length.")
                        result = {"fields":extract(value)}
                    elif self.path == "/api/evidence/approve":
                        result = app.evidence.save(body["body"], body["maker"], body["checker"])
                    else:
                        self.reply(404, {"error":"Unknown action"})
                        return
                self.reply(200, result)
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                self.reply(400, {"error":str(exc)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"CalamityOS demo: {url}", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
