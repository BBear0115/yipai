"""Prompt construction for independent pose-variation photos."""
from typing import TypedDict, Literal, List


# 姿势结构化定义
class PoseSpec(TypedDict):
    """结构化姿势定义"""
    angle: Literal['正面', '侧面', '背面', '细节']
    action_type: Literal['站姿', '走动', '坐姿', '动态']
    body_action: str
    hand_action: str
    camera_framing: Literal['全身', '七分身', '半身', '特写']
    visibility_focus: str


# 姿势库：按类别组织的姿势定义
POSE_LIBRARY: List[PoseSpec] = [
    # 正面站姿组
    {
        'angle': '正面',
        'action_type': '站姿',
        'body_action': '自然站立，身体重心均匀分布',
        'hand_action': '双手自然垂放身体两侧',
        'camera_framing': '全身',
        'visibility_focus': '服装正面完整展示，所有细节清晰可见'
    },
    {
        'angle': '正面',
        'action_type': '站姿',
        'body_action': '直立站姿，身体略微放松',
        'hand_action': '一只手轻放腰侧，另一只手自然垂放',
        'camera_framing': '全身',
        'visibility_focus': '强调服装腰线和整体轮廓'
    },

    # 侧面组
    {
        'angle': '侧面',
        'action_type': '站姿',
        'body_action': '身体向一侧转约四十五度',
        'hand_action': '双手自然下垂或轻放身前',
        'camera_framing': '全身',
        'visibility_focus': '展示服装侧面轮廓和立体剪裁'
    },
    {
        'angle': '侧面',
        'action_type': '站姿',
        'body_action': '侧身站立，上半身微微转向镜头',
        'hand_action': '双手自然摆放',
        'camera_framing': '七分身',
        'visibility_focus': '侧面线条和服装垂坠感'
    },
    {
        'angle': '背面',
        'action_type': '站姿',
        'body_action': '背对镜头站立，头部自然回转看向镜头',
        'hand_action': '双手自然垂放或轻放身侧',
        'camera_framing': '全身',
        'visibility_focus': '服装背面设计、后片细节'
    },

    # 走动组
    {
        'angle': '正面',
        'action_type': '走动',
        'body_action': '自然向前迈步，呈现行走瞬间',
        'hand_action': '双手随步伐自然摆动',
        'camera_framing': '全身',
        'visibility_focus': '服装动态下的垂坠和飘逸感'
    },
    {
        'angle': '侧面',
        'action_type': '走动',
        'body_action': '侧向行走，身体微微前倾',
        'hand_action': '一只手自然前摆，一只手后摆',
        'camera_framing': '全身',
        'visibility_focus': '服装侧面动态效果'
    },

    # 坐姿组
    {
        'angle': '正面',
        'action_type': '坐姿',
        'body_action': '优雅坐姿，背部挺直或微微前倾',
        'hand_action': '双手自然放在腿上或扶持坐具',
        'camera_framing': '七分身',
        'visibility_focus': '坐姿下服装的完整呈现，避免褶皱遮挡'
    },
    {
        'angle': '侧面',
        'action_type': '坐姿',
        'body_action': '侧坐姿态，上身转向镜头',
        'hand_action': '一只手放腿上，一只手扶持',
        'camera_framing': '七分身',
        'visibility_focus': '坐姿侧面服装展示'
    },

    # 动态组
    {
        'angle': '正面',
        'action_type': '动态',
        'body_action': '身体微微转动，呈现自然动势',
        'hand_action': '双手随身体动作自然摆动',
        'camera_framing': '全身',
        'visibility_focus': '服装在自然动作中的表现'
    },
    {
        'angle': '细节',
        'action_type': '站姿',
        'body_action': '放松站立',
        'hand_action': '手部动作突出服装细节（如提起袖口、整理下摆）',
        'camera_framing': '半身',
        'visibility_focus': '重点展示服装关键细节：面料纹理、工艺、装饰'
    },
]


# 兼容性：保留原有的简单描述格式
LEGACY_POSES = (
    '正面自然站立，双手自然垂放',
    '身体向一侧转约四十五度，自然看向镜头',
    '自然向前迈步，呈现轻松行走瞬间',
    '优雅坐姿，完整清楚展示服装',
    '侧身站立，回头自然看向镜头',
    '正面站立，一只手轻放腰侧',
    '身体微转，呈现服装侧面和轮廓',
    '轻松站姿，微微转向镜头并自然微笑',
)


