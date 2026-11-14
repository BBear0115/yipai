"""Isolated UI preview using recorded images; never calls an image provider.

Run: python3 testing/preview_server.py --port 8018 [--empty] [--large-text]
Data lives in a disposable temporary directory. Existing user data is untouched.
"""
import argparse
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
import shutil
import sys
import tempfile
import time
from uuid import uuid4

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'backend'))
import server

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=8018)
parser.add_argument('--empty', action='store_true')
parser.add_argument('--large-text', action='store_true', help='Render at 200% root font size for layout checks')
args = parser.parse_args()
fixtures = server.ROOT / 'testing' / '2026-11-10'
server.credentials = lambda: ('mock-only', 'mock-only')


def simulate(job_id, model, workflow_type='tryon', workflow_config=None):
    time.sleep(2)
    server.update_job(job_id, status='running')
    time.sleep(8)
    name = 'floral-dress' if model == 'female' else 'red-hoodie'
    output = server.data_path(job_id, 'result')
    if workflow_type == 'pose_variation':
        count = (workflow_config or {}).get('pose_count', 4)
        columns = 2 if count in (4, 6) else 3
        rows = 2 if count == 4 else 3
        with server.Image.open(fixtures / f'{name}-result.jpg') as source:
            tile = server.ImageOps.fit(source.convert('RGB'), (400, 600))
            sheet = server.Image.new('RGB', (columns * 400, rows * 600), '#f0f0f2')
            for index in range(count):
                sheet.paste(tile, ((index % columns) * 400, (index // columns) * 600))
            sheet.save(output, 'JPEG', quality=90)
    else:
        shutil.copyfile(fixtures / f'{name}-result.jpg', output)
    server.update_job(job_id, status='succeeded')


server.generate = simulate
original_public_job = server.public_job


def preview_public_job(row):
    job = original_public_job(row)
    if 'workflow_type' in row.keys() and row['workflow_type'] == 'background_change':
        job['previewOnly'] = True
    return job


server.public_job = preview_public_job


class PreviewHandler(server.Handler):
    def do_GET(self):
        if args.large_text and self.path in ('/', '/index.html'):
            raw = (server.STATIC / 'index.html').read_text().replace('</head>', '<style>:root{font-size:200%}</style></head>').encode('utf-8')
            self.headers_out(200, 'text/html; charset=utf-8', len(raw))
            return self.wfile.write(raw)
        return super().do_GET()

    def session(self):
        visitor = super().session()
        if args.empty:
            return visitor
        with server.connect() as db:
            existing = db.execute('SELECT COUNT(*) FROM jobs WHERE visitor=?', (visitor,)).fetchone()[0]
            if existing:
                return visitor
            samples = [('floral-dress', 'female', 'succeeded'), ('red-hoodie', 'male', 'succeeded'), ('striped-shirt', 'female', 'succeeded'), ('denim-jacket', 'male', 'failed')]
            for index, (name, model, status) in enumerate(samples):
                job_id = uuid4().hex
                created = (datetime.now(timezone.utc) - timedelta(hours=index)).isoformat()
                db.execute('INSERT INTO jobs (id,visitor,idem,model,status,created,updated,error) VALUES (?,?,?,?,?,?,?,?)',
                           (job_id, visitor, str(uuid4()), model, status, created, created, '模拟网络失败，可重试' if status == 'failed' else None))
                with server.Image.open(fixtures / f'{name}.png') as image:
                    image.convert('RGB').save(server.data_path(job_id, 'input'), 'JPEG')
                if status == 'succeeded':
                    result = 'striped-shirt-v2-result.jpg' if name == 'striped-shirt' else f'{name}-result.jpg'
                    shutil.copyfile(fixtures / result, server.data_path(job_id, 'result'))
        return visitor


with tempfile.TemporaryDirectory(prefix='yipai-ui-preview-') as folder:
    server.DATA = Path(folder)
    server.DB = server.DATA / 'jobs.sqlite3'
    server.init_db()
    print(f'MOCK UI preview (no generation charges): http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), PreviewHandler).serve_forever()
