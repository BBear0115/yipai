"""Generate two model-card assets through the user-specified Image2 gateway."""
from __future__ import annotations

import base64
from io import BytesIO
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / '.env.local'
GATEWAY = 'https://ai-force.duxiaoman-int.com/v1/responses'
Image.MAX_IMAGE_PIXELS = 30_000_000


def config() -> tuple[str | None, str | None]:
    values = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            if key.strip() in {'IMAGE2_GATEWAY_API_KEY', 'IMAGE2_UUAP_ID'}:
                values[key.strip()] = value.strip().strip('"\'')
    return (os.environ.get('IMAGE2_GATEWAY_API_KEY') or values.get('IMAGE2_GATEWAY_API_KEY'),
            os.environ.get('IMAGE2_UUAP_ID') or values.get('IMAGE2_UUAP_ID'))


def extract_image(response: dict) -> bytes:
    # Handle output[].result from Image2, plus common base64 response variants.
    def walk(node):
        if isinstance(node, dict):
            for key in ('b64_json', 'image_base64', 'image', 'data', 'result'):
                value = node.get(key)
                if isinstance(value, str) and len(value) > 100:
                    yield value
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
    for candidate in walk(response.get('output', response)):
        if candidate.startswith('data:image/'):
            candidate = candidate.partition(',')[2]
        candidate = ''.join(candidate.split())
        try:
            raw = base64.b64decode(candidate, validate=True)
            with Image.open(BytesIO(raw)) as image:
                image.verify()
            return raw
        except (ValueError, OSError, UnidentifiedImageError):
            continue
    raise RuntimeError('图片服务未返回可读取的图片')


def generate_models(dry_run=False):
    api_key, uuap_id = config()
    assets = ROOT / 'mockup' / 'assets'
    prompts = {}
    for gender, label in [('female', '女性'), ('male', '男性')]:
        prompts[gender] = (
            f'为鞋服展示工具制作一张真实商业摄影风格的成年{label}虚拟模特全身照。'
            '单人，25至30岁，东亚外貌，自然站姿，双手自然放置，头顶到鞋底完整可见，'
            '米白色简洁衬衫，深灰色长裤，简洁白鞋，没有品牌标志。'
            '纯浅灰摄影背景，柔和均匀光线，真实皮肤与面料纹理，人物位于画面右半区，'
            '左侧约三分之一留白用于界面文字；无文字、无拼图、无水印。'
        )
    (ROOT / 'scripts' / 'model-prompts.json').write_text(json.dumps(prompts, ensure_ascii=False, indent=2))
    if dry_run:
        print('请求预检通过：2 张，1536x1024，high；未发送请求')
        return
    if not api_key or not uuap_id:
        raise SystemExit('未配置 IMAGE2_GATEWAY_API_KEY 和 IMAGE2_UUAP_ID；未发送请求')
    assets.mkdir(exist_ok=True)
    for gender, prompt in prompts.items():
        destination = assets / (gender + '-model.png')
        if destination.exists():
            print(f'{gender}: 已有素材，跳过以避免重复计费')
            continue
        request_id = str(uuid4())
        body = {'model': 'gpt-image-2', 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}], 'size': '1536x1024', 'quality': 'high'}
        request = Request(GATEWAY, data=json.dumps(body).encode('utf-8'), headers={'Authorization':api_key,'Content-Type':'application/json','uuap-id':uuap_id,'request-id':request_id},method='POST')
        try:
            with urlopen(request, timeout=300) as response:
                raw = response.read(40 * 1024 * 1024 + 1)
                if len(raw) > 40 * 1024 * 1024:
                    raise RuntimeError('响应过大')
            raw_image = extract_image(json.loads(raw))
            image = Image.open(BytesIO(raw_image)).convert('RGB')
            font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 18)
            ImageDraw.Draw(image).text((image.width - 385, image.height - 36), '衣拍 · 人工智能生成', font=font, fill=(80,80,80))
            image.save(destination, format='PNG')
            print(f'{gender}: 已保存 {destination.name} request={request_id}')
        except HTTPError as exc:
            raise SystemExit(f'网关请求失败 HTTP {exc.code} request={request_id}') from None
        except Exception as exc:
            raise SystemExit(f'生成失败 {type(exc).__name__} request={request_id}') from None

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    generate_models(parser.parse_args().dry_run)
