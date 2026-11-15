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
import sys
import threading
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.workflows.background_change import build_background_change_prompt
from backend.workflows.pose_variation import build_pose_variation_prompt
from backend.workflows.retouch import build_product_retouch_prompt, build_material_enhancement_prompt
from backend.workflows.fusion import build_outfit_fusion_prompt, build_product_set_prompt
from backend.workflows.translation import build_image_translation_prompt
from backend.workflows.tryon import (
    GARMENT_ROLES, MAX_TRYON_INPUTS, MAX_TRYON_OUTPUTS, build_tryon_prompt, build_tryon_identity_prompt,
    normalize_tryon_config, ordered_tryon_inputs, validate_tryon_roles,
)
from backend.workflows.remake import (
    ANALYSIS_INSTRUCTION, REMAKE_COUNT, MAX_REMAKE_OUTPUTS, build_remake_prompt,
    build_role_remake_prompt, direct_reference_analysis, normalize_remake_config, parse_analysis,
)

STATIC = ROOT / 'mockup'
DATA = Path(os.environ.get('YIPAI_DATA_DIR', str(ROOT / 'backend' / 'data')))
DB = DATA / 'jobs.sqlite3'
GATEWAY = 'https://ai-force.duxiaoman-int.com/v1/responses'
IMAGE_MODEL = 'gpt-image-2.5-sunburst'
ANALYZE_BASE_URL = 'http://z.duxiaoman-int.com/coding/v1'
ANALYZE_MODEL = 'gpt-6.1-sol'
MAX_INPUT = 20 * 1024 * 1024
MAX_BODY = 30 * 1024 * 1024
MAX_OUTPUT = 40 * 1024 * 1024
SLOTS = threading.BoundedSemaphore(2)
Image.MAX_IMAGE_PIXELS = 30_000_000


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_setting(name: str) -> str | None:
    """Environment variables win over .env.local."""
    if os.environ.get(name):
        return os.environ[name]
    source = Path(os.environ.get('IMAGE2_ENV_FILE', str(ROOT / '.env.local')))
    if source.is_file():
        for line in source.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                if key.strip() == name:
                    return value.strip().strip('"\'') or None
    return None


def credentials() -> tuple[str | None, str | None]:
    return env_setting('IMAGE2_GATEWAY_API_KEY'), env_setting('IMAGE2_UUAP_ID')


def analysis_credentials() -> tuple[str | None, str, str]:
    """拍同款 reads the reference photo with a vision model on a separate gateway."""
    return (env_setting('ANALYZE_API_KEY'),
            env_setting('ANALYZE_BASE_URL') or ANALYZE_BASE_URL,
            env_setting('ANALYZE_MODEL') or ANALYZE_MODEL)


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
        if 'preview_only' not in columns:
            db.execute('ALTER TABLE jobs ADD COLUMN preview_only INTEGER NOT NULL DEFAULT 0')

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
        # One row per visitor and kind: like (好看), save (收藏), remake (拍同款 used it as a reference).
        db.execute('''CREATE TABLE IF NOT EXISTS post_reactions (
            post_id TEXT NOT NULL, visitor TEXT NOT NULL, kind TEXT NOT NULL, created TEXT NOT NULL,
            PRIMARY KEY (post_id, visitor, kind))''')
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


def migrate_pose_results():
    """Split already-generated pose sheets so old jobs also expose separate photos."""
    with connect() as db:
        rows = db.execute("SELECT id, workflow_config FROM jobs WHERE workflow_type='pose_variation' AND status='succeeded'").fetchall()
    for row in rows:
        try:
            count = json.loads(row['workflow_config'] or '{}').get('pose_count', 4)
            if count not in (4, 6, 8):
                continue
            destinations = [data_path(row['id'], f'result-{index}') for index in range(1, count + 1)]
            if all(path.is_file() for path in destinations):
                continue
            source = data_path(row['id'], 'result')
            if not source.is_file():
                continue
            columns, rows_count = (2, 2) if count == 4 else (2, 3) if count == 6 else (3, 3)
            with Image.open(source) as image:
                image = image.convert('RGB')
                for index, destination in enumerate(destinations):
                    column, row_index = index % columns, index // columns
                    left, right = round(column * image.width / columns), round((column + 1) * image.width / columns)
                    top, bottom = round(row_index * image.height / rows_count), round((row_index + 1) * image.height / rows_count)
                    tile = image.crop((left, top, right, bottom))
                    if column:
                        tile = tile.crop((3, 0, tile.width, tile.height))
                    if column < columns - 1:
                        tile = tile.crop((0, 0, tile.width - 3, tile.height))
                    if row_index:
                        tile = tile.crop((0, 3, tile.width, tile.height))
                    if row_index < rows_count - 1:
                        tile = tile.crop((0, 0, tile.width, tile.height - 3))
                    encoded = BytesIO()
                    tile.save(encoded, 'JPEG', quality=92)
                    temporary = destination.with_suffix('.tmp')
                    temporary.write_bytes(watermark(encoded.getvalue()))
                    temporary.replace(destination)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            print(f'Pose result migration failed job={row["id"]}')


