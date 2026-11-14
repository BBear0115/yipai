"""商品精修工作流"""

def build_product_retouch_prompt(mode: str, user_instruction: str = "") -> str:
    """
    生成商品精修提示词

    mode: 'faithful-retouch' | 'marketplace-white' | 'studio-polish'
    """

    if mode == 'faithful-retouch':
        base = """图1是需要精修的商品照片。

任务：进行保真精修，去除瑕疵但保持商品真实质感。

精修规则：
1. 去除：污渍、折痕、线头、灰尘、明显瑕疵
2. 优化：轻微提亮、色彩校正、对比度调整
3. 保留：商品原始材质、纹理、磨损感（如果是设计感）
4. 不要：过度修图、不真实的光泽、HDR效果

保持商品的真实性和可信度。"""

    elif mode == 'marketplace-white':
        base = """图1是需要制作电商白底图的商品照片。

任务：生成纯白色背景的电商商品图。

规则：
1. 背景：纯白色(#FFFFFF)，无阴影、无渐变
2. 商品：居中放置，完整展示
3. 精修：去除瑕疵、提亮商品
4. 光线：均匀明亮，无强烈阴影
5. 边缘：清晰、自然抠图效果

符合电商平台白底图要求。"""

    else:  # studio-polish
        base = """图1是需要精品抛光的商品照片。

任务：进行专业级精修，提升商品质感到商业大片水准。

精修规则：
1. 深度去瑕：所有瑕疵、污渍、折痕
2. 质感提升：增强材质光泽、面料纹理、细节清晰度
3. 光影优化：柔和高光、自然阴影、立体感
4. 色彩增强：饱和度适度提升、色彩层次丰富
5. 保持真实：不要过度到失真

输出专业商业摄影质量。"""

    if user_instruction:
        base += f"\n\n特殊要求：{user_instruction}"

    return base


def build_material_enhancement_prompt(material_type: str) -> str:
    """
    生成材质增强提示词

    material_type: 'silk' | 'denim' | 'leather' | 'knit' | 'cotton' | 'wool'
    """

    materials = {
        'silk': {
            'name': '丝绸',
            'features': '光泽流动、柔软垂坠、细腻质感、丝滑触感'
        },
        'denim': {
            'name': '牛仔',
            'features': '织物纹理、磨白效果、做旧质感、硬挺廓形'
        },
        'leather': {
            'name': '皮革',
            'features': '皮革纹理、自然光泽、柔软触感、高级质感'
        },
        'knit': {
            'name': '针织',
            'features': '编织纹理、柔软蓬松、温暖触感、透气质感'
        },
        'cotton': {
            'name': '棉质',
            'features': '自然肌理、柔软亲肤、透气舒适、天然质感'
        },
        'wool': {
            'name': '羊毛',
            'features': '毛织纹理、温暖厚实、自然蓬松、保暖质感'
        }
    }

    mat = materials.get(material_type, materials['cotton'])

    return f"""图1是 {mat['name']} 材质的商品照片。

任务：增强 {mat['name']} 材质的质感表现，保持真实自然。

材质增强规则：
1. 核心特征：突出 {mat['features']}
2. 细节增强：放大材质特有的纹理和光泽
3. 光影优化：增强材质对光线的自然反应
4. 色彩调整：符合 {mat['name']} 材质的自然色调
5. 保持真实：不要过度到失真或虚假

输出：{mat['name']} 材质的高质感商业照片。"""
