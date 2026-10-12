"""Small local-lab API: liveness is independent from database readiness."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def database_ready():
    import psycopg
    try:
        with psycopg.connect(
            host=os.getenv("PGHOST", "postgres"),
            dbname=os.getenv("PGDATABASE", "cloudtwin"),
            user=os.getenv("PGUSER", "cloudtwin"),
            password=os.environ["PGPASSWORD"], connect_timeout=2,
            options="-c statement_timeout=2000",
        ) as connection:
            return connection.execute("SELECT 1").fetchone() == (1,)
    except (psycopg.Error, KeyError):
        return False


def response(path, check_database=database_ready):
    site = os.getenv("CLOUDTWIN_SITE", "local")
    if path == "/healthz":
        return 200, {"status": "alive", "site": site}
    if path == "/readyz":
        ready = check_database()
        return (200 if ready else 503), {
            "status": "ready" if ready else "not_ready", "site": site,
            "database": "reachable" if ready else "unavailable",
        }
    if path == "/":
        return 200, {"service": "cloudtwin", "site": site, "stage": "day-1"}
    return 404, {"error": "not_found"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, payload = response(self.path)
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
