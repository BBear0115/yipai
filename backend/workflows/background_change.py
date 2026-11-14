"""Scene definitions and prompt construction for background replacement."""


SCENES = {
    'white': {
        'description': '纯白色无缝摄影棚背景，明亮干净的电商白底，柔和自然落影',
        'reference_url': None,
    },
    'studio_gray': {
        'description': '浅灰色无缝摄影棚背景，柔和棚拍光，低对比度商业人像摄影',
        'reference_url': None,
    },
    'outdoor_street': {
        'description': '浪漫城市街道背景，真实街拍空间、柔和自然光和轻微景深',
        'reference_url': 'https://vasthk.oss-cn-hongkong.aliyuncs.com/site-assets/original/remote/i.ibb.co/V004GhLP/bg-romantic-street-85e09fa3af.jpg',
    },
    'indoor_minimal': {
        'description': '明亮简约的室内空间，白墙、自然窗光和克制的生活方式氛围',
        'reference_url': None,
    },
    'beach': {
        'description': '开阔海边与礁石海岸，清爽自然天光和真实度假氛围',
        'reference_url': 'https://vasthk.oss-cn-hongkong.aliyuncs.com/site-assets/original/remote/i.ibb.co/7JzNFYD3/bg-reef-seaside-d91ba8f17d.jpg',
    },
    'cafe': {
        'description': '有格调的咖啡馆庭院，暖调自然光、真实室内外空间和生活方式氛围',
        'reference_url': 'https://vasthk.oss-cn-hongkong.aliyuncs.com/site-assets/original/remote/i.ibb.co/Jw2f4PcC/bg-cafe-courtyard-26119de07a.jpg',
    },
}


def background_reference_url(scene_type: str) -> str | None:
    """Return a curated scene reference when the selected scene has one."""
    if scene_type not in SCENES:
        raise ValueError(f'Unsupported scene_type: {scene_type}. Must be one of {list(SCENES)}')
    return SCENES[scene_type]['reference_url']


def build_background_change_prompt(scene_type: str) -> str:
    """Describe a scene replacement while protecting the source subject."""
    if scene_type not in SCENES:
        raise ValueError(f'Unsupported scene_type: {scene_type}. Must be one of {list(SCENES)}')
    scene_desc = SCENES[scene_type]['description']
    scene_reference_rule = (
        '图2只用于参考新背景的环境、空间、地面、光线和色彩；忽略图2中的人物、衣服、包、配饰和姿势。'
        if SCENES[scene_type]['reference_url'] else
        '没有场景参考图，只按文字描述生成新背景。'
    )

    return f"""【只换背景硬规则】
图1是唯一的人物、服装和构图来源。任务是把图1真实融入以下新场景：{scene_desc}。
{scene_reference_rule}

人物锁定：保留图1同一张脸、发型、肤色、身体比例、表情、视线、姿势、手部和身体位置，不换人、不增减人物。
服装保真：严格保留图1服装的品类、版型、固有色、图案、文字/logo、纽扣、口袋、拉链、面料纹理、穿搭层次与配饰；不得改款、换色或套风格滤镜。
画幅锁定：保持图1原始画幅比例、镜头距离、主体大小、人物在画面中的位置和可见身体范围。不得扩图、缩小人物、裁掉原图已可见的人体或服装，也不得补出裁切外的人体。
背景替换：只移除图1原背景并替换为{scene_desc}。图1以外的参考只用于场景，不得复制其中的人物、服饰或姿势。
真实融合：让人物自然处于新场景中；按场景匹配环境光、色温、曝光、对比度、透视和景深，在人物边缘、头发、袖口、衣摆及脚下生成自然融合与接触阴影。避免白边、硬切边、漂浮感和贴纸感。环境光不得改变服装固有色和面料质感。
商业摄影：写实自然的服装商业照片，人物清晰，背景不过度抢眼，肤色真实，肢体和手指自然。不要添加文字、水印或额外人物。"""
