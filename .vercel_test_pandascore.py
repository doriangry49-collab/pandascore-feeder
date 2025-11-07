import requests, json, os, sys

# Try to read key from .env first (do NOT print it)
def load_key():
    key = None
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('PANDASCORE_API_KEY'):
                    parts = line.split('=', 1)
                    if len(parts) > 1:
                        key = parts[1].strip().strip('"').strip("'")
                        break
    except FileNotFoundError:
        pass
    if not key:
        key = os.environ.get('PANDASCORE_API_KEY')
    return key

key = load_key()
if not key:
    print('NO_PANDASCORE_KEY')
    sys.exit(2)

url = 'https://api.pandascore.co/csgo/teams'
headers = {'Authorization': f'Bearer {key}'}

try:
    r = requests.get(url, headers=headers, timeout=15)
except Exception as e:
    print('REQUEST_ERROR', str(e))
    sys.exit(2)

print('STATUS', r.status_code)
try:
    j = r.json()
    if isinstance(j, list) and len(j) > 0:
        # show top-level keys of first item and a small snippet
        print('FIRST_ITEM_KEYS', list(j[0].keys()))
        snippet = json.dumps(j[0], ensure_ascii=False)
        print('FIRST_ITEM_SNIPPET', snippet[:1200])
    else:
        print('RESPONSE_JSON', json.dumps(j)[:1200])
except Exception:
    print('RESPONSE_TEXT', r.text[:1200])
