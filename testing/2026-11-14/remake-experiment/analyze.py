"""拍同款实验：用视觉模型自动反推参考截图，替代 cases.json 里的人工反推。

用法：
    .venv/bin/python testing/2026-11-14/remake-experiment/analyze.py [--case ID]

密钥写在项目根目录 .env.local 的 ANALYZE_API_KEY；接口地址和模型名可用
ANALYZE_BASE_URL、ANALYZE_MODEL 覆盖。结果写到 outputs/<case>/analysis.auto.json，
再用 run_experiment.py --analysis auto 生成图片。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from backend.server import image_data_url  # noqa: E402
from run_experiment import load_jpeg  # noqa: E402

DEFAULT_BASE_URL = 'http://z.duxiaoman-int.com/coding/v1'
DEFAULT_MODEL = 'gpt-6.1-sol'
FIELDS = ['original_category', 'shot', 'pose', 'styling', 'scene', 'lighting', 'color', 'mood']

INSTRUCTION = '''你是电商服装摄影的拍摄指导。图1是用户在电商平台截的参考图，图2是用户要拍的商品图。
任务：反推图1的拍法，写成一份拍摄方案，让我们的虚拟模特穿上图2的商品按这个方案重拍。

要求：
1. 忽略图1里的手机界面元素：状态栏、价格、按钮、角标、水印、平台文字。
2. 只描述拍法，不描述图1里原模特的长相，也不照搬原商品的图案、品牌字样和装饰。
3. 先判断图2里哪件才是商品（图2可能是带人或带搭配的上身图），再按图2商品的品类调整方案：
   原图展示的部位如果和图2商品不一致，就调整景别，保证图2商品完整、显眼。
4. styling 写其余搭配单品：保留参考图的气质，但颜色和图案要克制，不能抢图2商品的视觉重心，
   也不能出现任何品牌字样或图案。
5. scene 里如果原图有招牌或文字，写成"没有可辨认的文字"。
6. variants 写 3 条差异明显的拍法：第 1 条照参考图原姿势；第 2、3 条换姿势或机位，
   比如走动抓拍、坐姿、侧身、换景别，并且都要能让图2商品完整可见。

只输出一个 JSON 对象，不要任何其他文字，字段如下（值都用中文）：
{
  "original_category": "图1原商品的品类和款式",
  "product_note": "说明图2里哪件是目标商品；图2里还有哪些东西不是商品、不要出现在结果里",
  "shot": "景别与机位",
  "pose": "姿势与表情",
  "styling": "其余搭配单品",
  "scene": "场景",
  "lighting": "光线",
  "color": "色调",
  "mood": "整体风格",
  "variants": ["第1张拍法", "第2张拍法", "第3张拍法"]
}'''


def env_value(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    source = ROOT / '.env.local'
    if source.is_file():
        for line in source.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                if key.strip() == name:
                    return value.strip().strip('"\'') or None
    return None


def output_text(payload: dict) -> str:
    if isinstance(payload.get('output_text'), str):
        return payload['output_text']
    parts = []
    for item in payload.get('output') or []:
        for content in item.get('content') or []:
            if content.get('type') == 'output_text' and isinstance(content.get('text'), str):
                parts.append(content['text'])
    if not parts:
        raise RuntimeError('反推模型没有返回文字：' + json.dumps(payload, ensure_ascii=False)[:500])
    return ''.join(parts)


def parse_json(text: str) -> dict:
    match = re.search(r'\{.*\}', text, re.S)
    if not match:
        raise RuntimeError('反推结果不是 JSON：' + text[:500])
    data = json.loads(match.group(0))
    missing = [key for key in [*FIELDS, 'product_note', 'variants'] if not data.get(key)]
    if missing or len(data['variants']) != 3:
        raise RuntimeError(f'反推结果缺少字段 {missing} 或 variants 不是 3 条')
    return data


def analyze(reference: str, product: str, api_key: str, base_url: str, model: str) -> dict:
    body = {
        'model': model,
        'input': [{'role': 'user', 'content': [
            {'type': 'input_text', 'text': INSTRUCTION},
            {'type': 'input_image', 'image_url': reference},
            {'type': 'input_image', 'image_url': product},
        ]}],
        # 该网关只支持流式，非流式请求会返回 502
        'stream': True,
    }
    request = Request(base_url.rstrip('/') + '/responses', data=json.dumps(body).encode('utf-8'), method='POST',
                      headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json',
                               'Accept': 'text/event-stream', 'request-id': str(uuid4())})
    deltas, completed = [], None
    try:
        with urlopen(request, timeout=300) as response:
            for raw_line in response:
                line = raw_line.decode('utf-8', 'replace').strip()
                if not line.startswith('data:') or line == 'data: [DONE]':
                    continue
                event = json.loads(line[5:])
                if event.get('type') == 'response.output_text.delta':
                    deltas.append(event.get('delta', ''))
                elif event.get('type') == 'response.completed':
                    completed = event.get('response')
                elif event.get('type') in ('error', 'response.failed'):
                    raise RuntimeError('反推请求失败：' + json.dumps(event, ensure_ascii=False)[:500])
    except HTTPError as exc:
        raise RuntimeError(f'反推请求失败（{exc.code}）：' + exc.read().decode('utf-8', 'replace')[:500]) from exc
    text = ''.join(deltas) or output_text(completed or {})
    return parse_json(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', help='只反推指定用例')
    args = parser.parse_args()

    api_key = env_value('ANALYZE_API_KEY')
    if not api_key:
        raise SystemExit('未配置 ANALYZE_API_KEY（写在项目根目录 .env.local）')
    base_url = env_value('ANALYZE_BASE_URL') or DEFAULT_BASE_URL
    model = env_value('ANALYZE_MODEL') or DEFAULT_MODEL

    cases = json.loads((HERE / 'cases.json').read_text(encoding='utf-8'))
    if args.case:
        cases = [case for case in cases if case['id'] == args.case]
    for case in cases:
        reference = image_data_url(load_jpeg(HERE / case['reference'], case.get('reference_crop')))
        product = image_data_url(load_jpeg((HERE / case['product']).resolve(), case.get('product_crop')))
        try:
            result = analyze(reference, product, api_key, base_url, model)
        except Exception as exc:
            print(f'{case["id"]} 反推失败：{exc}')
            continue
        out_dir = HERE / 'outputs' / case['id']
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'analysis.auto.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{case["id"]} 反推完成（{model}）', flush=True)


if __name__ == '__main__':
    main()
