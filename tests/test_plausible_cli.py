import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

loader = importlib.machinery.SourceFileLoader('plausible_cli', str(Path(__file__).resolve().parents[1] / 'setup-plausible/scripts/plausible'))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)


class CLI(unittest.TestCase):
    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_capabilities_offline(self):
        with patch.object(cli, 'config', side_effect=AssertionError), patch.object(cli, 'request', side_effect=AssertionError):
            code, out, err = self.invoke(['capabilities', '--json'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['version'], cli.VERSION)
        self.assertEqual(err, '')

    def test_origin_rejects_credentials_and_paths(self):
        for value in ['http://plausible.example.com', 'https://user:secret@plausible.example.com', 'https://plausible.example.com/path', 'https://plausible.example.com?x=y']:
            with self.assertRaises(cli.backend.SetupError):
                cli.origin(value)

    def test_login_checks_before_storing(self):
        with patch.object(cli.sys.stdin, 'isatty', return_value=True), patch.object(cli.getpass, 'getpass', return_value='private-key'), patch.object(cli, 'query', side_effect=cli.backend.SetupError('Plausible returned HTTP 401.')), patch.object(cli.backend, 'store_generated_secret') as store:
            code, out, err = self.invoke(['login', '--url', 'https://plausible.example.com', '--site', 'example.com'])
        self.assertEqual(code, 1)
        store.assert_not_called()
        self.assertNotIn('private-key', out + err)

    def test_login_saves_only_public_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            with patch.object(cli, 'config_path', return_value=path), patch.object(cli.sys.stdin, 'isatty', return_value=True), patch.object(cli.getpass, 'getpass', return_value='private-key'), patch.object(cli, 'query', return_value={'results': []}), patch.object(cli.backend, 'store_generated_secret') as store:
                code, out, err = self.invoke(['login', '--url', 'https://plausible.example.com', '--site', 'example.com'])
            self.assertEqual(code, 0)
            self.assertNotIn('private-key', path.read_text() + out + err)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            store.assert_called_once_with('plausible-stats:plausible.example.com', 'stats-api', 'private-key')

    def test_query_and_site_override(self):
        saved = {'url': 'https://plausible.example.com', 'site': 'example.com'}
        with patch.object(cli, 'config', return_value=saved), patch.object(cli.backend, 'keychain_secret', return_value='secret'), patch.object(cli.sys, 'stdin', io.StringIO('{"site_id":"other.com","date_range":"30d","metrics":["events"],"pagination":{"limit":3,"offset":6}}')), patch.object(cli, 'query', return_value={'results': []}) as query:
            code, _, _ = self.invoke(['query', '--file', '-', '--site', 'chosen.com'])
        self.assertEqual(code, 0)
        self.assertEqual(query.call_args.args[2]['site_id'], 'chosen.com')
        self.assertEqual(query.call_args.args[2]['pagination']['offset'], 6)

    def test_missing_key_fails_without_creating_one(self):
        with patch.object(cli, 'config', return_value={'url': 'https://plausible.example.com', 'site': 'example.com'}), patch.object(cli.backend, 'keychain_secret', side_effect=cli.backend.MissingKeychainItem()), patch.object(cli.backend, 'ensure_stats_key', side_effect=AssertionError):
            code, _, err = self.invoke(['report'])
        self.assertEqual(code, 1)
        self.assertIn('Run plausible login', err)

    def test_timeseries_default_keeps_month(self):
        self.assertEqual(cli.parser().parse_args(['timeseries', '--period', '30d']).limit, 10000)

    def test_invalid_query_response(self):
        with patch.object(cli, 'request', return_value=('', 200, b'[]')):
            with self.assertRaises(cli.backend.SetupError):
                cli.query('https://plausible.example.com', 'secret', {})

    def test_http_requests_and_redirect_refusal(self):
        captured = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                captured.append((self.path, self.headers.get('Authorization'), body))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"results": [], "meta": {}}')
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', '/should-not-be-called')
                self.end_headers()
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            result = cli.query(base, 'test-secret', {'site_id': 'example.com', 'metrics': ['visitors']})
            self.assertEqual(result['results'], [])
            self.assertEqual(captured[0][1], 'Bearer test-secret')
            with self.assertRaisesRegex(cli.backend.SetupError, 'HTTP 302'):
                cli.request(base + '/redirect', headers={'Authorization': 'Bearer test-secret'})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
