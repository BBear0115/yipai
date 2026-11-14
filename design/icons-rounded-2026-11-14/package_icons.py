from pathlib import Path
from PIL import Image, ImageOps, ImageFont, ImageDraw
import json
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'generated/20261114T082112Z-393ea59b-7f9f-4e8e-a701-e7259e897586/image-01.png'
OUT = ROOT / 'yipai-rounded-icons'
OUT.mkdir(exist_ok=True)
ITEMS = [
    ('nav-create', '创作', '底部导航'),
    ('nav-community', '社区', '底部导航'),
    ('nav-profile', '我的', '底部导航'),
    ('feature-shoot', '开拍', '创作功能'),
    ('feature-remake', '拍同款', '创作功能'),
    ('feature-variations', '创意裂变', '创作功能'),
    ('community-like', '点赞', '社区操作'),
    ('community-bookmark', '收藏', '社区操作'),
    ('community-share', '分享', '社区操作'),
    ('community-save', '保存', '社区操作'),
    ('profile-settings', '设置', '我的页面'),
    ('profile-bookmarks', '收藏', '我的页面'),
    ('profile-portfolio', '作品集', '我的页面'),
]
source = Image.open(SOURCE).convert('RGB')
glyphs = []
for i, (name, label, group) in enumerate(ITEMS[:12]):
    col, row = i % 4, i // 4
    cell = source.crop((round(col*source.width/4), round(row*source.height/3),
                        round((col+1)*source.width/4), round((row+1)*source.height/3)))
    # Remap the nearly white generated background to transparency; preserve antialiasing.
    alpha = ImageOps.grayscale(cell).point(lambda v: round(max(0, 245-v)*255/245))
    bbox = alpha.point(lambda v: 255 if v > 24 else 0).getbbox()
    if bbox is None:
        raise ValueError(f'Missing icon: {name}')
    glyph = Image.new('RGBA', cell.size, (0, 0, 0, 0))
    glyph.putalpha(alpha)
    x0, y0, x1, y1 = bbox
    glyphs.append(glyph.crop((max(0, x0-2), max(0, y0-2), min(cell.width, x1+2), min(cell.height, y1+2))))
# Reuse the same bookmark pixels in both contexts.
glyphs[11] = glyphs[7].copy()
scale = 192 / max(max(im.size) for im in glyphs)
portfolio = Image.open(ROOT / 'portfolio-source.png').convert('RGB')
alpha = ImageOps.grayscale(portfolio).point(lambda v: round(max(0, 245-v)*255/245))
bbox = alpha.point(lambda v: 255 if v > 24 else 0).getbbox()
if bbox is None:
    raise ValueError('Missing portfolio icon')
portfolio = Image.new('RGBA', portfolio.size, (0, 0, 0, 0))
portfolio.putalpha(alpha)
x0, y0, x1, y1 = bbox
portfolio = portfolio.crop((max(0,x0-2), max(0,y0-2), min(portfolio.width,x1+2), min(portfolio.height,y1+2)))
portfolio_scale = (192/scale) / max(portfolio.size)
glyphs.append(portfolio.resize((round(portfolio.width*portfolio_scale), round(portfolio.height*portfolio_scale)), Image.Resampling.LANCZOS))
masters = []
manifest = []
for (name, label, group), glyph in zip(ITEMS, glyphs):
    glyph = glyph.resize((round(glyph.width*scale), round(glyph.height*scale)), Image.Resampling.LANCZOS)
    master = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    master.alpha_composite(glyph, ((256-glyph.width)//2, (256-glyph.height)//2))
    masters.append(master)
    for size in [24, 28, 32, 48, 64, 128, 256]:
        target = OUT / f'png-{size}'
        target.mkdir(exist_ok=True)
        master.resize((size, size), Image.Resampling.LANCZOS).save(target / f'{name}.png')
    manifest.append({'file': name+'.png', 'label': label, 'group': group})

font_path = '/System/Library/Fonts/STHeiti Medium.ttc'
font = lambda size: ImageFont.truetype(font_path, size)
board = Image.new('RGB', (1440, 1400), 'white')
d = ImageDraw.Draw(board)
d.text((88, 65), '衣拍 / 圆角线性图标', font=font(48), fill='#111111')
d.text((90, 141), '13 个图标  ·  黑色描边  ·  圆角轮廓  ·  透明 PNG', font=font(23), fill='#777777')
groups = [('01  底部导航', [0,1,2]), ('02  创作功能', [3,4,5]),
          ('03  社区操作', [6,7,8,9]), ('04  我的页面', [10,11,12])]
for row, (title, indices) in enumerate(groups):
    top = 225 + row*280
    d.line((88, top, 1352, top), fill='#e8e8e8', width=1)
    d.text((90, top+22), title, font=font(23), fill='#777777')
    for col, idx in enumerate(indices):
        cx = 246 + col*316
        icon = masters[idx].resize((112,112), Image.Resampling.LANCZOS)
        board.paste(icon, (cx-56, top+71), icon)
        d.text((cx,top+209), ITEMS[idx][1], font=font(27), fill='#111111', anchor='mm')
board.save(OUT / '图标总览.png')
board.save(ROOT / 'preview.png')

# One-to-one screen pixels, enlarged for a convenient inspection of raster edges.
qa = Image.new('RGB', (900, 210), '#f3f3f3')
qd = ImageDraw.Draw(qa)
for i, master in enumerate(masters):
    x = 25+i*65
    small = master.resize((28,28), Image.Resampling.LANCZOS)
    qa.paste(small, (x,35), small)
    enlarged = small.resize((56,56), Image.Resampling.NEAREST)
    qa.paste(enlarged, (x-14,100), enlarged)
qa.save(ROOT / 'qa-28px.png')

portfolio_preview = Image.new('RGB', (384, 320), 'white')
portfolio_icon = masters[12].resize((160,160), Image.Resampling.LANCZOS)
portfolio_preview.paste(portfolio_icon, (112,48), portfolio_icon)
ImageDraw.Draw(portfolio_preview).text((192,250), '作品集', font=font(28), fill='#111111', anchor='mm')
portfolio_preview.save(ROOT / 'portfolio-preview.png')

(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
readme = '''# 衣拍 · 圆角线性图标

使用 image2-5 / gpt-image-2.5-sunburst，根据用户提供的参考图生成。
13 个使用位置、12 个独立图形；两个页面的收藏复用同一图形。
我的页面新增作品集图标：四枚圆角方格组成的画廊标志。

提供 24、28、32、48、64、128、256 像素透明 PNG，均为黑色图形。
建议导航使用 28px，社区操作使用 24px，创作入口使用 32–48px。
所有图形保持统一缩放比例和线条粗细，画布中留有安全空间。
文件名前缀 nav / feature / community / profile 分别对应底部导航、创作功能、社区操作、我的页面。

PNG 为生成图片拆分、去白底后的栅格素材；非 SVG 矢量文件。
仅交付图标素材，未改动应用页面。
'''
(OUT / 'README.md').write_text(readme, encoding='utf-8')
archive = ROOT / '衣拍-圆角图标-13枚.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            z.write(path, path.relative_to(ROOT))
print(json.dumps({'preview': str(ROOT/'preview.png'), 'archive': str(archive), 'png_count': len(ITEMS)*7}, ensure_ascii=False))
