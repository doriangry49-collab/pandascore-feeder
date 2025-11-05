from http.server import BaseHTTPRequestHandler
import os
import json
import requests
import psycopg2 # yeni tercümanımız

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        api_key = os.environ.get("PANDASCORE_API_KEY")
        db_url = os.environ.get("DATABASE_URL") # beynin adresi

        if not api_key or not db_url:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "api key veya database url eksik"}).encode())
            return

        conn = None
        try:
            # 1. veri avı
            url = "https://api.pandascore.co/csgo/matches/upcoming?sort=-scheduled_at&per_page=50"
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status() # api hatası varsa burada patlar
            matches = response.json()

            # 2. beyne bağlan
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()

            # 3. beynin içinde bir "maçlar" defteri oluştur (eğer yoksa)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY,
                    team1_name VARCHAR(255),
                    team2_name VARCHAR(255),
                    scheduled_at TIMESTAMP WITH TIME ZONE,
                    league_name VARCHAR(255),
                    raw_data JSONB,
                    inserted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)

            # 4. avlanan veriyi deftere yaz
            inserted_count = 0
            for match in matches:
                # ON CONFLICT: eğer aynı id'li maç zaten varsa, görmezden gel. bu, tekrar tekrar çalıştırabilmemizi sağlar.
                cur.execute("""
                    INSERT INTO matches (id, team1_name, team2_name, scheduled_at, league_name, raw_data)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, (
                    match['id'],
                    match['opponents'][0]['opponent']['name'] if len(match['opponents']) > 0 else 'TBD',
                    match['opponents'][1]['opponent']['name'] if len(match['opponents']) > 1 else 'TBD',
                    match['scheduled_at'],
                    match['league']['name'],
                    json.dumps(match) # tüm veriyi de json olarak saklayalım, ne olur ne olmaz.
                ))
                if cur.rowcount > 0:
                    inserted_count += 1
            
            conn.commit() # değişiklikleri kalıcı olarak kaydet
            cur.close()

            # 5. rapor ver
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "başarılı", 
                "fetched_matches": len(matches),
                "newly_inserted_matches": inserted_count
            }).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        finally:
            if conn is not None:
                conn.close() # her durumda bağlantıyı kapat

        return
