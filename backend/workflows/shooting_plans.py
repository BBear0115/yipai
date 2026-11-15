"""Structured scene configurations for fashion photography."""

# Comprehensive scene library with detailed lighting, composition, and mood specifications
SCENE_CONFIGS = {
    'studio': {
        'name': '电商棚拍',
        'description': '简洁白色或浅灰摄影棚，商业产品摄影标准',
        'lighting': '柔和均匀的三点式商业布光，消除阴影，呈现商品真实色彩与细节',
        'composition': '正面或轻微侧身，服装轮廓完整清楚，视觉中心集中在商品',
        'mood': '专业、干净、客观，突出商品本身',
        'styling': '低调纯色搭配，只补足必要单品，不遮挡商品',
        'variants': [
            '正面站姿，双臂自然下垂或单手插袋，柔和均匀商业灯光，完整展示商品正面版型',
            '轻微转身展示服装侧面轮廓，保持干净棚拍背景，商品细节完整可见',
            '改变手臂姿势和机位，突出服装版型与面料垂坠感，保持画面简洁专业',
        ],
    },
    'lookbook': {
        'name': '城市 Lookbook',
        'description': '克制的城市街景与建筑线条，都市时尚氛围',
        'lighting': '自然日光或黄金时段柔和光线，营造真实街拍质感',
        'composition': '环境与人物平衡，利用建筑线条引导视线，商品完整展示',
        'mood': '轻松、真实、有态度，展现穿搭在日常场景中的状态',
        'styling': '根据商品色彩和季节协调搭配，不加入抢眼图案或遮挡商品的配饰',
        'variants': [
            '模特轻松站立在城市街景中，自然日光，展现整套穿搭的松弛感',
            '自然迈步或行走抓拍，捕捉轻松动态，利用城市建筑作为背景层次',
            '轻微侧身回望或倚靠墙面，以不同机位呈现服装轮廓，保持街拍真实感',
        ],
    },
    'lifestyle': {
        'name': '室内生活方式',
        'description': '明亮简约的室内空间，居家或咖啡厅等生活场景',
        'lighting': '柔和窗光或室内自然光，营造温暖亲和氛围',
        'composition': '环境营造生活感，人物姿态自然放松，商品融入日常穿搭',
        'mood': '亲和、松弛、有温度，传达服装的日常可穿性',
        'styling': '生活化搭配但保持克制，不新增品牌图案或遮挡商品的物件',
        'variants': [
            '自然站立在明亮室内空间，柔和窗光，画面亲和松弛',
            '靠近窗边或简洁家具自然倚靠，微侧身姿势展示商品，光线柔和',
            '改变取景角度和视线方向，或采用坐姿，保持服装细节清楚可见',
        ],
    },
    'magazine': {
        'name': '时尚杂志',
        'description': '专业时尚摄影风格，注重艺术性与视觉冲击力',
        'lighting': '戏剧性光影对比，或柔和高调光线，营造杂志大片质感',
        'composition': '构图讲究，利用环境元素和光影层次，突出时尚态度',
        'mood': '高级、有张力、艺术化，传达品牌调性与时尚主张',
        'styling': '完整造型搭配，配饰与场景呼应，但商品始终是视觉焦点',
        'variants': [
            '经典杂志人像构图，光影层次丰富，模特姿态舒展有张力，商品完整展示',
            '侧逆光或轮廓光营造戏剧感，利用环境线条构图，捕捉动态或特写',
            '高调柔光或暗调氛围，强调面部表情与肢体语言，商品细节清晰可辨',
        ],
    },
    'korean': {
        'name': '韩系清透',
        'description': '明亮通透的韩式摄影，色调清新柔和',
        'lighting': '高调柔光，微微过曝的清透感，减弱阴影',
        'composition': '简洁背景，人物居中或留白，营造轻盈空气感',
        'mood': '清新、柔和、少女感，传达轻松愉悦的情绪',
        'styling': '浅色系或柔和色彩搭配，简约配饰，整体干净清透',
        'variants': [
            '明亮均匀柔光，浅色或纯色背景，模特自然站立，画面清透明亮',
            '柔和侧光，微微仰拍或平视，捕捉自然笑容或放松表情，色调清新',
            '留白构图，模特微微侧身或回眸，光线通透，营造轻盈氛围感',
        ],
    },
    'street': {
        'name': '街头潮流',
        'description': '都市街头文化，潮流态度鲜明',
        'lighting': '自然光或城市环境光，真实街头质感',
        'composition': '街头涂鸦、霓虹灯、城市角落等元素，构图大胆有冲击力',
        'mood': '酷、有态度、年轻化，展现街头文化与个性',
        'styling': '潮流单品组合，配饰或鞋履呼应街头风格，商品是造型核心',
        'variants': [
            '街头涂鸦墙或工业风背景，自然光，模特放松站姿或倚靠，展现潮流态度',
            '城市街角或天桥下，捕捉行走或跳跃动态，光线真实，构图有张力',
            '夜晚城市霓虹灯光，或傍晚蓝调时刻，低角度拍摄，营造street style氛围',
        ],
    },
    'minimal_japanese': {
        'name': '简约日系',
        'description': '日式极简美学，克制内敛的东方审美',
        'lighting': '柔和自然光，避免过度曝光，保留细腻层次',
        'composition': '大量留白，构图克制，人物与环境和谐共存',
        'mood': '平静、内敛、有质感，传达生活美学',
        'styling': '基础色系搭配，避免繁复装饰，强调面料质感与版型',
        'variants': [
            '素色墙面或木质背景，柔和散射光，模特自然站立，构图留白克制',
            '窗边或室内一角，侧面或微侧身，捕捉日常状态，光线柔和细腻',
            '极简空间，平视或微俯拍，模特坐姿或倚靠，画面安静有呼吸感',
        ],
    },
    'vintage': {
        'name': '复古胶片',
        'description': '胶片摄影质感，怀旧复古氛围',
        'lighting': '温暖色温或冷调胶片感，模拟自然光的柔和过渡',
        'composition': '略带颗粒感的画面，色彩饱和度适中，构图经典',
        'mood': '怀旧、温暖、有故事感，唤起情感记忆',
        'styling': '复古单品或经典款式搭配，整体色调和谐统一',
        'variants': [
            '温暖色调，胶片颗粒质感，模特自然站立或行走，捕捉日常瞬间感',
            '冷调或褪色效果，侧光或逆光，营造时光感，构图参考老照片',
            '暖黄或青蓝调，室内或户外自然场景，模特放松姿态，画面有年代感',
        ],
    },
}

