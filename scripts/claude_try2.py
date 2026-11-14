import os, sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from pguard.llm_adapter import _http_transport, load_dotenv
load_dotenv(str(pathlib.Path(__file__).resolve().parents[1] / '.env'))
base = os.environ['CLAUDE_BASE_URL'].rstrip('/')
h = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0', 'Authorization': 'Bearer ' + os.environ['ANTHROPIC_API_KEY']}
trials = [
 ('no-temperature', {'model': 'claude-sonnet-5-5', 'messages': [{'role': 'user', 'content': 'Reply with the single word: pong'}], 'max_tokens': 256}),
 ('temp1', {'model': 'claude-sonnet-5-5', 'messages': [{'role': 'user', 'content': 'Reply with the single word: pong'}], 'temperature': 1.0, 'max_tokens': 256}),
]
for name, p in trials:
 s, b = _http_transport('POST', base + '/chat/completions', h, p, 60.0)
 u = ''
 if s == 200:
  d = json.loads(b)
  u = ' usage=' + json.dumps(d.get('usage', {}))
 print(name, 'status:', s, (b[:200] if s != 200 else 'OK content=' + repr(d['choices'][0]['message']['content'][:30]) + u))
