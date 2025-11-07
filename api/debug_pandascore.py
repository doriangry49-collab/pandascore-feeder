import os
import json
import requests
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            api_key = os.environ.get('PANDASCORE_API_KEY')
            if not api_key:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'PANDASCORE_API_KEY not set in env'}).encode())
                return

            url = 'https://api.pandascore.co/csgo/teams'
            headers = {'Authorization': f'Bearer {api_key}'}
            try:
                r = requests.get(url, headers=headers, timeout=15)
            except Exception as e:
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'request_failed', 'detail': str(e)}).encode())
                return

            # Return the PandaScore response body (caution: does not expose API key)
            self.send_response(r.status_code if r.status_code < 500 else 502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # If response is JSON, forward it
            try:
                self.wfile.write(r.content)
            except Exception:
                self.wfile.write(json.dumps({'error': 'could_not_forward_body'}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'internal', 'detail': str(e)}).encode())
