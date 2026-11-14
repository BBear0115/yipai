"""Prompt construction for independent pose-variation photos."""


POSES = (
    '正面自然站立，双手自然垂放',
    '身体向一侧转约四十五度，自然看向镜头',
    '自然向前迈步，呈现轻松行走瞬间',
    '优雅坐姿，完整清楚展示服装',
    '侧身站立，回头自然看向镜头',
    '正面站立，一只手轻放腰侧',
    '身体微转，呈现服装侧面和轮廓',
    '轻松站姿，微微转向镜头并自然微笑',
)


def build_pose_variation_prompt(pose_count: int, pose_index: int = 0) -> str:
    """Describe one photo in a pose set, keeping the source identity and outfit."""
    if pose_count not in (4, 6, 8):
        raise ValueError('pose_count must be 4, 6, or 8')
    if not isinstance(pose_index, int) or not 0 <= pose_index < pose_count:
        raise ValueError('pose_index must identify a pose in the selected set')

    return f"""图1是唯一人物和服装参考。生成这组姿势中的第 {pose_index + 1} 张独立成片。

姿势：{POSES[pose_index]}。

只输出一张完整的竖版商业时装照片。不要拼图、宫格、分栏、拼贴、边框、编号或文字。
保持图1中的同一人物、脸部身份、年龄、肤色和身体比例；严格保留服装的款式、颜色、图案、面料和所有细节，包括口袋、纽扣、拉链、Logo 与文字。
服装只出现姿势带来的自然褶皱，不改变服装结构。背景、光线和色调延续图1。
人物完整清晰地展示服装，肢体自然，不添加原图没有的帽子、包、首饰或其他配饰。"""
