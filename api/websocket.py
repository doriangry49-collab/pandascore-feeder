from http.server import BaseHTTPRequestHandler
import os
import json
import requests
import psycopg2
from datetime import datetime
import pusher
import time

# Pusher client initialization
def get_pusher_client():
    # Guard: ensure required env vars exist before creating client
    app_id = os.environ.get('PUSHER_APP_ID')
    key = os.environ.get('PUSHER_KEY')
    secret = os.environ.get('PUSHER_SECRET')
    cluster = os.environ.get('PUSHER_CLUSTER', 'eu')

    if not (app_id and key and secret):
        # Missing credentials -> return None so callers can skip publishing
        return None

    return pusher.Pusher(
        app_id=app_id,
        key=key,
        secret=secret,
        cluster=cluster,
        ssl=True
    )

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # API ve DB credentials
        api_key = os.environ.get("PANDASCORE_API_KEY")
        db_url = os.environ.get("DATABASE_URL")
        
        if not api_key or not db_url:
            self._send_error("API key veya database URL eksik")
            return
            
        try:
            # Pusher client'ı başlat (None ise publish adımları atlanacak)
            pusher_client = get_pusher_client()
            pusher_enabled = pusher_client is not None
            
            # 1. Canlı maçları çek
            live_matches = self._fetch_live_matches(api_key)
            
            # 2. Her maç için detaylı veri çek ve yayınla
            results = []
            for match in live_matches:
                match_data = self._process_match(match, api_key)
                if match_data:
                    # DB'ye kaydet
                    self._save_match_data(match_data, db_url)
                    results.append(match_data)
                    
                    # WebSocket üzerinden yayınla (sadece pusher mevcutsa)
                    if pusher_enabled:
                        try:
                            channel = f"match-{match_data['match_id']}"
                            pusher_client.trigger(
                                channel,
                                'match-update',
                                {
                                    'match': match_data,
                                    'timestamp': datetime.utcnow().isoformat()
                                }
                            )
                        except Exception as e:
                            # Log publishing failure but don't fail the whole request
                            print(f"Pusher publish hata: {e}")
            
            # 3. Genel maç listesi güncellemesini yayınla
            pusher_client.trigger(
                'matches',
                'list-update',
                {
                    'matches': results,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            # 4. HTTP yanıtı döndür
            self._send_success({
                "status": "success",
                "live_matches": results,
                "timestamp": datetime.utcnow().isoformat(),
                "websocket": {
                    "enabled": True,
                    "channels": {
                        "all_matches": "matches",
                        "individual_matches": [f"match-{match['match_id']}" for match in results]
                    }
                }
            })
            
        except Exception as e:
            self._send_error(f"Hata: {str(e)}")

    def _fetch_live_matches(self, api_key):
        """Devam eden CS:GO maçlarını çeker"""
        url = "https://api.pandascore.co/csgo/matches/running"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "per_page": "50",
                "sort": "-scheduled_at"
            }
        )
        response.raise_for_status()
        return response.json()

    def _process_match(self, match, api_key):
        """Maç verilerini işler ve formatlı hale getirir"""
        try:
            match_id = match.get('id')
            details_url = f"https://api.pandascore.co/csgo/matches/{match_id}/stats"
            details = requests.get(
                details_url,
                headers={"Authorization": f"Bearer {api_key}"}
            ).json()

            return {
                "match_id": match_id,
                "status": match.get('status'),
                "current_score": {
                    "team1": match.get('results', [{'score': 0}])[0].get('score', 0),
                    "team2": match.get('results', [{'score': 0}])[1].get('score', 0) if len(match.get('results', [])) > 1 else 0
                },
                "teams": {
                    "team1": {
                        "id": match.get('opponents', [{}])[0].get('opponent', {}).get('id'),
                        "name": match.get('opponents', [{}])[0].get('opponent', {}).get('name', 'TBD'),
                    },
                    "team2": {
                        "id": match.get('opponents', [{}])[1].get('opponent', {}).get('id') if len(match.get('opponents', [])) > 1 else None,
                        "name": match.get('opponents', [{}])[1].get('opponent', {}).get('name', 'TBD') if len(match.get('opponents', [])) > 1 else 'TBD',
                    }
                },
                "current_round": details.get('current_round', 0),
                "map": details.get('map', {}).get('name'),
                "player_stats": details.get('players', []),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"Maç işleme hatası ({match_id}): {str(e)}")
            return None

    def _save_match_data(self, match_data, db_url):
        """İşlenmiş maç verisini DB'ye kaydeder"""
        conn = None
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            
            # 1. matches tablosunu güncelle
            cur.execute("""
                UPDATE matches 
                SET match_status = %s,
                    live_score = %s,
                    player_stats = %s
                WHERE id = %s
            """, (
                match_data['status'],
                json.dumps(match_data['current_score']),
                json.dumps(match_data['player_stats']),
                match_data['match_id']
            ))
            
            # 2. İstatistikleri kaydet
            cur.execute("""
                INSERT INTO match_statistics 
                    (match_id, timestamp, event_type, event_data)
                VALUES 
                    (%s, %s, %s, %s)
                ON CONFLICT (match_id, timestamp) DO NOTHING
            """, (
                match_data['match_id'],
                match_data['timestamp'],
                'live_update',
                json.dumps(match_data)
            ))
            
            conn.commit()
            
        finally:
            if conn:
                conn.close()

    def _send_success(self, data):
        """Başarılı yanıt gönder"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, message):
        """Hata yanıtı gönder"""
        self.send_response(500)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "error",
            "message": message
        }).encode())