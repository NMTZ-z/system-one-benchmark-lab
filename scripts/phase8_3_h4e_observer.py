"""H4E wrapper for the unchanged advisory recorder, with owned readiness proof."""
import hashlib
import hmac
from http.server import ThreadingHTTPServer
import json
import os

import phase8_3_h4e_contract as c
from phase8_2a_shadow_proxy import Handler as Recorder


def main():
    os.umask(0o077)
    path = c.PRIVATE / 'observer/correlation_key.private.bin'
    c.safe_path(path)
    if path.stat().st_mode & 0o077:
        raise c.H4EBlocked('private observation key required')
    key = path.read_bytes()
    source_sha = json.loads((c.PRIVATE / 'input.private.json').read_text())['source_sha']
    if len(key) != 32:
        raise c.H4EBlocked('observation key has wrong size')
    proof = hmac.new(key, ('observer-ready\0' + source_sha + '\0' + str(os.getpid())).encode(), hashlib.sha256).hexdigest()
    class Handler(Recorder):
        destination = 'http://127.0.0.1:18782'
        evidence_path = c.PRIVATE / 'observer/http.private.jsonl'

        def do_GET(self):
            if self.path != '/_h4e_ready':
                self.send_error(404); return
            body = json.dumps({'case_id': c.CASE_ID, 'pid': os.getpid(), 'proof': proof}).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            super().do_POST()
            if self.evidence_path.is_file():
                with self.evidence_path.open('rb') as stream: os.fsync(stream.fileno())

    with ThreadingHTTPServer(('127.0.0.1', 18793), Handler) as server:
        server.run_salt = os.urandom(16).hex()
        server.correlation_secret = key
        server.run_id = c.CASE_ID
        server.serve_forever(poll_interval=.1)


if __name__ == '__main__':
    main()