# Legacy format for backward compatibility
AUTO_SHOOTING_PLANS = (
    (
        '电商棚拍',
        '简洁白色或浅灰摄影棚；正面或轻微侧身站姿，服装轮廓完整清楚；'
        '柔和均匀的商业灯光，画面干净，让目标商品成为视觉中心。'
        '搭配只补足必要单品，使用低调纯色，不遮挡商品。',
    ),
    (
        '城市 Lookbook',
        '克制的城市街景与自然日光；模特身体微转并自然迈步，形成轻松动态，'
        '机位略有变化但仍完整展示目标商品。搭配根据商品色彩和季节协调，'
        '不加入抢眼图案或遮挡商品的外套、包和配饰。',
    ),
    (
        '室内生活方式',
        '明亮简约的室内空间与柔和窗光；模特自然站立或轻倚，采用有别于前两张的角度和构图，'
        '保持目标商品完整可见。搭配更有生活感但保持克制，不新增品牌、图案或会遮住商品的物件。',
    ),
)

STYLED_SHOOTING_PLANS = {
    'studio': (
        '简洁白色或浅灰摄影棚；以正面站姿、柔和均匀的商业灯光呈现商品。',
        '保持干净棚拍背景，模特轻微转身展示服装侧面轮廓，商品完整清楚。',
        '保持干净棚拍背景，改变手臂姿势和机位，突出服装版型与面料垂坠。',
    ),
    'lookbook': (
        '克制的城市街景与自然日光；模特轻松站立，展现整套穿搭。',
        '在同一城市风格中自然迈步，捕捉轻松动态，商品完整可见。',
        '在城市建筑前轻微侧身回望，以不同机位呈现服装轮廓。',
    ),
    'lifestyle': (
        '明亮简约的室内空间与柔和窗光；模特自然站立，画面亲和松弛。',
        '靠近窗边或简洁家具自然倚靠，以微侧身姿势展示商品。',
        '在同类室内空间改变取景角度和视线方向，保持服装细节清楚。',
    ),
}


