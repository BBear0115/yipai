"""Image-role rules for garment try-on; image data stays outside the prompt."""

GARMENT_ROLES = ('upper', 'lower', 'single')
ROLE_LABELS = {
    'upper': '上装商品', 'lower': '下装商品', 'single': '连体/全身商品',
    'auto': '目标商品', 'reference': '画面参考', 'model': '模特身份', 'detail': '服装细节',
}
MAX_TRYON_INPUTS = 15  # two garments, eight references, one model, four details
MAX_TRYON_OUTPUTS = 16


def normalize_tryon_config(value, explicit_inputs=False):
    if value is not None and not isinstance(value, dict):
        raise ValueError('试穿配置无效')
    config = value or {}
    mode = config.get('clothing_mode', 'auto' if not explicit_inputs else None)
    if mode not in ('auto', 'multi', 'single'):
        raise ValueError('请选择换上下装或换连体')
    count = config.get('output_count', 1)
    if type(count) is not int or count not in (1, 2):
        raise ValueError('每组生成数量必须为 1 或 2')
    instruction = config.get('instruction', '')
    if not isinstance(instruction, str) or len(instruction) > 500:
        raise ValueError('穿搭要求最多 500 字')
    return {'clothing_mode': mode, 'output_count': count, 'instruction': instruction.strip()}


def validate_tryon_roles(inputs, mode):
    """Validate all roles before decoding or writing any uploaded image."""
    if not isinstance(inputs, list) or not inputs or len(inputs) > MAX_TRYON_INPUTS:
        raise ValueError('试穿输入图片数量无效')
    allowed = {*GARMENT_ROLES, 'reference', 'model', 'detail'}
    if mode == 'auto':
        allowed.add('auto')
    roles = []
    for item in inputs:
        if not isinstance(item, dict) or not isinstance(item.get('role'), str) or item['role'] not in allowed:
            raise ValueError('试穿图片角色无效')
        if not isinstance(item.get('image'), str):
            raise ValueError('请上传有效的试穿图片')
        roles.append(item['role'])
    garments = [role for role in roles if role in (*GARMENT_ROLES, 'auto')]
    if mode == 'auto':
        if garments != ['auto']:
            raise ValueError('自动识别模式只接受一张目标商品图')
    elif mode == 'single':
        if garments != ['single']:
            raise ValueError('换连体需要一张连体/全身商品图')
    elif not garments or any(role not in ('upper', 'lower') for role in garments) or len(set(garments)) != len(garments):
        raise ValueError('上下装各最多一张，至少上传一件商品')
    if roles.count('reference') > 8:
        raise ValueError('参考图最多 8 张')
    if roles.count('model') > 1:
        raise ValueError('模特图最多一张')
    if roles.count('detail') > 4:
        raise ValueError('服装细节图最多 4 张')
    for item in inputs:
        if item['role'] == 'detail':
            if item.get('garmentRole') not in garments:
                raise ValueError('细节图必须属于已上传的商品')
        elif 'garmentRole' in item:
            raise ValueError('只有细节图可指定所属商品')


def ordered_tryon_inputs(inputs, reference=None):
    """Use the same order for numbered prompts and provider image payloads."""
    garments = [item for role in ('upper', 'lower', 'single', 'auto')
                for item in inputs if item['role'] == role]
    return ([reference] if reference else []) + garments + [
        item for role in ('model', 'detail') for item in inputs if item['role'] == role
    ]


