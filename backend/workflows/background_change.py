"""Background change workflow for Yipai."""


def build_background_change_prompt(scene_type: str) -> str:
    """
    Generate background change prompt for replacing the background scene.

    Args:
        scene_type: Type of background scene to apply.
                   Supported: 'white', 'studio_gray', 'outdoor_street',
                   'indoor_minimal', 'beach', 'cafe'

    Returns:
        Formatted prompt string for gpt-image-2.5-flare model
    """
    scenes = {
        'white': '纯白色摄影背景，无阴影，干净商业电商白底图',
        'studio_gray': '浅灰色摄影棚背景，柔和顶光，商业产品照',
        'outdoor_street': '城市街道背景，自然光，时尚街拍风格',
        'indoor_minimal': '简约室内空间，明亮自然光，北欧风格',
        'beach': '海边沙滩背景，阳光明媚，度假风格',
        'cafe': '咖啡馆室内，温暖光线，生活方式场景'
    }

    if scene_type not in scenes:
        raise ValueError(f'Unsupported scene_type: {scene_type}. '
                        f'Must be one of {list(scenes.keys())}')

    scene_desc = scenes[scene_type]

    return f"""图1是唯一的人物和服装参考。

任务：保持图1的人物和服装完全不变，只更换背景场景为：{scene_desc}

【核心约束】
1. 人物保持规则：
   - 完整保留图1人物的脸部、身体、姿势、表情
   - 锁定肤色、发型、身体比例
   - 人物位置和大小与图1相似

2. 服装保持规则：
   - 完整保留图1服装的颜色、图案、版型、所有细节
   - 纽扣、口袋、拉链、Logo、文字保持一致
   - 不改变服装任何部分

3. 背景更换规则：
   - 新背景：{scene_desc}
   - 光线与新场景协调
   - 人物与背景融合自然（阴影、反光、景深）
   - 保持商业摄影质感

4. 画面质量：
   - 保持高质量商业摄影标准
   - 曝光准确、色彩自然
   - 人物清晰、背景合理虚化

图1是需要换背景的商品上身照片。"""
