from http.server import BaseHTTPRequestHandler
import os
import json
import requests

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # vercel environment variables'dan anahtarını alacak
        api_key = os.environ.get("PANDASCORE_API_KEY")

        if not api_key:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "pandascore api key bulunamadı"}).encode())
            return

        try:
            # pandascore'a istek atıyoruz (örnek: cs:go maçları)
            url = "https://api.pandascore.co/csgo/matches/upcoming"
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(url, headers=headers)
            
            # api'den gelen veriyi direkt olarak json'a çeviriyoruz
            data = response.json()
            
            # başarılı cevap
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())

        except Exception as e:
            # hata olursa yakala ve göster
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        return

