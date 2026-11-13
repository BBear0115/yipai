"""Exercise the deployed local HTTP API; real gateway calls incur usage."""
import base64
import http.cookiejar
import json
from pathlib import Path
import time
from urllib.request import Request, build_opener, HTTPCookieProcessor
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8000'
CASES = [('red-hoodie', 'male'), ('floral-dress', 'female'), ('denim-jacket', 'male')]

for name, model in CASES:
    path = ROOT / f'{name}.png'
    deadline = time.monotonic() + 1200
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(3)
    if not path.exists():
        raise RuntimeError(f'{name}: 测试原图未就绪')
    record = ROOT / f'{name}-run.json'
    if record.exists():
        print(f'{name}: 已有运行记录，跳过以免重复计费', flush=True)
        continue
    client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    assert json.load(client.open(BASE+'/api/session'))['ready']
    payload = {'image': 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode(),
               'model': model, 'idempotencyKey': str(uuid4())}
    def submit():
        return json.load(client.open(Request(BASE+'/api/jobs', data=json.dumps(payload).encode(),
            headers={'Content-Type':'application/json'}, method='POST')))['job']
    start = time.monotonic()
    job = submit()
    record.write_text(json.dumps({'job':job,'submitted':True},ensure_ascii=False,indent=2))
    assert submit()['id'] == job['id']
    print(f'{name}: 已提交，重复提交未创建第二个任务', flush=True)
    while job['status'] in ('queued','running') and time.monotonic()-start < 660:
        time.sleep(4)
        job = json.load(client.open(BASE+'/api/jobs/'+job['id']))['job']
    elapsed = round(time.monotonic()-start,1)
    result = {'job':job,'elapsed_seconds':elapsed,'idempotency_passed':True}
    if job['status']=='succeeded':
        (ROOT/f'{name}-result.jpg').write_bytes(client.open(BASE+job['image']).read())
        (ROOT/f'{name}-normalized.jpg').write_bytes(client.open(BASE+job['original']).read())
        assert len(json.load(client.open(BASE+'/api/jobs'))['jobs']) == 1
        result['history_passed'] = True
    record.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(f'{name}: {job["status"]}, {elapsed}s', flush=True)