def select_poses_for_set(pose_count: int) -> List[int]:
    """
    为指定数量的姿势集选择最佳姿势组合。

    策略：
    - 4张：正面站姿 + 侧面站姿 + 走动 + 背面/坐姿
    - 6张：正面2张 + 侧面2张 + 走动 + 背面/坐姿
    - 8张：覆盖所有主要角度和动作类型

    返回姿势库中的索引列表
    """
    if type(pose_count) is not int:
        raise ValueError('pose_count must be 4, 6, or 8')
    if pose_count == 4:
        # 优先覆盖主要角度：正面、侧面、走动、背面
        return [0, 2, 5, 4]

    elif pose_count == 6:
        # 增加更多角度变化和细节
        return [0, 1, 2, 4, 5, 7]

    elif pose_count == 8:
        # 完整覆盖：多个正面、侧面、背面、走动、坐姿
        return [0, 1, 2, 3, 4, 5, 6, 7]

    else:
        raise ValueError('pose_count must be 4, 6, or 8')


def build_pose_description(pose_spec: PoseSpec) -> str:
    """将结构化姿势定义转换为自然语言描述"""
    return (
        f"{pose_spec['body_action']}，{pose_spec['hand_action']}。"
        f"镜头取景：{pose_spec['camera_framing']}。"
        f"重点：{pose_spec['visibility_focus']}"
    )


def build_pose_variation_prompt(
    pose_count: int,
    pose_index: int = 0,
    use_structured: bool = True
) -> str:
    """
    构建姿势变化的提示词。

    Args:
        pose_count: 姿势集总数（4, 6, 或 8）
        pose_index: 当前姿势索引（0 到 pose_count-1）
        use_structured: 是否使用结构化姿势系统（默认 True）

    Returns:
        完整的提示词字符串
    """
    if type(pose_count) is not int or pose_count not in (4, 6, 8):
        raise ValueError('pose_count must be 4, 6, or 8')
    if type(pose_index) is not int or not 0 <= pose_index < pose_count:
        raise ValueError('pose_index must identify a pose in the selected set')

    # 获取姿势描述
    if use_structured:
        selected_poses = select_poses_for_set(pose_count)
        pose_lib_index = selected_poses[pose_index]
        pose_spec = POSE_LIBRARY[pose_lib_index]
        pose_description = build_pose_description(pose_spec)
    else:
        # 兼容模式：使用原有简单描述
        pose_description = LEGACY_POSES[pose_index]

    return f"""图1是唯一人物和服装参考。生成这组姿势中的第 {pose_index + 1} 张独立成片。

姿势：{pose_description}

只输出一张完整的竖版商业时装照片。不要拼图、宫格、分栏、拼贴、边框、编号或文字。
保持图1中的同一人物、脸部身份、年龄、肤色和身体比例；严格保留服装的款式、颜色、图案、面料和所有细节，包括口袋、纽扣、拉链、Logo 与文字。
服装只出现姿势带来的自然褶皱，不改变服装结构。背景、光线和色调延续图1。
人物完整清晰地展示服装，肢体自然，不添加原图没有的帽子、包、首饰或其他配饰。"""


def get_pose_set_summary(pose_count: int) -> dict:
    """
    获取姿势集的总体规划摘要。

    返回姿势分布统计，用于前端展示或验证。
    """
    if type(pose_count) is not int or pose_count not in (4, 6, 8):
        raise ValueError('pose_count must be 4, 6, or 8')

    selected_indices = select_poses_for_set(pose_count)
    poses = [POSE_LIBRARY[i] for i in selected_indices]

    # 统计各维度分布
    angles = {}
    action_types = {}
    framings = {}

    for pose in poses:
        angles[pose['angle']] = angles.get(pose['angle'], 0) + 1
        action_types[pose['action_type']] = action_types.get(pose['action_type'], 0) + 1
        framings[pose['camera_framing']] = framings.get(pose['camera_framing'], 0) + 1

    return {
        'total_count': pose_count,
        'angle_distribution': angles,
        'action_type_distribution': action_types,
        'framing_distribution': framings,
        'poses': [
            {
                'index': i,
                'angle': pose['angle'],
                'action_type': pose['action_type'],
                'framing': pose['camera_framing']
            }
            for i, pose in enumerate(poses)
        ]
    }
