# PandaScore Feeder

CS:GO maç verilerini ve analizlerini sunan bir API servisi. [PandaScore API](https://pandascore.co/) üzerinden maç verilerini çeker, analiz eder ve tahminler üretir.

## Özellikler

- 🎮 Yaklaşan CS:GO maçlarının takibi
- 📊 Canlı maç skorları ve istatistikleri
- 🔄 WebSocket ile gerçek zamanlı güncellemeler
- 📈 Takım performans analizleri
- 🎯 Maç sonucu tahminleri
- 🗺️ Harita bazlı performans analizi

## API Endpointleri

### Temel Endpointler

- `GET /api` - Yaklaşan maçları listeler
- `GET /api/live` - Devam eden maçları ve skorları getirir
- `GET /api/teams` - Takım listesi ve istatistiklerini getirir
  - `?team_id=X` - Belirli bir takımın detaylarını getirir

### Analiz Endpointleri

- `GET /api/analyze` - Takım analizlerini getirir
  - `?team_id=X` - Tek takım analizi
  - `?team1_id=X&team2_id=Y` - İki takım karşılaştırması

- `GET /api/predict` - Maç tahminlerini getirir
  - `?team1_id=X&team2_id=Y` - İki takım arasında tahmin üretir
  - `?match_id=X` - Belirli bir maç için tahmin üretir ve kaydeder

- `GET /api/matchstats` - Birleşik analiz sonuçlarını getirir
  - `?match_id=X` - Maç detayları, takım analizleri ve tahminler
  - `?team_id=X` - Tek takım için detaylı analiz
  - `?team1_id=X&team2_id=Y` - İki takım için karşılaştırmalı analiz

### WebSocket Desteği

Pusher üzerinden gerçek zamanlı güncellemeler:
- `matches` kanalı - Tüm maç listesi güncellemeleri
- `match-{id}` kanalları - Belirli maçların canlı güncellemeleri

## Kurulum

### Gerekli Environment Variables

```
DATABASE_URL="postgresql://<user>:<pass>@<host>:5432/<db>"
PANDASCORE_API_KEY="your-api-key"
PUSHER_APP_ID="your-app-id"
PUSHER_KEY="your-key"
PUSHER_SECRET="your-secret"
PUSHER_CLUSTER="eu"
```

### Vercel Deployment

1. Repository'yi fork edin
2. Vercel'de yeni proje oluşturun
3. Environment variable'ları ekleyin
4. Deploy edin

### Yerel Geliştirme

1. Repository'yi klonlayın
2. Dependencies'leri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
3. `.env` dosyasını oluşturun
4. Geliştirme sunucusunu başlatın:
   ```bash
   vercel dev
   ```

## Database Şeması

Ana tablolar:
- `matches` - Maç kayıtları
- `teams` - Takım bilgileri
- `team_stats` - Takım istatistikleri
- `historical_matches` - Geçmiş maç kayıtları
- `predictions` - Maç tahminleri
- `match_statistics` - Canlı maç istatistikleri

## Vercel Konfigürasyonu

Bu repository, Vercel konfigürasyonu için Infrastructure as Code yaklaşımını kullanır:
- Build ayarları ve cron görevleri `vercel.json` içinde tanımlıdır
- Günlük cron görevi (`0 0 * * *`) Hobby hesaplarıyla uyumludur
- Tüm endpoint'ler CORS desteklidir