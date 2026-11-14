"""拍同款实验：对比「只传反推文字」与「反推文字 + 参考截图」两种生成方式。

用法：
    .venv/bin/python testing/2026-11-14/remake-experiment/run_experiment.py --dry-run
    .venv/bin/python testing/2026-11-14/remake-experiment/run_experiment.py [--case ID] [--method text|ref] [--analysis manual|auto]

--analysis manual 用 cases.json 里的人工反推（视觉模型反推的理想上限），
auto 用 analyze.py 生成的 outputs/<case>/analysis.auto.json。
结果输出到 outputs/<case>/<method>-<n>.jpg，auto 模式为 auto-<method>-<n>.jpg。
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import sys
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from backend.server import credentials, image_data_url, request_image  # noqa: E402

VARIANTS = [
    '姿势与参考完全一致。',
    '在参考姿势基础上，身体向左微转约 15 度，头部轻微偏向镜头一侧，其余不变。',
    '在参考姿势基础上，改为一只手插兜、另一只手自然垂放，重心轻微落在一条腿上，其余不变。',
]


def load_jpeg(path: Path, crop=None) -> bytes:
    with Image.open(path) as image:
        image = image.convert('RGB')
        if crop:
            image = image.crop(tuple(crop))
        output = BytesIO()
        image.save(output, 'JPEG', quality=92)
        return output.getvalue()


def describe(analysis: dict) -> str:
    labels = [('shot', '景别与机位'), ('pose', '姿势'), ('styling', '搭配造型'), ('scene', '场景'),
              ('lighting', '光线'), ('color', '色调'), ('mood', '整体风格')]
    return '\n'.join(f'- {label}：{analysis[key]}' for key, label in labels if analysis.get(key))


def build_prompt(analysis: dict, variant: str, with_reference: bool, product_note: str = '') -> str:
    roles = '图1是唯一目标商品的原图，图2是虚拟模特的形象参考。' + product_note
    if with_reference:
        roles += ('图3是一张电商参考图，只用来参考拍法：构图、机位、姿势、搭配、场景、光线和色调。'
                  '图3中的人物长相、服装商品、品牌标识和任何文字都不得出现在结果里。')
    return (
        roles
        + '让图2中的模特穿上图1的商品，按下面的拍摄方案生成一张电商可用的竖版真实摄影图：\n'
        + describe(analysis) + '\n'
        + f'- 本张差异：{variant}\n'
        + f'参考图里原商品是{analysis.get("original_category", "未知品类")}，现在要展示的是图1的商品；'
        '如果参考姿势依赖原商品才有的结构（例如口袋、帽子），改用目标商品或其他单品上合理存在的结构，'
        '不要为了贴合姿势给图1商品添加任何结构。\n'
        '保留模特面部、发型和整体身份特征。'
        '严格保留目标商品的颜色、图案的大小与间距、面料质感、版型和结构，以图1实际可见结构为准，不按常见款式补全。'
        '搭配单品不能抢走目标商品的视觉重心，也不能遮挡目标商品。'
        '只有一位成年模特；不要额外人物、文字、价格、按钮、品牌标识、边框或水印。'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='只输出提示词，不发请求')
    parser.add_argument('--case', help='只跑指定用例')
    parser.add_argument('--method', choices=['text', 'ref'], help='只跑指定方式')
    parser.add_argument('--analysis', choices=['manual', 'auto'], default='manual', help='反推来源')
    args = parser.parse_args()

    cases = json.loads((HERE / 'cases.json').read_text(encoding='utf-8'))
    if args.case:
        cases = [case for case in cases if case['id'] == args.case]
    methods = [args.method] if args.method else ['text', 'ref']

    api_key, uuap_id = credentials()
    if not args.dry_run and not api_key:
        raise SystemExit('未配置 IMAGE2_GATEWAY_API_KEY（.env.local 或环境变量）；可先加 --dry-run 查看提示词')

    for case in cases:
        out_dir = HERE / 'outputs' / case['id']
        out_dir.mkdir(parents=True, exist_ok=True)
        product = image_data_url(load_jpeg((HERE / case['product']).resolve(), case.get('product_crop')))
        model = image_data_url(load_jpeg((HERE / case['model']).resolve()))
        reference_raw = load_jpeg(HERE / case['reference'], case.get('reference_crop'))
        (out_dir / 'reference-crop.jpg').write_bytes(reference_raw)
        reference = image_data_url(reference_raw)
        analysis, product_note, variants, prefix = case.get('analysis', {}), case.get('product_note', ''), case.get('variants', VARIANTS), ''
        if args.analysis == 'auto':
            auto_file = out_dir / 'analysis.auto.json'
            if not auto_file.is_file():
                print(f'{case["id"]} 缺少 analysis.auto.json，先运行 analyze.py')
                continue
            analysis = json.loads(auto_file.read_text(encoding='utf-8'))
            product_note, variants, prefix = analysis.get('product_note', ''), analysis['variants'], 'auto-'

        for method in methods:
            for index, variant in enumerate(variants, 1):
                with_reference = method == 'ref'
                prompt = build_prompt(analysis, variant, with_reference, product_note)
                stem = f'{prefix}{method}-{index}'
                (out_dir / f'{stem}.prompt.txt').write_text(prompt, encoding='utf-8')
                if args.dry_run:
                    print(f'[dry-run] {case["id"]} {stem}：{len(prompt)} 字')
                    continue
                images = [product, model, *([reference] if with_reference else [])]
                request_id = str(uuid4())
                try:
                    result = request_image(prompt, images, '1024x1536', api_key, uuap_id, request_id)
                except Exception as exc:  # 单张失败不影响其他张
                    print(f'{case["id"]} {stem} 失败 request={request_id}：{type(exc).__name__} {exc}')
                    continue
                (out_dir / f'{stem}.jpg').write_bytes(result)
                print(f'{case["id"]} {stem} 完成 request={request_id}', flush=True)


if __name__ == '__main__':
    main()
