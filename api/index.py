from http.server import BaseHTTPRequestHandler
import os
import json
import requests
import psycopg2

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        print("--- fonksiyon tetiklendi ---")
        api_key = os.environ.get("PANDASCORE_API_KEY")
        db_url = os.environ.get("DATABASE_URL")

        if not api_key or not db_url:
            error_msg = "hata: api key veya database url eksik."
            print(error_msg)
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": error_msg}).encode())
            return

        print("api key ve db url bulundu.")
        conn = None
        try:
            # 1. veri avı
            print("pandascore'dan veri çekiliyor...")
            url = "https://api.pandascore.co/csgo/matches/upcoming?sort=-scheduled_at&per_page=5" # test için sayıyı düşürdüm
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            matches = response.json()
            print(f"{len(matches)} adet maç verisi çekildi.")

            # 2. beyne bağlan
            print("veritabanına bağlanmaya çalışılıyor...")
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            print("veritabanına başarıyla bağlandı.")

            # 3. tablo oluşturma
            print("tablo oluşturma/kontrol etme komutu gönderiliyor...")
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
            print("tablo komutu işlendi.")
            
            # 4. veri yazma
            print("veri yazma işlemi başlıyor...")
            inserted_count = 0
            for match in matches:
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
                    json.dumps(match)
                ))
                if cur.rowcount > 0:
                    inserted_count += 1
            
            print(f"{inserted_count} yeni kayıt eklendi.")
            conn.commit()
            cur.close()
            print("işlem tamamlandı ve bağlantı kapatıldı.")

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
            error_msg = f"KRİTİK HATA: {str(e)}"
            print(error_msg) # bu, katilin itirafı olacak
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": error_msg}).encode())
        
        finally:
            if conn is not None:
                conn.close()
            print("--- fonksiyon tamamlandı ---")

        return
