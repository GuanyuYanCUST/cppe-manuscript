import os, sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from pguard.llm_adapter import _http_transport, load_dotenv
load_dotenv(str(pathlib.Path(__file__).resolve().parents[1] / '.env'))
url = os.environ['CLAUDE_BASE_URL'].rstrip('/') + '/models'
h = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Bearer ' + os.environ['ANTHROPIC_API_KEY']}
s, b = _http_transport('GET', url, h, None, 30.0)
print('status:', s)
ids = [m['id'] for m in json.loads(b).get('data', [])] if s == 200 else b[:400]
print(ids if s == 200 else ids)
