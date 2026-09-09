import base64
import importlib.machinery
import importlib.util
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.parse


SCRIPT = str(
    Path(__file__).resolve().parents[1]
    / "setup-plausible/scripts/plausible-setup"
)
loader = importlib.machinery.SourceFileLoader("plausible_setup", SCRIPT)
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class Handler(BaseHTTPRequestHandler):
    sites = {"example.com"}
    goals = []
    last_query = None

    def log_message(self, *_args):
        pass

    def response(self, body=b"", status=200, content_type="text/html", location=None, cookie=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if location:
            self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, value, status=200):
        self.response(json.dumps(value), status=status, content_type="application/json")

    def authenticated(self):
        return "sid=ok" in (self.headers.get("Cookie") or "")

    def plugin_authenticated(self):
        expected = base64.b64encode(b"example.com:plugin-secret").decode()
        return self.headers.get("Authorization") == f"Basic {expected}"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/login":
            self.response('<form action="/login" method="post"><input name="_csrf_token" value="login-token"></form>', cookie="sid=pre; Path=/")
        elif parsed.path == "/sites":
            if not self.authenticated():
                self.response(status=302, location="/login")
            else:
                self.response(" ".join(f"<div>{site}</div>" for site in self.sites))
        elif parsed.path == "/settings/api-keys/new":
            self.response('<form action="/settings/api-keys" method="post"><input name="_csrf_token" value="api-token"><input name="api_key[name]"><input name="api_key[type]" value="stats_api"><input name="api_key[key]" value="stats-secret"></form>')
        elif parsed.path == "/settings/api-keys":
            self.response("API key created successfully")
        elif parsed.path == "/api/plugins/v1/goals":
            if not self.plugin_authenticated():
                self.json_response({"detail": "Unauthorized"}, 401)
            else:
                self.json_response({"goals": self.goals, "meta": {"pagination": {}}})
        elif parsed.path == "/api/health":
            self.response("ok", content_type="text/plain")
        elif parsed.path == "/js/script.js":
            self.response("window.plausible=window.plausible||function(){};", content_type="text/javascript")
        else:
            self.response("missing", status=404)

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        if self.path == "/login":
            fields = urllib.parse.parse_qs(body.decode())
            if fields.get("email") == ["me@example.com"] and fields.get("password") == ["secret"]:
                self.response(status=302, location="/sites", cookie="sid=ok; Path=/")
            else:
                self.response("Invalid email or password")
        elif self.path == "/settings/api-keys":
            fields = urllib.parse.parse_qs(body.decode())
            if fields.get("api_key[key]") == ["stats-secret"]:
                self.response(status=302, location="/settings/api-keys")
            else:
                self.response("invalid")
        elif self.path == "/api/v2/query":
            if self.headers.get("Authorization") != "Bearer stats-secret":
                self.json_response({"detail": "Unauthorized"}, 401)
                return
            query = json.loads(body)
            Handler.last_query = query
            dimensions = query.get("dimensions", [])
            if dimensions == ["event:page"]:
                metrics, values = [12, 20], ["/"]
            elif dimensions == ["visit:source"]:
                metrics, values = [9], ["Google"]
            elif dimensions == ["event:goal"]:
                metrics, values = [3, 25.0], ["Signup"]
            elif dimensions == ["visit:country_name"]:
                metrics, values = [7, 46.7], ["Denmark"]
            else:
                metrics, values = [15, 18, 30, 40.0, 75], []
            self.json_response({"results": [{"dimensions": values, "metrics": metrics}], "meta": {}, "query": query})
        else:
            self.response("missing", status=404)

    def do_PUT(self):
        if not self.plugin_authenticated():
            self.json_response({"detail": "Unauthorized"}, 401)
            return
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size))
        goal_data = payload["goal"]
        display = goal_data.get("event_name") or f"Visit {goal_data['path']}"
        item = {"goal_type": payload["goal_type"], "goal": {"id": 7, "display_name": display, **goal_data}}
        self.goals[:] = [item]
        self.json_response({"goals": [item], "meta": {"pagination": {}}}, 201)

    def do_DELETE(self):
        if not self.plugin_authenticated():
            self.json_response({"detail": "Unauthorized"}, 401)
            return
        self.goals.clear()
        self.response(status=204)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Handler.goals = []
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_configuration_uses_customer_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            previous = os.environ.get(module.CONFIG_PATH_ENV)
            os.environ[module.CONFIG_PATH_ENV] = str(path)
            try:
                module.save_configured_url("https://analytics.example.com/path")
                self.assertEqual(module.configured_base_url(None), "https://analytics.example.com")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            finally:
                if previous is None:
                    os.environ.pop(module.CONFIG_PATH_ENV, None)
                else:
                    os.environ[module.CONFIG_PATH_ENV] = previous

    def test_login_and_stats_key_creation(self):
        session = module.PlausibleSession(self.base)
        session.login("me@example.com", "secret")
        self.assertEqual(session.create_stats_key("CLI"), "stats-secret")

    def test_report_queries_and_formatting(self):
        report = module.build_report(self.base, "stats-secret", "example.com", "7d", 10)
        output = module.format_report(report)
        self.assertIn("Visitors: 15", output)
        self.assertIn("Average visit: 1m 15s", output)
        self.assertIn("Google: visitors 9", output)
        self.assertIn("Signup: conversions 3, conversion rate 25%", output)

    def test_previous_period_comparison_and_exports(self):
        self.assertEqual(
            module.previous_period_range("7d", module.date(2026, 8, 6)),
            ["2026-07-24", "2026-07-30"],
        )
        report = module.build_report(
            self.base,
            "stats-secret",
            "example.com",
            "7d",
            10,
            compare="previous",
        )
        self.assertIn("Compared with", module.format_report(report))
        self.assertIn("| Previous | Change |", module.format_report_markdown(report))
        self.assertIn("previous,,visitors,15", module.format_report_csv(report))

    def test_breakdown_filters_and_formats(self):
        breakdown = module.build_breakdown(
            self.base,
            "stats-secret",
            "example.com",
            "30d",
            "country",
            10,
            ["source=Google"],
        )
        self.assertEqual(breakdown["dimension"], "visit:country_name")
        self.assertEqual(Handler.last_query["filters"], [["is", "visit:source", ["Google"]]])
        self.assertIn("Denmark", module.format_breakdown(breakdown, "text"))
        self.assertIn("Denmark,7,46.7", module.format_breakdown(breakdown, "csv"))
        self.assertIn("| Denmark | 7 | 46.7 |", module.format_breakdown(breakdown, "markdown"))

    def test_doctor_checks_instance_project_and_apis(self):
        original_login = module.logged_in_session
        original_keychain = module.keychain_secret
        with tempfile.TemporaryDirectory(suffix=".dev") as temp:
            root = Path(temp)
            layout = root / "src/layouts/Base.astro"
            layout.parent.mkdir(parents=True)
            layout.write_text(
                '<html>\n<head>\n<script is:inline defer data-domain="example.com" '
                f'src="{self.base}/js/script.js"></script>\n</head>\n</html>\n'
            )
            session = module.PlausibleSession(self.base)
            session.login("me@example.com", "secret")
            module.logged_in_session = lambda *_args: session
            module.keychain_secret = lambda service: "stats-secret" if "stats" in service else "plugin-secret"
            try:
                report = module.build_doctor_report(
                    self.base,
                    "plausible.example.com",
                    "login-service",
                    "stats-service",
                    str(root),
                    "example.com",
                    None,
                    "plugin-service",
                )
            finally:
                module.logged_in_session = original_login
                module.keychain_secret = original_keychain
        self.assertTrue(report["ok"], report)
        self.assertEqual({check["status"] for check in report["checks"]}, {"pass"})
        self.assertIn("Ready", module.format_doctor(report))

    def test_goal_crud(self):
        self.assertEqual(module.list_goals(self.base, "example.com", "plugin-secret"), [])
        created = module.plugin_api_request(
            self.base,
            "example.com",
            "plugin-secret",
            "/api/plugins/v1/goals",
            method="PUT",
            body={"goal_type": "Goal.CustomEvent", "goal": {"event_name": "Signup"}},
        )
        self.assertEqual(created["goals"][0]["goal"]["display_name"], "Signup")
        self.assertEqual(len(module.list_goals(self.base, "example.com", "plugin-secret")), 1)
        module.plugin_api_request(self.base, "example.com", "plugin-secret", "/api/plugins/v1/goals/7", method="DELETE")
        self.assertEqual(module.list_goals(self.base, "example.com", "plugin-secret"), [])

    def test_existing_tracker_is_idempotent(self):
        with tempfile.TemporaryDirectory(suffix=".dev") as temp:
            root = Path(temp)
            layout = root / "src/layouts/Base.astro"
            layout.parent.mkdir(parents=True)
            layout.write_text("<html>\n  <head>\n    <title>x</title>\n  </head>\n</html>\n")
            before, after = module.plan_integration(layout, "example.com", "https://analytics.example.com")
            self.assertIn('<script is:inline defer data-domain="example.com"', after)
            layout.write_text(after)
            self.assertEqual(module.plan_integration(layout, "example.com", "https://analytics.example.com"), (after, after))


if __name__ == "__main__":
    unittest.main()
