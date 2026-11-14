"""搭配融图工作流"""

def build_outfit_fusion_prompt(items: list) -> str:
    """
    生成搭配融图提示词

    items = [
        {'role': 'top', 'image_num': 1, 'desc': '白色衬衫'},
        {'role': 'bottom', 'image_num': 2, 'desc': '蓝色牛仔裤'},
        {'role': 'shoes', 'image_num': 3, 'desc': '白色运动鞋'},
        {'role': 'model', 'image_num': 4, 'desc': '模特参考'}
    ]
    """

    outfit_desc = []
    model_ref = None

    for item in items:
        if item['role'] == 'model':
            model_ref = f"图{item['image_num']}"
        else:
            role_name = {
                'top': '上衣',
                'bottom': '下装',
                'shoes': '鞋子',
                'accessory': '配饰'
            }.get(item['role'], '商品')
            outfit_desc.append(f"图{item['image_num']}是{role_name}（{item['desc']}）")

    outfit_list = '\n- '.join(outfit_desc)

    return f"""任务：将多件商品搭配在同一模特身上。

图片角色：
- {outfit_list}
- {model_ref}是模特参考（提供身体、姿势、背景）

【搭配融合规则】
1. 商品保真：
   - 每件商品锁定原图的颜色、图案、版型、细节
   - 纽扣、口袋、Logo、文字保持一致
   - 不改变任何商品特征

2. 模特继承：
   - 使用{model_ref}的身体、姿势、表情、背景
   - 保持{model_ref}的人物身份、肤色、发型
   - 如果{model_ref}有人脸，完整保留其脸部特征

3. 搭配协调：
   - 正确穿戴层级：上衣在外、下装在下、鞋子在脚
   - 服装尺码合身，符合人体比例
   - 颜色搭配和谐，整体风格统一

4. 画面质量：
   - 保持{model_ref}的光线、色调、背景
   - 商业摄影质感
   - 自然融合，无拼接痕迹

输出：完整的搭配上身效果图。"""


def build_product_set_prompt(angles: list) -> str:
    """
    生成商品套图提示词

    angles = ['front', 'side', 'back', 'detail']
    """

    angle_desc = {
        'front': '正面全身照，展示服装整体廓形和正面设计',
        'side': '侧面45度角，展示服装侧面轮廓和立体感',
        'back': '背面照，展示背部设计和细节',
        'detail': '细节特写，展示面料纹理、纽扣、拉链等关键细节'
    }

    angles_text = '\n'.join([f"{i+1}. {angle_desc[a]}" for i, a in enumerate(angles)])
    layout = '2x2' if len(angles) == 4 else '2x3' if len(angles) == 6 else '3x3'

    return f"""图1是商品上身照片。

任务：生成 {len(angles)} 张不同角度的商品套图，在一张图片中以网格布局展示。

角度要求：
{angles_text}

【套图生成规则】
1. 人物与服装一致性：
   - 所有角度保持同一个人、同一张脸
   - 同一套服装、同一颜色图案
   - 锁定服装所有细节（纽扣、口袋、Logo）

2. 角度差异化：
   - 每个角度明确展示对应的视角
   - 镜头距离和构图适应不同角度需求
   - 细节照可以更近，全身照保持完整

3. 统一质量：
   - 同一背景、同一光线、同一色调
   - 商业摄影标准
   - 网格布局清晰整齐

4. 输出布局：
   - {layout} 宫格布局
   - 无边框、无编号文字

生成适合电商展示的商品套图。"""
