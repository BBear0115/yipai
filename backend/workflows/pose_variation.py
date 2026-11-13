"""Pose variation workflow for Yipai."""


def build_pose_variation_prompt(pose_count: int) -> str:
    """
    Generate pose variation prompt for creating multiple poses from one image.

    Args:
        pose_count: Number of poses to generate (4, 6, or 8)

    Returns:
        Formatted prompt string for gpt-image-2.5-flare model
    """
    if pose_count not in (4, 6, 8):
        raise ValueError('pose_count must be 4, 6, or 8')

    layout = '2x2' if pose_count == 4 else '2x3' if pose_count == 6 else '3x3'

    return f"""图1是唯一的人物和服装参考。

任务：生成 {pose_count} 个不同姿势的商业时装大片，展示在一张图片的网格布局中。

【核心约束】
1. 人物身份锁定：
   - 必须保持图1同一个人（同一张脸、同一脸型、同一年龄、同一肤色）
   - 同一性别表达、同一身体比例、同一头身比
   - 不要换脸、不要变成其他人

2. 服装保真规则：
   - 锁定图1服装的版型、颜色、图案、面料纹理
   - 保留所有细节：纽扣、口袋、拉链、Logo、文字
   - 只有姿势变化导致的自然褶皱，不改变服装结构

3. 姿势设计规则：
   - {pose_count} 个姿势要有明显差异但保持商业摄影风格
   - 可选姿势：站立直视、侧身45度、回眸、行走、托腮、交叉手臂
   - 每个姿势展示服装的不同角度（正面、侧面、背面）
   - 表情自然变化：微笑、沉静、自信

4. 画面质量：
   - 保持图1的曝光、对比度、色温、肤色明暗
   - 统一背景、统一光线、统一色调
   - 商业摄影质感，不要HDR、不要过度锐化

5. 输出布局：
   - 生成 {pose_count} 宫格布局（{layout}）
   - 每个格子是完整的人物照片
   - 不要边框、编号、文字标注

图1是商品上身效果图。"""
