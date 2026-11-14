"""拍同款：先用视觉模型反推参考图的拍法，再让模特穿上用户的商品，按这个拍法生成 3 张。"""
from __future__ import annotations

import json
import re

REMAKE_COUNT = 3
ANALYSIS_FIELDS = ('original_category', 'product_note', 'shot', 'pose', 'styling', 'scene', 'lighting', 'color', 'mood')

ANALYSIS_INSTRUCTION = '''你是电商服装摄影的拍摄指导。图1是用户想模仿的参考图（多为电商截图），图2是用户要拍的商品图。
任务：反推图1的拍法，写成一份拍摄方案，让虚拟模特穿上图2的商品按这个方案重拍。

要求：
1. 忽略图1里的手机界面元素：状态栏、价格、按钮、角标、水印、平台文字。
2. 只描述拍法，不描述图1里原模特的长相，也不照搬原商品的图案、品牌字样和装饰。
3. 先判断图2里哪件才是商品（图2可能是带人或带搭配的上身图），再按图2商品的品类调整方案：
   原图展示的部位和图2商品不一致时，调整景别，保证图2商品完整、显眼。
4. styling 写其余搭配单品：保留参考图的气质，但颜色和图案要克制，不能抢图2商品的视觉重心，也不能有品牌字样或图案。
5. scene 里如果原图有招牌或文字，写成"没有可辨认的文字"。
6. variants 写 3 条差异明显的拍法：第 1 条照参考图原姿势；第 2、3 条换姿势或机位（走动抓拍、坐姿、侧身、换景别），都要让图2商品完整可见。
7. 每个字段用一两句话写清楚生图要用的信息，不写镜头焦段、器材和布光设备。
8. reference_box 是图1中真正的商品照片区域（去掉状态栏、按钮、价格条等界面部分），product_box 是图2中商品照片区域；
   都用 [左, 上, 右, 下] 表示，取值是相对整张图的千分比（0-1000 的整数）。没有界面元素时写 [0, 0, 1000, 1000]。

只输出一个 JSON 对象，不要任何其他文字，字段如下（文字值都用中文）：
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
  "variants": ["第1张拍法", "第2张拍法", "第3张拍法"],
  "reference_box": [0, 0, 1000, 1000],
  "product_box": [0, 0, 1000, 1000]
}'''


def _box(value):
    if not (isinstance(value, list) and len(value) == 4 and all(isinstance(v, (int, float)) for v in value)):
        return None
    left, top, right, bottom = (max(0, min(1000, int(v))) for v in value)
    # A box covering under a quarter of the image is more likely a misread than a real photo region.
    if right - left < 200 or bottom - top < 200 or (right - left) * (bottom - top) < 250_000:
        return None
    return [left, top, right, bottom]


def parse_analysis(text: str) -> dict:
    match = re.search(r'\{.*\}', text, re.S)
    if not match:
        raise ValueError('反推结果不是 JSON')
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError('反推结果不是 JSON 对象')
    missing = [key for key in ANALYSIS_FIELDS if not isinstance(data.get(key), str) or not data[key].strip()]
    variants = data.get('variants')
    if missing or not isinstance(variants, list) or len(variants) < REMAKE_COUNT or not all(isinstance(v, str) and v.strip() for v in variants[:REMAKE_COUNT]):
        raise ValueError('反推结果缺少字段')
    result = {key: data[key].strip() for key in ANALYSIS_FIELDS}
    result['variants'] = [v.strip() for v in variants[:REMAKE_COUNT]]
    result['reference_box'] = _box(data.get('reference_box'))
    result['product_box'] = _box(data.get('product_box'))
    return result


def build_remake_prompt(analysis: dict, index: int, keep_model: bool) -> str:
    """index 从 0 开始。keep_model 表示图1来自用户作品，直接沿用图1里的模特，此时不会传模特参考图。"""
    if keep_model:
        roles = ('图1是一张已经穿着目标商品的模特图，图1中的模特就是出镜模特，保留其面部、发型和整体身份特征。'
                 '图2是参考图。')
        subject = '让图1中的模特继续穿着图1的商品'
    else:
        roles = ('图1是目标商品的原图；图1里如果有人，忽略此人的长相、发型和身材，只看衣服。'
                 '图2是虚拟模特的形象参考，出镜的人必须是图2的模特，保留其面部、发型和整体身份特征。图3是参考图。')
        subject = '让图2中的模特穿上图1的商品'
    reference = '图2' if keep_model else '图3'
    lines = [('景别与机位', 'shot'), ('姿势', 'pose'), ('搭配造型', 'styling'), ('场景', 'scene'),
             ('光线', 'lighting'), ('色调', 'color'), ('整体风格', 'mood')]
    plan = '\n'.join(f'- {label}：{analysis[key]}' for label, key in lines)
    return (
        roles
        + f'{reference}只用来参考拍法：构图、机位、姿势、搭配、场景、光线和色调；'
        f'{reference}中的人物长相、服装商品、品牌标识、界面元素和任何文字都不得出现在结果里。'
        + analysis['product_note']
        + f'\n{subject}，按下面的拍摄方案生成一张电商可用的竖版真实摄影图：\n'
        + plan + '\n'
        + f'- 本张拍法：{analysis["variants"][index]}\n'
        + f'参考图里原商品是{analysis["original_category"]}，现在要展示的是图1的商品；'
        '如果参考姿势依赖原商品才有的结构（例如口袋、帽子），改用目标商品或其他单品上合理存在的结构，'
        '不要为了贴合姿势给图1商品添加任何结构。\n'
        '严格保留目标商品的颜色、图案的大小与间距、面料质感、版型和结构，以图1实际可见结构为准，不按常见款式补全。'
        '搭配单品不能抢走目标商品的视觉重心，也不能遮挡目标商品。'
        '只有一位成年模特；不要额外人物、文字、价格、按钮、品牌标识、边框或水印。'
    )
