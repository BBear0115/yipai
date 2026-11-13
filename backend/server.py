"""Local, anonymous Image2 backend for 衣拍."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from backend.workflows.background_change import build_background_change_prompt
from backend.workflows.pose_variation import build_pose_variation_prompt
from backend.workflows.retouch import build_product_retouch_prompt, build_material_enhancement_prompt
from backend.workflows.fusion import build_outfit_fusion_prompt, build_product_set_prompt
from backend.workflows.translation import build_image_translation_prompt

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'mockup'
DATA = Path(os.environ.get('YIPAI_DATA_DIR', str(ROOT / 'backend' / 'data')))
DB = DATA / 'jobs.sqlite3'
GATEWAY = 'https://ai-force.duxiaoman-int.com/v1/responses'
MAX_INPUT = 20 * 1024 * 1024
MAX_BODY = 30 * 1024 * 1024
MAX_OUTPUT = 40 * 1024 * 1024
SLOTS = threading.BoundedSemaphore(2)
Image.MAX_IMAGE_PIXELS = 30_000_000


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def credentials() -> tuple[str | None, str | None]:
    source = Path(os.environ.get('IMAGE2_ENV_FILE', str(ROOT / '.env.local')))
    values = {}
    if source.is_file():
        for line in source.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                if key.strip() in ('IMAGE2_GATEWAY_API_KEY', 'IMAGE2_UUAP_ID'):
                    values[key.strip()] = value.strip().strip('"\'')
    return (os.environ.get('IMAGE2_GATEWAY_API_KEY') or values.get('IMAGE2_GATEWAY_API_KEY'),
            os.environ.get('IMAGE2_UUAP_ID') or values.get('IMAGE2_UUAP_ID'))


def connect():
    connection = sqlite3.connect(DB, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    DATA.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, visitor TEXT NOT NULL, idem TEXT NOT NULL,
            model TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL,
            updated TEXT NOT NULL, request_id TEXT, error TEXT,
            UNIQUE(visitor, idem))''')
        db.execute('CREATE INDEX IF NOT EXISTS jobs_visitor_created ON jobs(visitor, created DESC)')

        # Add workflow-related columns to jobs table if they don't exist
        cursor = db.execute("PRAGMA table_info(jobs)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'workflow_type' not in columns:
            db.execute('ALTER TABLE jobs ADD COLUMN workflow_type TEXT NOT NULL DEFAULT "tryon"')
        if 'workflow_config' not in columns:
            db.execute('ALTER TABLE jobs ADD COLUMN workflow_config TEXT')
        if 'source_job_id' not in columns:
            db.execute('ALTER TABLE jobs ADD COLUMN source_job_id TEXT')
        if 'input_images' not in columns:
            db.execute('ALTER TABLE jobs ADD COLUMN input_images TEXT')

        # Create workflow_types table
        db.execute('''CREATE TABLE IF NOT EXISTS workflow_types (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0)''')

        # Initialize workflow types if table is empty
        existing = db.execute('SELECT COUNT(*) FROM workflow_types').fetchone()[0]
        if existing == 0:
            workflows = [
                ('tryon', 'tryon', '虚拟试穿', '让模特试穿商品，生成真实的上身/上脚效果图', '👗', 1),
                ('pose_variation', 'pose_variation', '姿态变化', '保持模特身份，改变姿势和构图', '🤸', 2),
                ('background_change', 'background_change', '背景替换', '更换拍摄场景和背景', '🌄', 3),
                ('product_retouch', 'product_retouch', '商品精修', '优化商品细节，修正瑕疵', '✨', 4),
                ('outfit_fusion', 'outfit_fusion', '服饰融合', '将多件商品组合在一起展示', '👔', 5),
                ('material_enhance', 'material_enhance', '材质增强', '强化材质表现，提升质感', '💎', 6),
                ('product_set', 'product_set', '商品组合', '多商品场景化展示', '📦', 7),
                ('image_translation', 'image_translation', '图像转译', '风格迁移和图像变换', '🎨', 8),
            ]
            db.executemany(
                'INSERT INTO workflow_types (id, name, display_name, description, icon, sort_order) VALUES (?, ?, ?, ?, ?, ?)',
                workflows
            )

        db.execute('''CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY, visitor TEXT NOT NULL, nickname TEXT NOT NULL,
            product_name TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS posts_created ON posts(created DESC)')
        db.execute('''CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, gender TEXT NOT NULL,
            image_path TEXT NOT NULL, is_preset INTEGER NOT NULL DEFAULT 1,
            visitor TEXT, sort_order INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS models_preset_sort ON models(is_preset DESC, sort_order ASC, created ASC)')
        db.execute('''CREATE TABLE IF NOT EXISTS task_queue (
            id TEXT PRIMARY KEY, visitor TEXT NOT NULL, title TEXT NOT NULL,
            status TEXT NOT NULL, status_group TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0, expected_count INTEGER NOT NULL DEFAULT 1,
            result_count INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL,
            updated TEXT NOT NULL, completed TEXT)''')
        db.execute('CREATE INDEX IF NOT EXISTS task_queue_visitor_created ON task_queue(visitor, created DESC)')
        db.execute("UPDATE jobs SET status='failed', error='服务已重启，请重新生成', updated=? WHERE status IN ('queued','running')", (now(),))


def data_path(job_id: str, kind: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise ValueError('任务编号无效')
    return DATA / f'{job_id}.{kind}.jpg'


def post_path(post_id: str, kind: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', post_id) or kind not in ('input', 'result'):
        raise ValueError('作品编号无效')
    return DATA / f'post-{post_id}.{kind}.jpg'


def model_path(model_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', model_id):
        raise ValueError('模特编号无效')
    return DATA / f'model-{model_id}.jpg'


def public_post(row, visitor: str):
    post_id = row['id']
    return {
        'id': post_id, 'nickname': row['nickname'],
        'productName': row['product_name'], 'note': row['note'],
        'created': row['created'], 'mine': row['visitor'] == visitor,
        'image': f'/api/posts/{post_id}/result',
        'productImage': f'/api/posts/{post_id}/input',
    }


def parse_image(data_url: str) -> bytes:
    match = re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)', data_url)
    if not match:
        raise ValueError('请上传 PNG、JPG 或 WebP 图片')
    try:
        raw = base64.b64decode(match.group(1), validate=True)
    except Exception as exc:
        raise ValueError('图片数据无效') from exc
    if not raw or len(raw) > MAX_INPUT:
        raise ValueError('图片不能超过 20 MB')
    try:
        image = Image.open(BytesIO(raw))
        if image.format not in ('PNG', 'JPEG', 'WEBP'):
            raise ValueError('图片格式不支持')
        image.load()
        image = ImageOps.exif_transpose(image).convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError('无法读取图片') from exc
    if min(image.size) < 512:
        raise ValueError('图片尺寸过小，请换更清楚的图片')
    output = BytesIO()
    image.save(output, 'JPEG', quality=92)
    return output.getvalue()


def image_data_url(raw: bytes) -> str:
    return 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii')


def extract_output(payload: dict) -> bytes:
    output = payload.get('output')
    if not isinstance(output, list):
        raise RuntimeError('图片服务未返回结果')
    for item in output:
        if not isinstance(item, dict):
            continue
        for content in [item, *(item.get('content') or [])]:
            if not isinstance(content, dict):
                continue
            value = content.get('result') or content.get('b64_json')
            if not isinstance(value, str):
                continue
            value = ''.join(value.split())
            if value.startswith('data:image/'):
                value = value.partition(',')[2]
            try:
                raw = base64.b64decode(value, validate=True)
                if not raw or len(raw) > MAX_OUTPUT:
                    continue
                with Image.open(BytesIO(raw)) as img:
                    img.verify()
                return raw
            except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
                continue
    raise RuntimeError('图片服务未返回可读取的图片')


def prompt_for(model: str) -> str:
    person = '成年女性' if model == 'female' else '成年男性'
    return (
        '图1是唯一目标商品的原图，图2是所选虚拟模特的形象参考。'
        f'让图2中的{person}模特自然展示图1的商品，生成电商可用的竖版真实摄影商品图。'
        '如果图1是服装，准确展示上身效果；如果是鞋，准确展示上脚效果和完整鞋型。'
        '保留模特面部、发型和整体身份特征。背景简洁，柔和光线，商品清晰且不被遮挡。'
        '严格保留目标商品的颜色、图案、标识、文字、版型、鞋底和结构。'
        '以图1实际可见结构为准，不按常见款式补全：逐一保留口袋、纽扣、拉链、装饰的数量和位置；'
        '单侧口袋必须保持单侧，不得为了左右对称添加另一侧口袋。'
        '模特双手自然垂放且不遮挡商品，不插兜、不提拉下摆、不把上衣塞进裤腰；长发放到肩后，完整展示领口和衣身。'
        '不要复制图2中的服饰来替代目标商品，不要凭空增加商品图案或品牌。'
        '只有一位成年模特；不要额外人物、文字、价格、边框或水印。'
    )


def watermark(raw: bytes) -> bytes:
    image = Image.open(BytesIO(raw)).convert('RGB')
    draw = ImageDraw.Draw(image, 'RGBA')
    label = '衣拍 · 人工智能生成'
    try:
        font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', max(20, image.width // 48))
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(12, image.width // 70)
    margin = max(16, image.width // 50)
    x = image.width - width - pad * 2 - margin
    y = image.height - height - pad * 2 - margin
    draw.rounded_rectangle((x, y, x + width + pad * 2, y + height + pad * 2), radius=10, fill=(24, 24, 24, 180))
    draw.text((x + pad, y + pad - bbox[1]), label, fill=(255, 255, 255, 255), font=font)
    result = BytesIO()
    image.save(result, 'JPEG', quality=92)
    return result.getvalue()


def update_job(job_id: str, **fields):
    fields['updated'] = now()
    with connect() as db:
        names = list(fields)
        db.execute('UPDATE jobs SET ' + ', '.join(f'{name}=?' for name in names) + ' WHERE id=?', [fields[name] for name in names] + [job_id])


def generate(job_id: str, model: str, workflow_type: str = 'tryon', workflow_config: dict | None = None):
    with SLOTS:
        request_id = str(uuid4())
        try:
            api_key, uuap_id = credentials()
            if not api_key:
                raise RuntimeError('图片服务未配置')

            update_job(job_id, status='running', request_id=request_id)

            if workflow_type == 'pose_variation':
                pose_count = (workflow_config or {}).get('pose_count', 4)
                if pose_count not in (4, 6, 8):
                    pose_count = 4

                prompt_text = build_pose_variation_prompt(pose_count)
                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                size = '1536x1536' if pose_count == 4 else '1536x2048'
            elif workflow_type == 'background_change':
                scene_type = (workflow_config or {}).get('scene_type', 'white')
                prompt_text = build_background_change_prompt(scene_type)
                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                size = '1024x1536'
            elif workflow_type == 'product_retouch':
                mode = (workflow_config or {}).get('mode', 'faithful-retouch')
                user_instruction = (workflow_config or {}).get('instruction', '')
                prompt_text = build_product_retouch_prompt(mode, user_instruction)
                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                size = '1024x1536'
            elif workflow_type == 'material_enhance':
                material_type = (workflow_config or {}).get('material_type', 'cotton')
                prompt_text = build_material_enhancement_prompt(material_type)
                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                size = '1024x1536'
            elif workflow_type == 'outfit_fusion':
                items = (workflow_config or {}).get('items', [])
                if not items:
                    raise ValueError('outfit_fusion requires items configuration')
                prompt_text = build_outfit_fusion_prompt(items)
                # 多图输入：从 workflow_config 中的 items 获取图片路径
                images = []
                for item in items:
                    img_path = data_path(job_id, f"input_{item['image_num']}")
                    if img_path.is_file():
                        images.append(image_data_url(img_path.read_bytes()))
                if not images:
                    raise ValueError('No input images found for outfit_fusion')
                size = '1024x1536'
            elif workflow_type == 'product_set':
                angles = (workflow_config or {}).get('angles', ['front', 'side', 'back', 'detail'])
                prompt_text = build_product_set_prompt(angles)
                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                size = '1536x2048' if len(angles) >= 6 else '1536x1536'
            elif workflow_type == 'image_translation':
                translation_type = (workflow_config or {}).get('translation_type', 'season')
                source_style = (workflow_config or {}).get('source_style', '')
                target_style = (workflow_config or {}).get('target_style', '')
                custom_desc = (workflow_config or {}).get('custom_desc', '')
                if not source_style or not target_style:
                    raise ValueError('image_translation requires source_style and target_style')
                prompt_text = build_image_translation_prompt(translation_type, source_style, target_style, custom_desc)
                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                size = '1024x1536'
            else:
                model_file = STATIC / 'assets' / f'{model}-model.png'
                if not model_file.is_file():
                    raise RuntimeError('模特参考图缺失')

                prompt_text = prompt_for(model)
                images = [image_data_url(data_path(job_id, 'input').read_bytes()),
                          'data:image/png;base64,' + base64.b64encode(model_file.read_bytes()).decode('ascii')]
                size = '1024x1536'

            body = {
                'model': 'gpt-image-2.5-flare',
                'input': [{'role': 'user', 'content': [
                    {'type': 'input_text', 'text': prompt_text},
                    *[{'type': 'input_image', 'image_url': image} for image in images],
                ]}],
                'size': size, 'quality': 'high',
            }
            headers = {'Authorization': api_key, 'Content-Type': 'application/json',
                       'request-id': request_id}
            if uuap_id:
                headers['uuap-id'] = uuap_id
            request = Request(GATEWAY, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
            with urlopen(request, timeout=300) as response:
                response_raw = response.read(MAX_OUTPUT + 1)
            if len(response_raw) > MAX_OUTPUT:
                raise RuntimeError('图片服务响应过大')
            result = watermark(extract_output(json.loads(response_raw)))
            destination = data_path(job_id, 'result')
            temporary = destination.with_suffix('.tmp')
            temporary.write_bytes(result)
            temporary.replace(destination)
            update_job(job_id, status='succeeded')
            print(f'Image2 request={request_id} status=success')
        except HTTPError as exc:
            update_job(job_id, status='failed', error=f'图片服务请求失败（{exc.code}）')
            print(f'Image2 request={request_id} http={exc.code}')
        except (URLError, TimeoutError):
            update_job(job_id, status='failed', error='图片服务连接超时，请重新生成')
            print(f'Image2 request={request_id} status=timeout')
        except Exception as exc:
            message = str(exc) if str(exc) in ('图片服务未配置', '模特参考图缺失') else '图片生成失败，请重新生成'
            update_job(job_id, status='failed', error=message)
            print(f'Image2 request={request_id} failure={type(exc).__name__}')


def public_job(row):
    job_id = row['id']
    result = {
        'id': job_id, 'model': row['model'], 'status': row['status'],
        'created': row['created'], 'error': row['error'],
        'original': f'/api/jobs/{job_id}/input',
        'image': f'/api/jobs/{job_id}/result' if row['status'] == 'succeeded' else None,
    }
    # Add workflow fields if they exist
    if 'workflow_type' in row.keys():
        result['workflowType'] = row['workflow_type']
    if 'workflow_config' in row.keys() and row['workflow_config']:
        try:
            result['workflowConfig'] = json.loads(row['workflow_config']) if row['workflow_config'] else None
        except (json.JSONDecodeError, TypeError):
            result['workflowConfig'] = None
    if 'source_job_id' in row.keys():
        result['sourceJobId'] = row['source_job_id']
    if 'input_images' in row.keys() and row['input_images']:
        try:
            result['inputImages'] = json.loads(row['input_images']) if row['input_images'] else None
        except (json.JSONDecodeError, TypeError):
            result['inputImages'] = None
    return result


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args))

    def session(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
        except cookies.CookieError:
            pass
        item = jar.get('yipai_session')
        value = item.value if item else None
        if not value or not re.fullmatch(r'[a-f0-9]{64}', value):
            value = secrets.token_hex(32)
            self.new_cookie = value
        else:
            self.new_cookie = None
        return hashlib.sha256(value.encode()).hexdigest()

    def headers_out(self, status, content_type, size):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        if getattr(self, 'new_cookie', None):
            self.send_header('Set-Cookie', f'yipai_session={self.new_cookie}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000')
        self.end_headers()

    def json_out(self, status, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.headers_out(status, 'application/json; charset=utf-8', len(raw))
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == '/api/session':
            self.session()
            key, uid = credentials()
            return self.json_out(200, {'ready': bool(key)})
        if self.path == '/api/tasks':
            visitor = self.session()
            with connect() as db:
                rows = db.execute('SELECT * FROM task_queue WHERE visitor=? ORDER BY created DESC', (visitor,)).fetchall()
            tasks = []
            for row in rows:
                progress_pct = row['progress'] if row['progress'] >= 0 else 0
                tasks.append({
                    'id': row['id'],
                    'title': row['title'],
                    'status': row['status'],
                    'statusGroup': row['status_group'],
                    'progress': progress_pct,
                    'expectedCount': row['expected_count'],
                    'resultCount': row['result_count'],
                    'created': row['created'],
                    'updated': row['updated'],
                    'completed': row['completed'],
                })
            grouped = {
                'queued': [t for t in tasks if t['statusGroup'] == 'queued'],
                'running': [t for t in tasks if t['statusGroup'] == 'running'],
                'completed': [t for t in tasks if t['statusGroup'] == 'completed'],
                'failed': [t for t in tasks if t['statusGroup'] == 'failed'],
            }
            return self.json_out(200, {'tasks': tasks, 'grouped': grouped})
        if self.path == '/api/jobs':
            visitor = self.session()
            with connect() as db:
                rows = db.execute('SELECT * FROM jobs WHERE visitor=? ORDER BY created DESC LIMIT 100', (visitor,)).fetchall()
            return self.json_out(200, {'jobs': [public_job(row) for row in rows]})
        if self.path == '/api/posts':
            visitor = self.session()
            with connect() as db:
                rows = db.execute('SELECT * FROM posts ORDER BY created DESC LIMIT 50').fetchall()
            return self.json_out(200, {'posts': [public_post(row, visitor) for row in rows]})
        if self.path == '/api/workflows':
            with connect() as db:
                rows = db.execute('SELECT * FROM workflow_types ORDER BY sort_order ASC').fetchall()
            workflows = [{
                'id': row['id'],
                'name': row['name'],
                'displayName': row['display_name'],
                'description': row['description'],
                'icon': row['icon'],
                'sortOrder': row['sort_order']
            } for row in rows]
            return self.json_out(200, {'workflows': workflows})
        if self.path == '/api/models':
            visitor = self.session()
            with connect() as db:
                rows = db.execute('SELECT * FROM models WHERE is_preset=1 OR visitor=? ORDER BY is_preset DESC, sort_order ASC, created ASC', (visitor,)).fetchall()
            return self.json_out(200, {'models': [{'id': row['id'], 'name': row['name'], 'gender': row['gender'], 'image': f'/api/models/{row["id"]}/image', 'isPreset': bool(row['is_preset'])} for row in rows]})
        model_match = re.fullmatch(r'/api/models/([a-f0-9]{32})/image', self.path)
        if model_match:
            model_id = model_match.group(1)
            visitor = self.session()
            with connect() as db:
                row = db.execute('SELECT * FROM models WHERE id=?', (model_id,)).fetchone()
            if not row:
                return self.json_out(404, {'error': '模特不存在'})
            if not row['is_preset'] and row['visitor'] != visitor:
                return self.json_out(403, {'error': '无权访问该模特'})
            path = model_path(model_id)
            if not path.is_file():
                return self.json_out(404, {'error': '模特图片不存在'})
            raw = path.read_bytes()
            self.headers_out(200, 'image/jpeg', len(raw))
            return self.wfile.write(raw)
        post_match = re.fullmatch(r'/api/posts/([a-f0-9]{32})(?:/(input|result))?', self.path)
        if post_match:
            post_id, kind = post_match.groups()
            visitor = self.session()
            with connect() as db:
                row = db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
            if not row:
                return self.json_out(404, {'error': '社区作品不存在'})
            if not kind:
                return self.json_out(200, {'post': public_post(row, visitor)})
            path = post_path(post_id, kind)
            if not path.is_file():
                return self.json_out(404, {'error': '图片不存在'})
            raw = path.read_bytes()
            self.headers_out(200, 'image/jpeg', len(raw))
            return self.wfile.write(raw)
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})(?:/(input|result))?', self.path)
        if match:
            visitor = self.session()
            job_id, kind = match.groups()
            with connect() as db:
                row = db.execute('SELECT * FROM jobs WHERE id=? AND visitor=?', (job_id, visitor)).fetchone()
            if not row:
                return self.json_out(404, {'error': '作品不存在'})
            if not kind:
                return self.json_out(200, {'job': public_job(row)})
            if kind == 'result' and row['status'] != 'succeeded':
                return self.json_out(404, {'error': '图片尚未生成'})
            path = data_path(job_id, kind)
            if not path.is_file():
                return self.json_out(404, {'error': '图片不存在'})
            raw = path.read_bytes()
            self.headers_out(200, 'image/jpeg', len(raw))
            return self.wfile.write(raw)
        if self.path.startswith('/api/'):
            return self.json_out(404, {'error': '接口不存在'})
        if self.path.startswith('/.') or '..' in self.path:
            return self.json_out(404, {'error': '页面不存在'})
        return super().do_GET()

    def same_origin(self):
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.json_out(403, {'error': '请求来源无效'})
            return False
        return True

    def do_POST(self):
        if not self.same_origin():
            return
        if self.path == '/api/posts':
            return self.create_post()
        if self.path == '/api/models':
            return self.create_model()
        if self.path != '/api/jobs':
            return self.json_out(404, {'error': '接口不存在'})
        visitor = self.session()
        api_key, uuap_id = credentials()
        if not api_key:
            return self.json_out(503, {'error': '图片服务未配置'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > MAX_BODY:
                raise ValueError('请求图片过大')
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValueError('请求数据无效') from None
            if not isinstance(payload, dict):
                raise ValueError('请求数据无效')
            idem = payload.get('idempotencyKey')
            model = payload.get('model')
            workflow_type = payload.get('workflowType', 'tryon')
            workflow_config = payload.get('workflowConfig')

            if not isinstance(idem, str) or not re.fullmatch(r'[a-f0-9-]{36}', idem):
                raise ValueError('请求编号无效')

            if workflow_type == 'pose_variation':
                if workflow_config and not isinstance(workflow_config, dict):
                    raise ValueError('工作流配置无效')
                model = model or 'female'
            elif workflow_type == 'background_change':
                if workflow_config and not isinstance(workflow_config, dict):
                    raise ValueError('工作流配置无效')
                scene_type = (workflow_config or {}).get('scene_type', 'white')
                valid_scenes = ['white', 'studio_gray', 'outdoor_street', 'indoor_minimal', 'beach', 'cafe']
                if scene_type not in valid_scenes:
                    raise ValueError(f'场景类型无效，支持：{", ".join(valid_scenes)}')
                model = model or 'female'
            elif workflow_type == 'product_retouch':
                if workflow_config and not isinstance(workflow_config, dict):
                    raise ValueError('工作流配置无效')
                mode = (workflow_config or {}).get('mode', 'faithful-retouch')
                valid_modes = ['faithful-retouch', 'marketplace-white', 'studio-polish']
                if mode not in valid_modes:
                    raise ValueError(f'精修模式无效，支持：{", ".join(valid_modes)}')
                model = model or 'female'
            elif workflow_type == 'material_enhance':
                if workflow_config and not isinstance(workflow_config, dict):
                    raise ValueError('工作流配置无效')
                material_type = (workflow_config or {}).get('material_type', 'cotton')
                valid_materials = ['silk', 'denim', 'leather', 'knit', 'cotton', 'wool']
                if material_type not in valid_materials:
                    raise ValueError(f'材质类型无效，支持：{", ".join(valid_materials)}')
                model = model or 'female'
            elif workflow_type == 'outfit_fusion':
                if not workflow_config or not isinstance(workflow_config, dict):
                    raise ValueError('outfit_fusion 需要配置 items')
                items = workflow_config.get('items', [])
                if not isinstance(items, list) or len(items) < 2:
                    raise ValueError('outfit_fusion 需要至少2件商品')
                model = model or 'female'
            elif workflow_type == 'product_set':
                if workflow_config and not isinstance(workflow_config, dict):
                    raise ValueError('工作流配置无效')
                angles = (workflow_config or {}).get('angles', ['front', 'side', 'back', 'detail'])
                if not isinstance(angles, list) or len(angles) < 2:
                    raise ValueError('套图需要至少2个角度')
                valid_angles = ['front', 'side', 'back', 'detail']
                for angle in angles:
                    if angle not in valid_angles:
                        raise ValueError(f'角度无效，支持：{", ".join(valid_angles)}')
                model = model or 'female'
            elif workflow_type == 'image_translation':
                if not workflow_config or not isinstance(workflow_config, dict):
                    raise ValueError('image_translation 需要配置')
                translation_type = workflow_config.get('translation_type')
                source_style = workflow_config.get('source_style')
                target_style = workflow_config.get('target_style')
                if not translation_type or not source_style or not target_style:
                    raise ValueError('image_translation 需要 translation_type, source_style, target_style')
                valid_types = ['season', 'scene', 'style', 'time']
                if translation_type not in valid_types:
                    raise ValueError(f'翻译类型无效，支持：{", ".join(valid_types)}')
                model = model or 'female'
            else:
                if model not in ('female', 'male'):
                    raise ValueError('请选择模特')

            if not isinstance(payload.get('image'), str):
                raise ValueError('请上传商品图片')
            with connect() as db:
                previous = db.execute('SELECT * FROM jobs WHERE visitor=? AND idem=?', (visitor, idem)).fetchone()
            if previous:
                return self.json_out(200, {'job': public_job(previous)})
            image = parse_image(payload['image'])
            job_id = uuid4().hex
            timestamp = now()
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM jobs WHERE visitor=? AND idem=?', (visitor, idem)).fetchone()
                if existing:
                    count = db.execute("SELECT COUNT(*) FROM jobs WHERE visitor=? AND status IN ('queued','running')", (visitor,)).fetchone()[0]
                    return self.json_out(200, {'job': public_job(existing), 'queueCount': count})
                count = db.execute("SELECT COUNT(*) FROM jobs WHERE visitor=? AND status IN ('queued','running')", (visitor,)).fetchone()[0]
                if count >= 10:
                    return self.json_out(429, {'error': f'排队任务已达上限（{count}/10），请等待完成后再提交', 'queueCount': count})
                cursor = db.execute('INSERT OR IGNORE INTO jobs (id,visitor,idem,model,status,created,updated,workflow_type,workflow_config) VALUES (?,?,?,?,?,?,?,?,?)',
                           (job_id, visitor, idem, model, 'queued', timestamp, timestamp, workflow_type, json.dumps(workflow_config) if workflow_config else None))
                if cursor.rowcount == 0:
                    previous = db.execute('SELECT * FROM jobs WHERE visitor=? AND idem=?', (visitor, idem)).fetchone()
                    count = db.execute("SELECT COUNT(*) FROM jobs WHERE visitor=? AND status IN ('queued','running')", (visitor,)).fetchone()[0]
                    return self.json_out(200, {'job': public_job(previous), 'queueCount': count})
                count += 1
            try:
                data_path(job_id, 'input').write_bytes(image)
            except OSError:
                update_job(job_id, status='failed', error='图片保存失败，请重试')
                return self.json_out(500, {'error': '图片保存失败，请重试'})
            threading.Thread(target=generate, args=(job_id, model, workflow_type, workflow_config), daemon=True).start()
            return self.json_out(202, {'job': public_job({'id': job_id, 'model': model, 'status': 'queued', 'created': timestamp, 'error': None}), 'queueCount': count})
        except (ValueError, json.JSONDecodeError) as exc:
            return self.json_out(400, {'error': str(exc)})
        except Exception as exc:
            print(f'create failure={type(exc).__name__}')
            return self.json_out(500, {'error': '任务创建失败'})

    def create_post(self):
        visitor = self.session()
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 4096:
                raise ValueError('发布内容过长')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('发布内容无效')
            post_id = payload.get('jobId')
            if not isinstance(post_id, str) or not re.fullmatch(r'[a-f0-9]{32}', post_id):
                raise ValueError('作品编号无效')
            fields = []
            for key, maximum, fallback in [('nickname', 20, '衣拍访客'), ('productName', 30, ''), ('note', 300, '')]:
                value = payload.get(key, fallback)
                if not isinstance(value, str) or len(value.strip()) > maximum:
                    raise ValueError('发布内容过长')
                fields.append(value.strip() or fallback)
            nickname, product_name, note = fields
            if not product_name or not note:
                raise ValueError('请填写商品和使用心得')
            with connect() as db:
                job = db.execute('SELECT status FROM jobs WHERE id=? AND visitor=?', (post_id, visitor)).fetchone()
                if not job or job['status'] != 'succeeded':
                    return self.json_out(404, {'error': '作品不存在或尚未完成'})
                existing = db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
                if existing:
                    return self.json_out(200, {'post': public_post(existing, visitor)})
                for kind in ('input', 'result'):
                    shutil.copyfile(data_path(post_id, kind), post_path(post_id, kind))
                db.execute('INSERT INTO posts VALUES (?,?,?,?,?,?)',
                           (post_id, visitor, nickname, product_name, note, now()))
                row = db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
            return self.json_out(201, {'post': public_post(row, visitor)})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return self.json_out(400, {'error': '发布内容无效，请检查后重试'})
        except (OSError, sqlite3.Error) as exc:
            print(f'post create failure={type(exc).__name__}')
            return self.json_out(500, {'error': '发布失败，请重试'})

    def create_model(self):
        visitor = self.session()
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > MAX_BODY:
                raise ValueError('上传内容过大')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('上传内容无效')
            name = payload.get('name', '').strip()
            if not name or len(name) > 20:
                raise ValueError('模特名称为1-20字符')
            gender = payload.get('gender', '').strip()
            if gender not in ('male', 'female'):
                raise ValueError('性别必须是male或female')
            image_data = payload.get('image')
            if not isinstance(image_data, str):
                raise ValueError('请上传模特图片')
            image = parse_image(image_data)
            model_id = hashlib.md5((visitor + name + str(len(image))).encode()).hexdigest()
            timestamp = now()
            with connect() as db:
                existing = db.execute('SELECT * FROM models WHERE id=?', (model_id,)).fetchone()
                if existing:
                    return self.json_out(200, {'model': {'id': existing['id'], 'name': existing['name'], 'gender': existing['gender'], 'image': f'/api/models/{existing["id"]}/image', 'isPreset': bool(existing['is_preset'])}})
                custom_count = db.execute('SELECT COUNT(*) FROM models WHERE visitor=? AND is_preset=0', (visitor,)).fetchone()[0]
                if custom_count >= 20:
                    return self.json_out(429, {'error': '自定义模特数量已达上限（20个）'})
                db.execute('INSERT INTO models (id,name,gender,image_path,is_preset,visitor,sort_order,created) VALUES (?,?,?,?,?,?,?,?)',
                           (model_id, name, gender, str(model_path(model_id)), 0, visitor, 0, timestamp))
            try:
                model_path(model_id).write_bytes(image)
            except OSError:
                with connect() as db:
                    db.execute('DELETE FROM models WHERE id=?', (model_id,))
                return self.json_out(500, {'error': '模特图片保存失败，请重试'})
            return self.json_out(201, {'model': {'id': model_id, 'name': name, 'gender': gender, 'image': f'/api/models/{model_id}/image', 'isPreset': False}})
        except (ValueError, json.JSONDecodeError) as exc:
            return self.json_out(400, {'error': str(exc)})
        except Exception as exc:
            print(f'model create failure={type(exc).__name__}')
            return self.json_out(500, {'error': '模特创建失败'})

    def do_DELETE(self):
        if not self.same_origin():
            return
        model_match = re.fullmatch(r'/api/models/([a-f0-9]{32})', self.path)
        if model_match:
            visitor = self.session()
            model_id = model_match.group(1)
            with connect() as db:
                row = db.execute('SELECT * FROM models WHERE id=?', (model_id,)).fetchone()
                if not row:
                    return self.json_out(404, {'error': '模特不存在'})
                if row['is_preset']:
                    return self.json_out(403, {'error': '预设模特不能删除'})
                if row['visitor'] != visitor:
                    return self.json_out(403, {'error': '无权删除该模特'})
                db.execute('DELETE FROM models WHERE id=? AND visitor=?', (model_id, visitor))
            model_path(model_id).unlink(missing_ok=True)
            return self.json_out(200, {'deleted': True})
        post_match = re.fullmatch(r'/api/posts/([a-f0-9]{32})', self.path)
        if post_match:
            visitor = self.session()
            post_id = post_match.group(1)
            with connect() as db:
                row = db.execute('SELECT id FROM posts WHERE id=? AND visitor=?', (post_id, visitor)).fetchone()
                if not row:
                    return self.json_out(404, {'error': '社区作品不存在'})
                db.execute('DELETE FROM posts WHERE id=? AND visitor=?', (post_id, visitor))
            for kind in ('input', 'result'):
                post_path(post_id, kind).unlink(missing_ok=True)
            return self.json_out(200, {'deleted': True})
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})', self.path)
        if not match:
            return self.json_out(404, {'error': '接口不存在'})
        visitor = self.session()
        job_id = match.group(1)
        with connect() as db:
            row = db.execute('SELECT status FROM jobs WHERE id=? AND visitor=?', (job_id, visitor)).fetchone()
            if not row:
                return self.json_out(404, {'error': '作品不存在'})
            if row['status'] in ('queued', 'running'):
                return self.json_out(409, {'error': '图片生成中，暂时无法删除'})
            db.execute('DELETE FROM jobs WHERE id=? AND visitor=?', (job_id, visitor))
        for kind in ('input', 'result'):
            data_path(job_id, kind).unlink(missing_ok=True)
        return self.json_out(200, {'deleted': True})


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('YIPAI_PORT', '8000'))
    print(f'衣拍服务启动：http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