def data_path(job_id: str, kind: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise ValueError('任务编号无效')
    return DATA / f'{job_id}.{kind}.jpg'


def analysis_path(job_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise ValueError('任务编号无效')
    return DATA / f'{job_id}.analysis.json'


def post_path(post_id: str, kind: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', post_id) or kind not in ('input', 'result'):
        raise ValueError('作品编号无效')
    return DATA / f'post-{post_id}.{kind}.jpg'


def model_path(model_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', model_id):
        raise ValueError('模特编号无效')
    return DATA / f'model-{model_id}.jpg'


REACTIONS = {'like': 'likes', 'save': 'saves', 'remake': 'remakes'}


def reaction_stats(db, post_ids, visitor: str) -> dict:
    stats = {post_id: {'likes': 0, 'saves': 0, 'remakes': 0, 'liked': False, 'saved': False} for post_id in post_ids}
    if not stats:
        return stats
    marks = ','.join('?' * len(stats))
    for row in db.execute(f'SELECT post_id, kind, COUNT(*) AS total, SUM(visitor=?) AS own FROM post_reactions '
                          f'WHERE post_id IN ({marks}) GROUP BY post_id, kind', (visitor, *stats)):
        if row['kind'] not in REACTIONS:
            continue
        item = stats[row['post_id']]
        item[REACTIONS[row['kind']]] = row['total']
        if row['kind'] in ('like', 'save'):
            item['liked' if row['kind'] == 'like' else 'saved'] = bool(row['own'])
    return stats


def public_post(row, visitor: str, stats: dict | None = None):
    post_id = row['id']
    return {
        'id': post_id, 'nickname': row['nickname'],
        'productName': row['product_name'], 'note': row['note'],
        'created': row['created'], 'mine': row['visitor'] == visitor,
        'image': f'/api/posts/{post_id}/result',
        'productImage': f'/api/posts/{post_id}/input',
        **(stats or {'likes': 0, 'saves': 0, 'remakes': 0, 'liked': False, 'saved': False}),
    }


def job_posts(db, job_ids, visitor: str) -> dict:
    """Publish details for the visitor's own jobs; a post shares its job's id."""
    ids = list(job_ids)
    if not ids:
        return {}
    rows = db.execute(f'SELECT * FROM posts WHERE visitor=? AND id IN ({",".join("?" * len(ids))})', (visitor, *ids)).fetchall()
    stats = reaction_stats(db, [row['id'] for row in rows], visitor)
    return {row['id']: {'productName': row['product_name'], 'note': row['note'], 'created': row['created'],
                        **{key: stats[row['id']][key] for key in ('likes', 'saves', 'remakes')}} for row in rows}


def delete_post_rows(db, post_id: str):
    db.execute('DELETE FROM posts WHERE id=?', (post_id,))
    db.execute('DELETE FROM post_reactions WHERE post_id=?', (post_id,))


def parse_image(data_url: str, min_dimension: int = 512) -> bytes:
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
    if min(image.size) < min_dimension:
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
    return build_tryon_prompt(model, [{'role': 'auto'}, {'role': 'model'}], normalize_tryon_config(None))


def prepare_tryon_inputs(payload, visitor, workflow_type='tryon'):
    """Normalize uploads and snapshot library identities before starting a job."""
    explicit = 'inputImages' in payload
    config = (normalize_remake_config(payload.get('workflowConfig')) if workflow_type == 'remake'
              else normalize_tryon_config(payload.get('workflowConfig'), explicit))
    supplied = payload.get('inputImages')
    if explicit:
        validate_tryon_roles(supplied, config['clothing_mode'])
    else:
        if not isinstance(payload.get('image'), str):
            raise ValueError('请上传商品图片')
        # Old callers can submit shoes and individual garments without choosing a slot.
        role = 'single' if config['clothing_mode'] == 'single' else 'auto'
        if config['clothing_mode'] == 'multi':
            raise ValueError('换上下装需要指定商品图片角色')
        supplied = [{'role': role, 'image': payload['image']}]
    model_id = payload.get('modelId')
    if model_id is not None and (not isinstance(model_id, str) or not re.fullmatch(r'[a-f0-9]{32}', model_id)):
        raise ValueError('模特编号无效')
    if model_id and any(item['role'] == 'model' for item in supplied):
        raise ValueError('上传模特图和模特库不能同时选择')
    if workflow_type == 'remake' and config['model_source'] == 'work' and (
            model_id or any(item['role'] == 'model' for item in supplied)):
        raise ValueError('沿用作品人物时不能另选模特')
    inputs = []
    total = 0
    for item in supplied:
        minimum = 128 if item['role'] == 'detail' else 400 if item['role'] in ('reference', 'model') else 256
        image = parse_image(item['image'], min_dimension=minimum)
        encoded = item['image'].partition(',')[2]
        total += len(encoded) * 3 // 4 - (len(encoded) - len(encoded.rstrip('=')))
        if total > MAX_INPUT:
            raise ValueError('所有输入图片合计不能超过 20 MB')
        normalized = {'role': item['role'], 'bytes': image}
        if item['role'] == 'detail':
            normalized['garmentRole'] = item['garmentRole']
        inputs.append(normalized)
    if model_id:
        with connect() as db:
            row = db.execute('SELECT * FROM models WHERE id=? AND (is_preset=1 OR visitor=?)', (model_id, visitor)).fetchone()
        if not row or not model_path(model_id).is_file():
            raise ValueError('所选模特不存在或无权访问')
        inputs.append({'role': 'model', 'bytes': model_path(model_id).read_bytes()})
    elif not any(item['role'] == 'model' for item in inputs) and (
            (workflow_type == 'remake' and config['model_source'] != 'work')
            or (workflow_type == 'tryon' and not any(item['role'] == 'reference' for item in inputs))):
        default = STATIC / 'assets' / f'{payload.get("model") or "female"}-model.png'
        if not default.is_file():
            raise ValueError('模特参考图缺失')
        inputs.append({'role': 'model', 'bytes': parse_image('data:image/png;base64,' + base64.b64encode(default.read_bytes()).decode('ascii'), min_dimension=400)})
    if len(inputs) > MAX_TRYON_INPUTS:
        raise ValueError('试穿输入图片数量无效')
    if sum(len(item['bytes']) for item in inputs) > MAX_INPUT:
        raise ValueError('所有输入图片合计不能超过 20 MB')
    return config, inputs


def tryon_job_inputs(job_id):
    with connect() as db:
        row = db.execute('SELECT input_images FROM jobs WHERE id=?', (job_id,)).fetchone()
    descriptors = json.loads(row['input_images']) if row and row['input_images'] else []
    inputs = []
    for item in descriptors:
        match = re.fullmatch(rf'/api/jobs/{job_id}/(input-([1-9]|1[0-5]))', item.get('url', ''))
        if not match:
            raise RuntimeError('试穿输入图片缺失')
        inputs.append({**item, 'bytes': data_path(job_id, match.group(1)).read_bytes()})
    return inputs


def watermark_font(size: int):
    # PingFang moved into downloadable assets on newer macOS; fall back to fonts that ship with the system.
    candidates = [os.environ.get('YIPAI_WATERMARK_FONT'),
                  '/System/Library/Fonts/PingFang.ttc',
                  *sorted(str(path) for path in Path('/System/Library/AssetsV2').glob('com_apple_MobileAsset_Font*/*/AssetData/PingFang.ttc')),
                  '/System/Library/Fonts/Hiragino Sans GB.ttc',
                  '/System/Library/Fonts/STHeiti Medium.ttc',
                  '/Library/Fonts/Arial Unicode.ttf',
                  '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                  '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc']
    for candidate in candidates:
        if candidate:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return None


def watermark(raw: bytes) -> bytes:
    image = Image.open(BytesIO(raw)).convert('RGBA')
    # Render the brand lockup at 3x, then scale it with the image's shorter side.
    unit = 3
    font = watermark_font(18 * unit)
    if font:
        brand, label = '衣拍', 'AI 生成'
    else:
        # The built-in font has no CJK glyphs.
        brand, label = 'YIPAI', 'AI GENERATED'
        font = ImageFont.load_default(size=18 * unit)
    measure = ImageDraw.Draw(image)
    brand_box = measure.textbbox((0, 0), brand, font=font)
    label_box = measure.textbbox((0, 0), label, font=font)
    brand_width = brand_box[2] - brand_box[0]
    label_width = label_box[2] - label_box[0]
    icon_size, gap = 24 * unit, 8 * unit
    height = 40 * unit
    brand_x = icon_size + gap
    divider_x = brand_x + brand_width + 10 * unit
    label_x = divider_x + 10 * unit
    width = label_x + label_width
    badge = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(badge)
    with Image.open(STATIC / 'assets' / 'yipai-symbol-dark.png') as source:
        symbol = source.convert('RGBA')
        symbol = ImageOps.contain(symbol.crop(symbol.getbbox()), (icon_size, icon_size), Image.Resampling.LANCZOS)
        symbol.putalpha(symbol.getchannel('A').point(lambda alpha: alpha * 220 // 255))
    badge.alpha_composite(symbol, ((icon_size - symbol.width) // 2, (height - symbol.height) // 2))
    draw.text((brand_x - brand_box[0], (height - brand_box[1] - brand_box[3]) // 2),
              brand, fill=(255, 255, 255, 220), font=font)
    draw.line((divider_x, 14 * unit, divider_x, 26 * unit), fill=(255, 255, 255, 110), width=unit)
    draw.text((label_x - label_box[0], (height - label_box[1] - label_box[3]) // 2),
              label, fill=(255, 255, 255, 220), font=font)
    scale = min(image.size) / (900 * unit)
    badge = badge.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS)
    margin = max(1, round(min(image.size) * 0.026))
    image.alpha_composite(badge, (image.width - badge.width - margin, image.height - badge.height - margin))
    result = BytesIO()
    image.convert('RGB').save(result, 'JPEG', quality=92)
    return result.getvalue()


def update_job(job_id: str, **fields):
    fields['updated'] = now()
    with connect() as db:
        names = list(fields)
        db.execute('UPDATE jobs SET ' + ', '.join(f'{name}=?' for name in names) + ' WHERE id=?', [fields[name] for name in names] + [job_id])


def request_image(prompt_text: str, images: list[str], size: str, api_key: str,
                  uuap_id: str | None, request_id: str) -> bytes:
    body = {
        'model': IMAGE_MODEL,
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
    return watermark(extract_output(json.loads(response_raw)))


def request_analysis(reference: bytes, product: bytes | list[dict], request_id: str) -> dict:
    """Ask the vision model to read the reference photo's shooting plan. The gateway only answers streamed requests."""
    api_key, base_url, model = analysis_credentials()
    if not api_key:
        raise RuntimeError('反推服务未配置')
    products = product if isinstance(product, list) else [{'role': 'auto', 'bytes': product}]
    instruction = ANALYSIS_INSTRUCTION
    if len(products) > 1:
        labels = {'upper': '上装商品', 'lower': '下装商品', 'single': '连体商品', 'auto': '目标商品'}
        instruction += '\n本次需要同时展示多件商品：' + '；'.join(
            f'图{index}是{labels[item["role"]]}' for index, item in enumerate(products, 2)
        ) + '。product_note 与每条拍摄方案必须兼顾所有商品，不可只展示第一件；product_box 仅对应图2。'
    content = [{'type': 'input_text', 'text': instruction},
               {'type': 'input_image', 'image_url': image_data_url(reference)}]
    content.extend({'type': 'input_image', 'image_url': image_data_url(item['bytes'])} for item in products)
    body = {'model': model, 'stream': True, 'input': [{'role': 'user', 'content': content}]}
    request = Request(base_url.rstrip('/') + '/responses', data=json.dumps(body).encode('utf-8'), method='POST',
                      headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json',
                               'Accept': 'text/event-stream', 'request-id': request_id})
    deltas, final = [], ''
    with urlopen(request, timeout=300) as response:
        for raw_line in response:
            line = raw_line.decode('utf-8', 'replace').strip()
            if not line.startswith('data:') or line == 'data: [DONE]':
                continue
            event = json.loads(line[5:])
            kind = event.get('type')
            if kind == 'response.output_text.delta':
                deltas.append(event.get('delta') or '')
            elif kind == 'response.output_text.done':
                final = event.get('text') or final
            elif kind in ('error', 'response.failed'):
                raise RuntimeError('反推服务返回错误')
    return parse_analysis(final or ''.join(deltas))


def crop_box(raw: bytes, box) -> bytes:
    """Crop to the photo region the analysis found, so app chrome never reaches image generation."""
    if not box or box == [0, 0, 1000, 1000]:
        return raw
    with Image.open(BytesIO(raw)) as image:
        image = image.convert('RGB')
        left, top, right, bottom = (round(value * size / 1000) for value, size in zip(box, (image.width, image.height, image.width, image.height)))
        cropped = image.crop((left, top, right, bottom))
        if min(cropped.size) < 256:
            return raw
        output = BytesIO()
        cropped.save(output, 'JPEG', quality=92)
        return output.getvalue()


def remake_analysis(reference, products, request_id):
    try:
        return request_analysis(reference, products, request_id)
    except RuntimeError as exc:
        if str(exc) != '反推服务未配置':
            raise
        # Keep uploads on the configured image provider; its multimodal editor can read the reference directly.
        return direct_reference_analysis()


def generate_remake(job_id: str, workflow_config: dict, api_key: str, uuap_id: str | None, request_id: str, inputs):
    if inputs:
        config = normalize_remake_config(workflow_config)
        references = [item for item in inputs if item['role'] == 'reference'] or [None]
        garments = [item for item in inputs if item['role'] in (*GARMENT_ROLES, 'auto')]
        stored = analysis_path(job_id)
        cached = json.loads(stored.read_text(encoding='utf-8')) if references[0] and stored.is_file() else {}
        analyses = cached.get('references', []) if isinstance(cached, dict) else []
        for group, reference in enumerate(references):
            analysis = None
            if reference:
                if len(analyses) <= group:
                    analyses.append(remake_analysis(reference['bytes'], garments, f'{request_id}-analysis-{group + 1}'))
                    temporary = stored.with_suffix('.tmp')
                    temporary.write_text(json.dumps({'references': analyses}, ensure_ascii=False), encoding='utf-8')
                    temporary.replace(stored)
                analysis = analyses[group]
            ordered = ordered_tryon_inputs(inputs, reference)
            cropped = [{**item, 'bytes': crop_box(item['bytes'], analysis.get('reference_box'))}
                       if item['role'] == 'reference' else
                       {**item, 'bytes': crop_box(item['bytes'], analysis.get('product_box'))}
                       if item is garments[0] else item for item in ordered] if analysis else ordered
            images = [image_data_url(item['bytes']) for item in cropped]
            identity = next((item for item in ordered if item['role'] == 'model'), None)
            for candidate in range(config['output_count']):
                output_index = group * config['output_count'] + candidate + 1
                destination = data_path(job_id, f'result-{output_index}')
                if destination.is_file():
                    continue
                result = request_image(build_role_remake_prompt(model=workflow_config.get('model', 'female'),
                                       inputs=ordered, config=config, analysis=analysis, index=candidate),
                                       images, '1024x1536', api_key, uuap_id, f'{request_id}-{output_index}')
                if reference and identity:
                    result = request_image(build_tryon_identity_prompt(),
                                           [image_data_url(result), image_data_url(identity['bytes'])],
                                           '1024x1536', api_key, uuap_id, f'{request_id}-{output_index}-identity')
                temporary = destination.with_suffix('.tmp')
                temporary.write_bytes(result)
                temporary.replace(destination)
                if output_index == 1:
                    shutil.copyfile(destination, data_path(job_id, 'result'))
                update_job(job_id)
                print(f'Image2 request={request_id} remake={output_index}/{len(references) * config["output_count"]} status=success')
        return
    product = data_path(job_id, 'input').read_bytes()
    reference = data_path(job_id, 'reference').read_bytes()
    keep_model = workflow_config.get('model_source') == 'work'
    stored = analysis_path(job_id)
    if stored.is_file():
        # Regenerating reuses the earlier analysis so the three photos keep the same plan.
        analysis = json.loads(stored.read_text(encoding='utf-8'))
    else:
        analysis = remake_analysis(reference, product, f'{request_id}-analysis')
        stored.write_text(json.dumps(analysis, ensure_ascii=False), encoding='utf-8')
        print(f'Remake request={request_id} plan={analysis.get("_source", "vision-analysis")} status=success')
    images = [image_data_url(crop_box(product, analysis.get('product_box')))]
    if not keep_model:
        model_file = STATIC / 'assets' / f'{workflow_config.get("model", "female")}-model.png'
        if not model_file.is_file():
            raise RuntimeError('模特参考图缺失')
        images.append('data:image/png;base64,' + base64.b64encode(model_file.read_bytes()).decode('ascii'))
    images.append(image_data_url(crop_box(reference, analysis.get('reference_box'))))
    for index in range(REMAKE_COUNT):
        destination = data_path(job_id, f'result-{index + 1}')
        if destination.is_file():
            continue
        result = request_image(build_remake_prompt(analysis, index, keep_model), images, '1024x1536',
                               api_key, uuap_id, f'{request_id}-{index + 1}')
        temporary = destination.with_suffix('.tmp')
        temporary.write_bytes(result)
        temporary.replace(destination)
        if index == 0:
            shutil.copyfile(destination, data_path(job_id, 'result'))
        update_job(job_id)
        print(f'Image2 request={request_id} remake={index + 1}/{REMAKE_COUNT} status=success')


def generate(job_id: str, model: str, workflow_type: str = 'tryon', workflow_config: dict | None = None):
    with SLOTS:
        request_id = str(uuid4())
        remake_has_reference = False
        try:
            api_key, uuap_id = credentials()
            if not api_key:
                raise RuntimeError('图片服务未配置')

            update_job(job_id, status='running', request_id=request_id)

            if workflow_type == 'tryon':
                config = normalize_tryon_config(workflow_config)
                inputs = tryon_job_inputs(job_id)
                if not inputs:
                    model_file = STATIC / 'assets' / f'{model}-model.png'
                    if not model_file.is_file():
                        raise RuntimeError('模特参考图缺失')
                    inputs = [{'role': 'auto', 'bytes': data_path(job_id, 'input').read_bytes()},
                              {'role': 'model', 'bytes': parse_image('data:image/png;base64,' + base64.b64encode(model_file.read_bytes()).decode('ascii'), min_dimension=400)}]
                references = [item for item in inputs if item['role'] == 'reference'] or [None]
                output_index = 0
                for reference in references:
                    ordered = ordered_tryon_inputs(inputs, reference)
                    images = [image_data_url(item['bytes']) for item in ordered]
                    for candidate in range(config['output_count']):
                        prompt_text = build_tryon_prompt(model, ordered, config, candidate)
                        output_index += 1
                        result = request_image(prompt_text, images, '1024x1536', api_key, uuap_id, f'{request_id}-{output_index}')
                        identity = next((item for item in ordered if item['role'] == 'model'), None)
                        if reference and identity:
                            result = request_image(
                                build_tryon_identity_prompt(),
                                [image_data_url(result), image_data_url(identity['bytes'])],
                                '1024x1536', api_key, uuap_id, f'{request_id}-{output_index}-identity',
                            )
                        destination = data_path(job_id, f'result-{output_index}')
                        temporary = destination.with_suffix('.tmp')
                        temporary.write_bytes(result)
                        temporary.replace(destination)
                        if output_index == 1:
                            shutil.copyfile(destination, data_path(job_id, 'result'))
                        update_job(job_id)
                        print(f'Image2 request={request_id} output={output_index}/{len(references) * config["output_count"]} status=success')
                update_job(job_id, status='succeeded')
                return
            elif workflow_type == 'pose_variation':
                pose_count = (workflow_config or {}).get('pose_count', 4)
                if type(pose_count) is not int or pose_count not in (4, 6, 8):
                    pose_count = 4

                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                for index in range(pose_count):
                    prompt_text = build_pose_variation_prompt(pose_count, index)
                    result = request_image(prompt_text, images, '1024x1536', api_key, uuap_id, f'{request_id}-{index + 1}')
                    destination = data_path(job_id, f'result-{index + 1}')
                    temporary = destination.with_suffix('.tmp')
                    temporary.write_bytes(result)
                    temporary.replace(destination)
                    if index == 0:
                        shutil.copyfile(destination, data_path(job_id, 'result'))
                    update_job(job_id)
                    print(f'Image2 request={request_id} pose={index + 1}/{pose_count} status=success')
                update_job(job_id, status='succeeded')
                return
            elif workflow_type == 'remake':
                inputs = tryon_job_inputs(job_id)
                remake_has_reference = any(item['role'] == 'reference' for item in inputs) or data_path(job_id, 'reference').is_file()
                generate_remake(job_id, workflow_config or {}, api_key, uuap_id, request_id, inputs)
                update_job(job_id, status='succeeded')
                return
            elif workflow_type == 'background_change':
                scene_type = (workflow_config or {}).get('scene_type', 'white')
                prompt_text = build_background_change_prompt(scene_type)
                images = [image_data_url(data_path(job_id, 'input').read_bytes())]
                # Scene thumbnails contain people; never send them as edit inputs.
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
                raise ValueError('工作流类型无效')

            result = request_image(prompt_text, images, size, api_key, uuap_id, request_id)
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
            if str(exc) in ('图片服务未配置', '模特参考图缺失', '反推服务未配置'):
                message = str(exc)
            elif remake_has_reference and not analysis_path(job_id).is_file():
                message = '没能看懂这张参考图，请换一张更清楚的截图'
            else:
                message = '图片生成失败，请重新生成'
            update_job(job_id, status='failed', error=message)
            print(f'Image2 request={request_id} failure={type(exc).__name__}')


def public_job(row, post: dict | None = None):
    job_id = row['id']
    result = {
        'id': job_id, 'model': row['model'], 'status': row['status'],
        'created': row['created'], 'error': row['error'],
        'original': f'/api/jobs/{job_id}/input',
        'image': f'/api/jobs/{job_id}/result' if row['status'] == 'succeeded' else None,
        'previewOnly': bool(row['preview_only']) if 'preview_only' in row.keys() else False,
        'post': post,
    }
    # Add workflow fields if they exist
    if 'workflow_type' in row.keys():
        result['workflowType'] = row['workflow_type']
    if 'workflow_config' in row.keys():
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
    if result.get('workflowType') == 'remake':
        refs = [item for item in result.get('inputImages', []) if item['role'] == 'reference']
        result['reference'] = refs[0]['url'] if refs else None
        if not result.get('inputImages'):
            result['reference'] = f'/api/jobs/{job_id}/reference'
    if result.get('workflowType') in ('tryon', 'pose_variation', 'remake'):
        maximum = MAX_REMAKE_OUTPUTS if result['workflowType'] == 'remake' else MAX_TRYON_OUTPUTS if result['workflowType'] == 'tryon' else 8
        result['images'] = [f'/api/jobs/{job_id}/result-{index}' for index in range(1, maximum + 1)
                            if data_path(job_id, f'result-{index}').is_file()]
        if result['images'] and row['status'] == 'succeeded':
            result['image'] = result['images'][0]
        elif result['image']:
            result['images'] = [result['image']]
    return result


class Handler(SimpleHTTPRequestHandler):
    generation_mode = 'live'

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

    def headers_out(self, status, content_type, size, extra_headers=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
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
            return self.json_out(200, {'ready': bool(key), 'generationMode': self.generation_mode})
        if self.path == '/api/jobs':
            visitor = self.session()
            with connect() as db:
                rows = db.execute('SELECT * FROM jobs WHERE visitor=? ORDER BY created DESC LIMIT 100', (visitor,)).fetchall()
                published = job_posts(db, [row['id'] for row in rows], visitor)
            return self.json_out(200, {'jobs': [public_job(row, published.get(row['id'])) for row in rows]})
        if self.path == '/api/posts':
            visitor = self.session()
            with connect() as db:
                rows = db.execute('SELECT * FROM posts ORDER BY created DESC LIMIT 50').fetchall()
                stats = reaction_stats(db, [row['id'] for row in rows], visitor)
            return self.json_out(200, {'posts': [public_post(row, visitor, stats[row['id']]) for row in rows]})
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
            # Only include models with actual image files
            models = []
            for row in rows:
                if model_path(row['id']).is_file():
                    models.append({'id': row['id'], 'name': row['name'], 'gender': row['gender'], 'image': f'/api/models/{row["id"]}/image', 'isPreset': bool(row['is_preset'])})
            return self.json_out(200, {'models': models})
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
                stats = reaction_stats(db, [post_id], visitor) if row else {}
            if not row:
                return self.json_out(404, {'error': '社区作品不存在'})
            if not kind:
                return self.json_out(200, {'post': public_post(row, visitor, stats[post_id])})
            path = post_path(post_id, kind)
            if not path.is_file():
                return self.json_out(404, {'error': '图片不存在'})
            raw = path.read_bytes()
            self.headers_out(200, 'image/jpeg', len(raw))
            return self.wfile.write(raw)
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})(?:/(input|reference|input-(?:[1-9]|1[0-5])|result|result-(?:[1-9]|1[0-9]|2[0-4])|download\.zip))?', self.path)
        if match:
            visitor = self.session()
            job_id, kind = match.groups()
            with connect() as db:
                row = db.execute('SELECT * FROM jobs WHERE id=? AND visitor=?', (job_id, visitor)).fetchone()
                published = job_posts(db, [job_id], visitor) if row and not kind else {}
            if not row:
                return self.json_out(404, {'error': '作品不存在'})
            if not kind:
                return self.json_out(200, {'job': public_job(row, published.get(job_id))})
            if kind != 'reference' and not kind.startswith('input') and row['status'] != 'succeeded':
                return self.json_out(404, {'error': '图片尚未生成'})
            if kind == 'download.zip':
                images = public_job(row).get('images', [])
                if not images:
                    return self.json_out(404, {'error': '没有可下载的图片'})
                archive = BytesIO()
                with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED) as bundle:
                    for index, image in enumerate(images, 1):
                        prefix = {'pose_variation': 'pose', 'tryon': 'tryon', 'remake': 'remake'}[row['workflow_type']]
                        bundle.write(data_path(job_id, image.rsplit('/', 1)[-1]), f'yipai-{prefix}-{index}.jpg')
                raw = archive.getvalue()
                self.headers_out(200, 'application/zip', len(raw), {'Content-Disposition': f'attachment; filename="yipai-{job_id}.zip"'})
                return self.wfile.write(raw)
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
        reaction_match = re.fullmatch(r'/api/posts/([a-f0-9]{32})/reactions', self.path)
        if reaction_match:
            return self.react(reaction_match.group(1))
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
                if workflow_config is not None and not isinstance(workflow_config, dict):
                    raise ValueError('工作流配置无效')
                pose_count = (workflow_config or {}).get('pose_count', 4)
                if type(pose_count) is not int or pose_count not in (4, 6, 8):
                    raise ValueError('姿势数量必须是 4、6 或 8')
                model = model or 'female'
            elif workflow_type == 'remake':
                if 'inputImages' in payload:
                    workflow_config = normalize_remake_config(workflow_config)
                    model = model or 'female'
                    if model not in ('female', 'male'):
                        raise ValueError('请选择模特性别')
                else:
                    if not isinstance(workflow_config, dict):
                        raise ValueError('工作流配置无效')
                    if workflow_config.get('model_source') not in ('preset', 'work'):
                        raise ValueError('请选择模特')
                    if workflow_config['model_source'] == 'preset' and workflow_config.get('model') not in ('female', 'male'):
                        raise ValueError('请选择模特')
                    if not isinstance(payload.get('reference'), str):
                        raise ValueError('请上传参考图')
                    workflow_config = {'model_source': workflow_config['model_source'], 'model': workflow_config.get('model') or 'female'}
                    model = workflow_config['model']
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
            elif workflow_type == 'tryon':
                model = model or 'female'
                if model not in ('female', 'male'):
                    raise ValueError('请选择模特性别')
                workflow_config = normalize_tryon_config(workflow_config, 'inputImages' in payload)
            else:
                raise ValueError('工作流类型无效')

            if not isinstance(payload.get('image'), str) and not (workflow_type in ('tryon', 'remake') and 'inputImages' in payload):
                raise ValueError('请上传商品图片')
            with connect() as db:
                previous = db.execute('SELECT * FROM jobs WHERE visitor=? AND idem=?', (visitor, idem)).fetchone()
            if previous:
                return self.json_out(200, {'job': public_job(previous)})
            prepared_inputs = []
            if workflow_type == 'tryon' or (workflow_type == 'remake' and 'inputImages' in payload):
                workflow_config, prepared_inputs = prepare_tryon_inputs(payload, visitor, workflow_type)
                if workflow_type == 'remake':
                    workflow_config['model'] = model
                image = next(item['bytes'] for item in prepared_inputs if item['role'] in (*GARMENT_ROLES, 'auto'))
            else:
                image = parse_image(payload['image'])
            reference = parse_image(payload['reference']) if workflow_type == 'remake' and not prepared_inputs else None
            job_id = uuid4().hex
            input_descriptors = []
            for index, item in enumerate(prepared_inputs, 1):
                descriptor = {'role': item['role'], 'url': f'/api/jobs/{job_id}/input-{index}'}
                if item['role'] == 'detail':
                    descriptor['garmentRole'] = item['garmentRole']
                input_descriptors.append(descriptor)
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
                cursor = db.execute('INSERT OR IGNORE INTO jobs (id,visitor,idem,model,status,created,updated,workflow_type,workflow_config,input_images,preview_only) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (job_id, visitor, idem, model, 'queued', timestamp, timestamp, workflow_type, json.dumps(workflow_config) if workflow_config else None, json.dumps(input_descriptors) if input_descriptors else None, self.generation_mode == 'demo'))
                if cursor.rowcount == 0:
                    previous = db.execute('SELECT * FROM jobs WHERE visitor=? AND idem=?', (visitor, idem)).fetchone()
                    count = db.execute("SELECT COUNT(*) FROM jobs WHERE visitor=? AND status IN ('queued','running')", (visitor,)).fetchone()[0]
                    return self.json_out(200, {'job': public_job(previous), 'queueCount': count})
                count += 1
            try:
                data_path(job_id, 'input').write_bytes(image)
                for index, item in enumerate(prepared_inputs, 1):
                    data_path(job_id, f'input-{index}').write_bytes(item['bytes'])
                if reference:
                    data_path(job_id, 'reference').write_bytes(reference)
            except OSError:
                for kind in ('input', *(f'input-{index}' for index in range(1, len(prepared_inputs) + 1))):
                    data_path(job_id, kind).unlink(missing_ok=True)
                update_job(job_id, status='failed', error='图片保存失败，请重试')
                return self.json_out(500, {'error': '图片保存失败，请重试'})
            threading.Thread(target=generate, args=(job_id, model, workflow_type, workflow_config), daemon=True).start()
            return self.json_out(202, {'job': public_job({'id': job_id, 'model': model, 'status': 'queued', 'created': timestamp, 'error': None, 'workflow_type': workflow_type, 'workflow_config': json.dumps(workflow_config) if workflow_config else None, 'input_images': json.dumps(input_descriptors) if input_descriptors else None, 'preview_only': self.generation_mode == 'demo'}), 'queueCount': count})
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
                    return self.json_out(200, {'post': public_post(existing, visitor, reaction_stats(db, [post_id], visitor)[post_id])})
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

    def react(self, post_id: str):
        visitor = self.session()
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 256:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            kind, active = payload.get('kind'), payload.get('active', True)
            if kind not in REACTIONS or not isinstance(active, bool) or (kind == 'remake' and not active):
                raise ValueError
        except (ValueError, AttributeError, json.JSONDecodeError, UnicodeDecodeError):
            return self.json_out(400, {'error': '操作无效'})
        with connect() as db:
            if not db.execute('SELECT 1 FROM posts WHERE id=?', (post_id,)).fetchone():
                return self.json_out(404, {'error': '社区作品不存在'})
            if active:
                db.execute('INSERT OR IGNORE INTO post_reactions VALUES (?,?,?,?)', (post_id, visitor, kind, now()))
            else:
                db.execute('DELETE FROM post_reactions WHERE post_id=? AND visitor=? AND kind=?', (post_id, visitor, kind))
            stats = reaction_stats(db, [post_id], visitor)[post_id]
        return self.json_out(200, {'stats': stats})

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
            image = parse_image(image_data, min_dimension=400)
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
                delete_post_rows(db, post_id)
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
            published = db.execute('SELECT 1 FROM posts WHERE id=? AND visitor=?', (job_id, visitor)).fetchone()
            if published:
                delete_post_rows(db, job_id)
        for kind in ('input', 'reference', 'result', *(f'input-{index}' for index in range(1, MAX_TRYON_INPUTS + 1)), *(f'result-{index}' for index in range(1, MAX_REMAKE_OUTPUTS + 1))):
            data_path(job_id, kind).unlink(missing_ok=True)
        analysis_path(job_id).unlink(missing_ok=True)
        if published:
            for kind in ('input', 'result'):
                post_path(job_id, kind).unlink(missing_ok=True)
        return self.json_out(200, {'deleted': True, 'postDeleted': bool(published)})


if __name__ == '__main__':
    init_db()
    migrate_pose_results()
    port = int(os.environ.get('YIPAI_PORT', '8000'))
    print(f'衣拍服务启动：http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
