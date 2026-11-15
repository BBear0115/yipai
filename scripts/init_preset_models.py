"""初始化预设模特到数据库。

将 mockup/assets/ 中的现有模特图片注册到数据库，
可选通过 Image2 生成更多多样化的预设模特。
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'mockup'
DATA = Path(os.environ.get('YIPAI_DATA_DIR', str(ROOT / 'backend' / 'data')))
DB = DATA / 'jobs.sqlite3'
GATEWAY = 'https://ai-force.duxiaoman-int.com/v1/responses'


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


def model_path(model_id: str) -> Path:
    return DATA / f'model-{model_id}.jpg'


def init_existing_models(dry_run: bool = False) -> list[dict]:
    """将 mockup/assets 中的预设模特注册到数据库。"""
    models = [
        {'id': uuid4().hex, 'name': '预设女模特', 'gender': 'female',
         'source': STATIC / 'assets' / 'female-model.png'},
        {'id': uuid4().hex, 'name': '预设男模特', 'gender': 'male',
         'source': STATIC / 'assets' / 'male-model.png'},
    ]

    registered = []
    with connect() as db:
        for model in models:
            if not model['source'].is_file():
                print(f"⚠️  {model['source']} 不存在，跳过")
                continue

            # 检查是否已存在同名预设模特
            existing = db.execute(
                'SELECT id FROM models WHERE name=? AND is_preset=1',
                (model['name'],)
            ).fetchone()

            if existing:
                print(f"✓ {model['name']} 已存在（ID: {existing['id']}）")
                registered.append({'id': existing['id'], **model})
                continue

            if dry_run:
                print(f"[Dry Run] 将注册 {model['name']}（ID: {model['id']}）")
                continue

            # 转换并保存图片为 JPEG
            dest_path = model_path(model['id'])
            img = Image.open(model['source']).convert('RGB')
            img.save(dest_path, 'JPEG', quality=92)

            # 插入数据库
            db.execute(
                'INSERT INTO models (id, name, gender, image_path, is_preset, visitor, sort_order, created) '
                'VALUES (?, ?, ?, ?, 1, NULL, ?, ?)',
                (model['id'], model['name'], model['gender'], str(dest_path), 0, now())
            )

            print(f"✓ 注册 {model['name']}（ID: {model['id']}）")
            registered.append(model)

    return registered


def generate_diverse_models(count: int = 10, dry_run: bool = False) -> list[dict]:
    """通过 Image2 生成多样化的预设模特。"""
    if type(count) is not int or count < 0:
        raise ValueError('模特数量必须是非负整数')
    prompts_file = ROOT / 'scripts' / 'model-prompts.json'
    if not prompts_file.is_file():
        print(f"⚠️  {prompts_file} 不存在，跳过生成")
        return []

    api_key, uuap_id = credentials()
    if not api_key and not dry_run:
        print("⚠️  未配置 IMAGE2_GATEWAY_API_KEY，跳过生成")
        return []

    # 定义多样化的模特配置，覆盖不同风格、年龄感和气质
    diverse_configs = [
        # 女性模特：覆盖不同年龄段、风格和气质
        {'name': '清纯甜美女模特', 'gender': 'female', 'desc': '20-23岁年轻女性',
         'style': '清新自然，邻家少女感，圆润脸型，大眼睛，黑色长直发，温柔笑容'},
        {'name': '优雅知性女模特', 'gender': 'female', 'desc': '28-32岁成熟女性',
         'style': '气质优雅，职业精英感，精致妆容，中长波浪发，自信从容的表情'},
        {'name': '酷飒个性女模特', 'gender': 'female', 'desc': '24-27岁时尚女性',
         'style': '时尚个性，酷飒帅气，利落短发或高马尾，立体五官，微带冷感的气场'},
        {'name': '健康活力女模特', 'gender': 'female', 'desc': '23-26岁运动女性',
         'style': '健康阳光，小麦肤色，运动感强，马甲线身材，充满活力的神采'},

        # 男性模特：覆盖不同年龄段、风格和气质
        {'name': '阳光少年男模特', 'gender': 'male', 'desc': '20-24岁年轻男性',
         'style': '阳光青春，清新少年感，清秀五官，短发整洁，温暖笑容'},
        {'name': '成熟稳重男模特', 'gender': 'male', 'desc': '30-35岁成熟男性',
         'style': '成熟大气，商务精英感，立体五官，短发精干，沉稳自信的气质'},
        {'name': '型格潮流男模特', 'gender': 'male', 'desc': '25-28岁潮流男性',
         'style': '时尚型男，潮流个性，个性发型，棱角分明，街头时尚感'},
        {'name': '斯文儒雅男模特', 'gender': 'male', 'desc': '26-30岁文艺男性',
         'style': '温文尔雅，书卷气质，文艺范，戴细框眼镜或不戴，温和内敛的表情'},
    ]

    # 限制生成数量
    configs_to_generate = diverse_configs[:min(count, len(diverse_configs))]

    with open(prompts_file, 'r', encoding='utf-8') as f:
        base_prompts = json.load(f)

    generated = []
    with connect() as db:
        for config in configs_to_generate:
            # 检查是否已存在
            existing = db.execute(
                'SELECT id FROM models WHERE name=? AND is_preset=1',
                (config['name'],)
            ).fetchone()

            if existing:
                print(f"✓ {config['name']} 已存在（ID: {existing['id']}）")
                continue

            if dry_run:
                print(f"[Dry Run] 将生成 {config['name']}（{config['desc']}）")
                continue

            model_id = uuid4().hex
            request_id = str(uuid4())

            try:
                # 构建个性化提示词，融入风格描述
                base_prompt = base_prompts.get(config['gender'], '')
                # 提取年龄描述并替换
                age_desc = config['desc']
                style_desc = config['style']

                # 在基础提示词中插入个性化风格
                custom_prompt = base_prompt.replace(
                    '25至30岁，东亚外貌',
                    f'{age_desc}，东亚外貌，{style_desc}'
                )

                body = {
                    'model': 'gpt-image-2.5-flare',
                    'input': [{'role': 'user', 'content': [
                        {'type': 'input_text', 'text': custom_prompt},
                    ]}],
                    'size': '1024x1536',
                    'quality': 'high',
                }

                headers = {
                    'Authorization': api_key,
                    'Content-Type': 'application/json',
                    'request-id': request_id
                }
                if uuap_id:
                    headers['uuap-id'] = uuap_id

                print(f"生成 {config['name']}...", end=' ', flush=True)
                request = Request(GATEWAY, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')

                with urlopen(request, timeout=300) as response:
                    response_raw = response.read()

                result = json.loads(response_raw)

                # 提取图片数据
                output = result.get('output', [])
                if not output:
                    print(f"❌ 生成失败：无输出")
                    continue

                image_data = None
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    for content in [item, *(item.get('content') or [])]:
                        if not isinstance(content, dict):
                            continue
                        value = content.get('result') or content.get('b64_json')
                        if value:
                            if value.startswith('data:image/'):
                                value = value.partition(',')[2]
                            image_data = base64.b64decode(value)
                            break
                    if image_data:
                        break

                if not image_data:
                    print(f"❌ 生成失败：未找到图片数据")
                    continue

                # 保存图片
                final_path = model_path(model_id)
                temp_path = final_path.with_suffix('.tmp')
                temp_path.write_bytes(image_data)

                # 转换为 JPEG
                img = Image.open(temp_path)
                img.convert('RGB').save(final_path, 'JPEG', quality=92)
                temp_path.unlink()

                # 插入数据库
                db.execute(
                    'INSERT INTO models (id, name, gender, image_path, is_preset, visitor, sort_order, created) '
                    'VALUES (?, ?, ?, ?, 1, NULL, ?, ?)',
                    (model_id, config['name'], config['gender'], str(final_path), len(generated) + 10, now())
                )

                print(f"✓ （ID: {model_id}）")
                generated.append({'id': model_id, **config})

                # 避免请求过快
                time.sleep(2)

            except HTTPError as exc:
                print(f"❌ HTTP {exc.code}")
            except (URLError, TimeoutError):
                print(f"❌ 连接超时")
            except Exception as exc:
                print(f"❌ {type(exc).__name__}: {exc}")

    return generated


def main():
    parser = argparse.ArgumentParser(description='初始化预设模特到数据库')
    parser.add_argument('--dry-run', action='store_true', help='预检模式，不实际写入')
    parser.add_argument('--generate', type=int, metavar='N', help='生成 N 个多样化预设模特（通过 Image2）')
    parser.add_argument('--existing-only', action='store_true', help='仅注册现有模特图片，不生成新的')
    args = parser.parse_args()

    if not DATA.exists():
        print(f"❌ 数据目录不存在：{DATA}")
        print("请先运行 backend/server.py 初始化数据库")
        sys.exit(1)

    if not DB.exists():
        print(f"❌ 数据库不存在：{DB}")
        print("请先运行 backend/server.py 初始化数据库")
        sys.exit(1)

    print("=" * 60)
    print("初始化预设模特")
    print("=" * 60)

    # 注册现有模特
    print("\n1. 注册现有模特图片")
    print("-" * 60)
    existing = init_existing_models(dry_run=args.dry_run)

    # 生成更多预设模特
    if not args.existing_only and args.generate:
        print(f"\n2. 生成 {args.generate} 个多样化预设模特")
        print("-" * 60)
        generated = generate_diverse_models(count=args.generate, dry_run=args.dry_run)
        print(f"\n✓ 共生成 {len(generated)} 个新模特")

    print("\n" + "=" * 60)
    if args.dry_run:
        print("[Dry Run] 预检完成，未实际修改数据库")
    else:
        print("✓ 初始化完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