def get_available_scenes() -> list[str]:
    """Return all available scene IDs."""
    return list(SCENE_CONFIGS.keys())


def get_scene_metadata(scene_id: str) -> dict:
    """Get scene configuration without variants (for UI display)."""
    if scene_id not in SCENE_CONFIGS:
        raise ValueError('场景不存在')
    scene = SCENE_CONFIGS[scene_id]
    return {
        'id': scene_id,
        'name': scene['name'],
        'description': scene['description'],
        'lighting': scene['lighting'],
        'composition': scene['composition'],
        'mood': scene['mood'],
        'styling': scene['styling'],
    }


def build_scene_prompt(scene_id: str, variant_index: int, pose_preference: str = 'balanced') -> str:
    """Build complete shooting plan from scene configuration."""
    if scene_id not in SCENE_CONFIGS:
        raise ValueError('场景不存在')
    if type(variant_index) is not int or not 0 <= variant_index < 3:
        raise ValueError('拍摄方案序号无效')
    if not isinstance(pose_preference, str) or pose_preference not in POSE_MODIFIERS:
        raise ValueError('姿势偏好无效')

    scene = SCENE_CONFIGS[scene_id]
    prompt = (
        f"{scene['name']}：{scene['description']}。"
        f"光线：{scene['lighting']}。"
        f"构图：{scene['composition']}。"
        f"氛围：{scene['mood']}。"
        f"搭配：{scene['styling']}。"
        f"本张拍法：{scene['variants'][variant_index]}"
    )
    modifier = POSE_MODIFIERS[pose_preference]
    if modifier:
        prompt += f"。姿势要求：{modifier}与本张拍法冲突时优先遵守此要求，保证商品完整可见。"
    return prompt


POSE_MODIFIERS = {
    'frontal': '以正面或接近正面的角度展示，',
    'side': '以侧身或侧面角度展示，',
    'dynamic': '以走动、转身等动态姿势展示，',
    'balanced': '',
}


# Styling presets for outfit coordination
STYLING_PRESETS = {
    'minimal': {
        'name': '极简搭配',
        'description': '低调纯色单品，不抢商品重心',
        'guidance': '搭配单品使用纯色或极简款式，颜色克制（黑白灰米驼等基础色），无图案无品牌标识，不遮挡商品关键部位。',
    },
    'coordinated': {
        'name': '协调搭配',
        'description': '色彩呼应，增强整体感',
        'guidance': '搭配单品色彩与商品协调呼应，可使用相近色或对比色，但饱和度和明度要让商品保持视觉中心，无抢眼图案。',
    },
    'seasonal': {
        'name': '应季搭配',
        'description': '符合商品季节感的完整造型',
        'guidance': '根据商品的面料和款式判断季节，搭配相应的应季单品（如夏季配凉鞋短裤，冬季配外套长裤），整体协调但商品是焦点。',
    },
}


def get_styling_guidance(preset: str = 'minimal') -> str:
    """Get styling guidance for outfit coordination."""
    if preset not in STYLING_PRESETS:
        preset = 'minimal'
    config = STYLING_PRESETS[preset]
    return config['guidance']


def build_auto_shooting_plan(index: int, style: str = 'auto', pose_preference: str = 'balanced') -> str:
    """Return one distinct plan for a no-reference output in a group of up to three.

    For backward compatibility. New code should use build_scene_prompt().
    """
    if type(index) is not int or not 0 <= index < len(AUTO_SHOOTING_PLANS):
        raise ValueError('拍摄方案序号无效')
    if pose_preference not in POSE_MODIFIERS:
        pose_preference = 'balanced'

    if style == 'auto':
        name, description = AUTO_SHOOTING_PLANS[index]
    elif style in STYLED_SHOOTING_PLANS:
        name = {'studio': '电商棚拍', 'lookbook': '城市 Lookbook', 'lifestyle': '室内生活方式'}[style]
        description = STYLED_SHOOTING_PLANS[style][index]
    else:
        raise ValueError('拍摄方向无效')

    modifier = POSE_MODIFIERS[pose_preference]
    if modifier:
        description = modifier + description

    return f'{name}：{description}'
