from http.server import BaseHTTPRequestHandler
import os
import json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Return a small JSON with public Pusher info (key, cluster).

        This endpoint intentionally does NOT return any secret. It is
        safe to call from browser clients so the demo page can auto-load
        the public key.
        """
        key = os.environ.get('PUSHER_KEY')
        cluster = os.environ.get('PUSHER_CLUSTER', 'eu')

        if not key:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'PUSHER_KEY not configured'
            }).encode())
            return

        payload = {
            'pusher_key': key,
            'pusher_cluster': cluster
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())
