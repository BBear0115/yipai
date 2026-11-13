"""Create reproducible garment product photos for end-to-end quality checks."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
import server  # noqa: E402

OUTPUT = Path(__file__).resolve().parent
FIXTURES = {
    'striped-shirt': '一件成人长袖圆领针织上衣，白底海军蓝色均匀横条纹，袖子也有连续横条纹，左胸无口袋，无文字无标志。正面平铺，完整衣领、袖口和下摆清晰可见。',
    'red-hoodie': '一件成人正红色套头连帽卫衣，胸前只有白色大写英文单词 NORTH，前腹有一个袋鼠口袋，袖口和下摆为罗纹，正面平铺，完整展示全部衣服。',
    'floral-dress': '一件成人女性浅黄色及膝连衣裙，深绿色小叶与白色五瓣小花重复印花，方领，短泡泡袖，腰部收褶，A字裙摆，正面平铺，衣服完整可见。',
    'denim-jacket': '一件成人蓝色牛仔外套，翻领，正面六枚金属纽扣，左右胸各一个带翻盖的对称口袋，长袖袖口有纽扣，短款直筒版型，正面平铺，完整可见。',
}


def main():
    key, uid = server.credentials()
    if not key or not uid:
        raise SystemExit('Image2 服务未配置')
    for name, garment in FIXTURES.items():
        target = OUTPUT / f'{name}.png'
        if target.exists():
            print(f'{name}: 已存在，跳过', flush=True)
            continue
        prompt = (
            '为鞋服商品上身效果测试制作真实电商商品原图。只拍摄单件衣服，不出现人物、模特、衣架、配饰或其它衣服。'
            '纯浅灰背景，柔和均匀光线，面料纹理真实，衣服居中占画面大部分，无遮挡，正面完整展示。'
            f'商品精确规格：{garment}不要增加说明文字、价格、水印或多余品牌。'
        )
        body = {'model': 'gpt-image-2', 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}],
                'size': '1024x1024', 'quality': 'high'}
        request = Request(server.GATEWAY, data=json.dumps(body, ensure_ascii=False).encode(),
                          headers={'Authorization': key, 'Content-Type': 'application/json', 'uuap-id': uid,
                                   'request-id': str(uuid4())}, method='POST')
        with urlopen(request, timeout=300) as response:
            raw = response.read(server.MAX_OUTPUT + 1)
        if len(raw) > server.MAX_OUTPUT:
            raise RuntimeError('响应过大')
        image = server.extract_output(json.loads(raw))
        target.write_bytes(image)
        print(f'{name}: 已生成 {target.name}', flush=True)


if __name__ == '__main__':
    main()