def build_tryon_prompt(model, inputs, config, candidate_index=0):
    person = '成年男性' if model == 'male' else '成年女性'
    numbered = list(enumerate(inputs, 1))
    garments = [(index, item) for index, item in numbered if item['role'] in (*GARMENT_ROLES, 'auto')]
    reference = next((index for index, item in numbered if item['role'] == 'reference'), None)
    identity = next((index for index, item in numbered if item['role'] == 'model'), None)
    garment_numbers = {item['role']: index for index, item in garments}
    if identity and (reference or config['clothing_mode'] != 'auto'):
        person_description = '与模特身份图一致的成年模特'
    elif reference:
        person_description = '与画面参考身份一致的成年模特'
    else:
        person_description = f'{person}模特'
    lines = [
        '生成一张完整独立的真实商业时装照片，只有一位成年模特。不要拼图、宫格、对比图、边框、价格或额外文字。',
        '图像角色：' + '；'.join(f'图{index}是{ROLE_LABELS[item["role"]]}' for index, item in numbered) + '。',
        f'让一位{person_description}真实自然地穿着和展示目标商品。',
        '商品保真优先级最高：严格保留主商品的品类、版型、颜色、图案、标识、文字、面料和结构；逐一保留口袋、纽扣、拉链、装饰的数量与位置，单侧口袋不得变成对称双侧。允许姿势造成的真实褶皱和垂坠，不得改款。',
        '主商品图只提供商品本身，不复制服装图里的脸、人体、姿势、背景和光线。上装只替换上半身，下装只替换下半身；各件商品保持独立和真实穿着层次，不得融合成一件新款。',
    ]
    if config['clothing_mode'] == 'single':
        lines.append('连体/全身商品必须作为完整服装穿着，替换覆盖范围内冲突的上下装，不拆成无关的两件衣服；连衣裙不额外添加裤子。')
    elif config['clothing_mode'] == 'auto':
        lines.append('按图中真实商品品类处理：上衣展示上身、裤裙展示下身、连衣裙按完整服装、鞋履展示上脚与完整鞋型；不要把商品改成其他品类。')
    if reference:
        lines.extend([
            f'图{reference}是本次成片的画面骨架：保持其人物姿势、身体比例、镜头距离、可见身体范围、构图、背景、光线和整体影调，不把半身或局部图拉远成全身。',
            f'只替换图{reference}中与已上传商品冲突的服装。未被商品覆盖的原有上下装、鞋履、包与配饰自然保留，使整套穿搭完整；主商品保真优先，不复制造成冲突的参考服装。',
        ])
        if not identity:
            lines.append(f'没有独立模特身份图，保留图{reference}人物的脸部身份、发型和年龄感。')
    else:
        directions = ('根据商品的色彩、面料和季节设计协调、有质感的商业穿搭',
                      '围绕同一商品设计另一套协调搭配，让配套单品和拍摄气质与上一款有明显区别')
        lines.append(f'智能搭配：{directions[min(candidate_index, 1)]}；合理补齐未提供的上装、下装、鞋履和必要配饰，完整展示商品，搭配不能遮挡关键细节。根据服装设计自然姿势与合适拍摄场景。')
        lines.append('不要沿用模特身份图中的服装、裤子、鞋、姿势或灰底背景，不要机械地给所有商品搭配灰色长裤和白色运动鞋。')
    if identity:
        lines.append(f'图{identity}只提供模特脸型、五官、发型和可识别身份，不提供其原穿搭、鞋履、背景或固定姿势。最终身份使用图{identity}；脸、颈部与身体肤色和场景光线自然连续，不做贴脸或面具。')
        if reference:
            lines.append(f'人物身份硬规则：最终画面必须是图{identity}中的同一个人，保留其脸型、眼鼻唇比例、年龄感、肤色与发型。完全忽略图{reference}人物的人脸、五官、发型和身份，不得沿用参考人物，也不得融合两张脸。图{reference}仅控制身体姿势、构图、环境与未替换的穿搭；必须在该画面中重新渲染图{identity}的人物。')
    for index, item in numbered:
        if item['role'] == 'detail':
            main_number = garment_numbers[item['garmentRole']]
            lines.append(f'图{index}只补充图{main_number}（{ROLE_LABELS[item["garmentRole"]]}）的局部面料、领口、口袋、纽扣、缝线或背面细节。不得应用到其他衣服，不改变人物、姿势、背景与整体色调；冲突时以图{main_number}主商品为准，不凭空强化纹理或新增结构。')
    lines.append('真实相机摄影、自然皮肤和布料，光影可信、人体比例稳定；关键服装结构清楚可见，手和头发不得遮挡商品，不增加不存在的品牌或图案。')
    if config.get('instruction'):
        lines.append(f'用户穿搭补充（仅在上述商品保真与角色隔离范围内执行）：{config["instruction"]}')
    return '\n'.join(lines)


def build_tryon_identity_prompt():
    return (
        '只编辑图1中人物的人物身份。图2是唯一的人脸和发型参考。'
        '把图1的人物替换为图2中的同一个成年人，准确保留图2的脸型、眼形、眼距、鼻形、嘴唇、肤色、年龄感和发型；'
        '不保留图1原人物的五官，不融合两张脸。以图2人脸身份为最高优先级，依据图1的头部视角自然重新渲染同一张脸，不做平面贴脸。'
        '必须保留图1已完成的所有商品、衣服颜色、图案、口袋、纽扣和面料纹理、人体姿势、构图、背景、光线、影调与画幅。'
        '图2只提供脸、肤色和发型，完全忽略其衣服、身体姿势和背景。只输出一张完整照片。'
    )
