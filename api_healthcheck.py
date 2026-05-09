import urllib.request
import urllib.parse
import json
import ssl
import os
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("API_BASE_URL", "https://omapi.onlymonster.ai")

def fetch_data(endpoint, params=None):
    url = f"{BASE_URL}{endpoint}"
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
        
    req = urllib.request.Request(url)
    req.add_header("x-om-auth-token", API_KEY)
    req.add_header("Accept", "application/json")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"error_code": e.code, "error_body": e.read().decode('utf-8')}
    except Exception as e:
        return {"error": str(e)}

def test_api():
    if not API_KEY:
        print("⚠️ API_KEY not found .env!")
        return

    print("🔄 1. Checking /api/v0/accounts ...")
    accounts_data = fetch_data("/api/v0/accounts")
    print(json.dumps(accounts_data, indent=2, ensure_ascii=False))
    
    print("\n" + "="*50 + "\n")
    
    print("🔄 2. Checking /api/v0/users/metrics ...")
    metrics_data = fetch_data("/api/v0/users/metrics", {
        "from": "2026-05-01T00:00:00.000Z",
        "to": "2026-05-31T23:59:59.999Z",
        "limit": 100,
        "offset": 0
    })
    print(json.dumps(metrics_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_api()
