"""
Minimal stand-in for the user-lookup GraphQL service, so the integration tests never call a real SLAC service.
Answers every `users(filter: UserInput!)` query (main.py's lookupUser / lookupUserGids) from canned, synthetic
data for the seeded test users (scripts/dev/00-test-users.mongodb), matching on filter.username / filter.eppns.
The query text is not parsed: each user carries the union of the fields main.py asks for.

Usage: python tests/stubs/user_lookup_stub.py [port]   (default 8099; serves POST /graphql)
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

# Synthetic values only. Kept consistent with SNAPSHOT in tests/integration/test_posix_sync.py.
USERS = [
    {"username": "regular_user", "fullname": "Regular User", "uidnumber": 99001, "eppns": ["regular_user@example.com"],
     "preferredemail": "regular_user@example.com", "shell": "/bin/bash", "gidNumber": 1001, "secondaryGidNumbers": [2113, 3049]},
    {"username": "admin", "fullname": "Admin User", "uidnumber": 99002, "eppns": ["admin@example.com"],
     "preferredemail": "admin@example.com", "shell": "/bin/bash", "gidNumber": 1002, "secondaryGidNumbers": []},
]


def lookup(flt: dict) -> list:
    if flt.get("username"):
        return [u for u in USERS if u["username"] == flt["username"]]
    if flt.get("eppns"):
        eppns = flt["eppns"] if isinstance(flt["eppns"], list) else [flt["eppns"]]
        return [u for u in USERS if set(eppns) & set(u["eppns"])]
    return []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            resp = {"data": {"users": lookup((body.get("variables") or {}).get("filter") or {})}}
        except Exception as e:
            resp = {"errors": [{"message": f"user-lookup stub: {e}"}]}
        out = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):  # readiness probe
        self.send_response(200)
        self.end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
