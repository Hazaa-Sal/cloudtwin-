import os
import unittest
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from app.server import Handler, response


class HealthTests(unittest.TestCase):
    def test_liveness_does_not_depend_on_database(self):
        def must_not_call():
            raise AssertionError("liveness must not query database")
        self.assertEqual(response("/healthz", must_not_call)[0], 200)

    def test_readiness_fails_closed(self):
        status, body = response("/readyz", lambda: False)
        self.assertEqual(status, 503)
        self.assertEqual(body["database"], "unavailable")

    def test_readiness_and_site(self):
        with patch.dict(os.environ, CLOUDTWIN_SITE="dr"):
            status, body = response("/readyz", lambda: True)
        self.assertEqual(status, 200)
        self.assertEqual(body["site"], "dr")

    def test_unknown_path(self):
        self.assertEqual(response("/missing")[0], 404)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_live_http_response(self):
        with urllib.request.urlopen(self.url + '/healthz', timeout=3) as result:
            self.assertEqual(result.status, 200)
            self.assertEqual(result.headers['Content-Type'], 'application/json')
            self.assertEqual(json.load(result)['status'], 'alive')

    def test_http_unready_preserves_503(self):
        with patch('app.server.response', return_value=(503, {'status': 'not_ready'})):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url + '/readyz', timeout=3)
            self.assertEqual(error.exception.code, 503)
            self.assertEqual(json.load(error.exception)['status'], 'not_ready')


if __name__ == "__main__":
    unittest.main()
