"""图片翻译工作流"""

def build_image_translation_prompt(translation_type: str, source_style: str, target_style: str, custom_desc: str = "") -> str:
    """
    生成图片翻译提示词

    translation_type: 'season' | 'scene' | 'style' | 'time'
    source_style: 原始风格
    target_style: 目标风格
    """

    if translation_type == 'season':
        base = f"""图1是{source_style}风格的商品照片。

任务：将照片氛围从{source_style}转换到{target_style}，但保持商品本身不变。

翻译规则：
1. 商品完全不变：
   - 锁定服装颜色、图案、版型、所有细节
   - 人物脸部、身体、姿势不变

2. 氛围转换：
   - 背景：从{source_style}场景变为{target_style}场景
   - 光线：从{source_style}光线变为{target_style}光线
   - 色调：从{source_style}色调变为{target_style}色调

3. 季节特征：
   - {target_style}的典型环境（树叶、光线、天气）
   - {target_style}的色温和氛围感

保持商品展示清晰，氛围自然协调。"""

    elif translation_type == 'scene':
        base = f"""图1是{source_style}场景的商品照片。

任务：将场景从{source_style}转换到{target_style}，保持人物和服装不变。

翻译规则：
1. 人物服装锁定：
   - 完整保留图1的人物身份、脸部、姿势
   - 锁定服装所有细节和颜色

2. 场景转换：
   - 从{source_style}环境变为{target_style}环境
   - 背景元素符合{target_style}的典型特征
   - 光线和色调适配新场景

3. 自然融合：
   - 人物与新场景的光影协调
   - 合理的空间关系和透视

输出：{target_style}场景的商品展示照片。"""

    elif translation_type == 'style':
        base = f"""图1是{source_style}风格的商品照片。

任务：将摄影风格从{source_style}转换到{target_style}，保持商品和人物身份不变。

翻译规则：
1. 内容保持：
   - 人物身份、脸部、服装完全不变
   - 商品细节、颜色、图案锁定

2. 风格转换：
   - 从{source_style}摄影风格变为{target_style}风格
   - 构图、光线、色调符合{target_style}特征
   - 背景和氛围适配新风格

3. 质量标准：
   - 保持{target_style}的典型审美
   - 商业摄影水准

输出：{target_style}风格的商品照片。"""

    else:  # time
        base = f"""图1是{source_style}的商品照片。

任务：将时间氛围从{source_style}转换到{target_style}，保持主体不变。

翻译规则：
1. 主体保持：
   - 人物和服装完全不变
   - 商品细节锁定

2. 时间转换：
   - 光线：从{source_style}光线变为{target_style}光线
   - 色温：符合{target_style}的自然色温
   - 氛围：{target_style}的典型感觉

3. 细节协调：
   - 阴影方向和强度符合{target_style}
   - 环境亮度自然

输出：{target_style}氛围的商品照片。"""

    if custom_desc:
        base += f"\n\n补充说明：{custom_desc}"

    return base


# 预设的翻译选项
TRANSLATION_PRESETS = {
    'season': {
        'spring': '春季（明亮、清新、嫩绿）',
        'summer': '夏季（阳光、明媚、热情）',
        'autumn': '秋季（温暖、金黄、沉静）',
        'winter': '冬季（冷色调、清冷、雪景）'
    },
    'scene': {
        'indoor': '室内（简约空间、自然光）',
        'outdoor_street': '户外街道（城市、街拍）',
        'outdoor_nature': '户外自然（公园、树林）',
        'beach': '海边（沙滩、海浪）',
        'studio': '摄影棚（纯背景、专业光）'
    },
    'style': {
        'casual': '休闲风格',
        'formal': '正式风格',
        'vintage': '复古风格',
        'minimalist': '极简风格',
        'editorial': '杂志大片风格'
    },
    'time': {
        'morning': '清晨（柔和晨光）',
        'noon': '正午（明亮直射光）',
        'afternoon': '午后（温暖侧光）',
        'evening': '傍晚（金色夕阳）',
        'night': '夜晚（人工光源）'
    }
}
