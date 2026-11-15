"""姿势变化系统使用示例"""
from pose_variation import (
    build_pose_variation_prompt,
    get_pose_set_summary,
    POSE_LIBRARY
)


def example_basic_usage():
    """基础使用示例：生成4张姿势照片"""
    print("=== 示例1: 生成4张姿势照片 ===\n")

    pose_count = 4

    # 查看姿势规划
    summary = get_pose_set_summary(pose_count)
    print(f"姿势集规划: {pose_count}张")
    print(f"角度分布: {summary['angle_distribution']}")
    print(f"动作分布: {summary['action_type_distribution']}\n")

    # 生成每张照片的提示词
    for i in range(pose_count):
        prompt = build_pose_variation_prompt(
            pose_count=pose_count,
            pose_index=i,
            use_structured=True
        )
        print(f"第{i+1}张照片提示词:")
        print(prompt)
        print("\n" + "="*60 + "\n")


def example_compare_modes():
    """对比结构化模式和兼容模式"""
    print("=== 示例2: 对比两种模式 ===\n")

    # 结构化模式
    structured = build_pose_variation_prompt(
        pose_count=4,
        pose_index=0,
        use_structured=True
    )

    # 兼容模式
    legacy = build_pose_variation_prompt(
        pose_count=4,
        pose_index=0,
        use_structured=False
    )

    print("结构化模式 (use_structured=True):")
    print("-" * 60)
    print(structured)
    print("\n")

    print("兼容模式 (use_structured=False):")
    print("-" * 60)
    print(legacy)
    print("\n")


def example_different_set_sizes():
    """展示不同数量的姿势集规划"""
    print("=== 示例3: 不同数量姿势集的规划策略 ===\n")

    for count in [4, 6, 8]:
        summary = get_pose_set_summary(count)

        print(f"{count}张姿势集:")
        print(f"  角度分布: {summary['angle_distribution']}")
        print(f"  动作分布: {summary['action_type_distribution']}")
        print(f"  取景分布: {summary['framing_distribution']}")

        print("  姿势详情:")
        for pose_info in summary['poses']:
            print(f"    {pose_info['index']+1}. {pose_info['angle']} - "
                  f"{pose_info['action_type']} - {pose_info['framing']}")
        print()


def example_inspect_pose_library():
    """查看姿势库内容"""
    print("=== 示例4: 姿势库内容 ===\n")

    print(f"姿势库共有 {len(POSE_LIBRARY)} 个姿势定义\n")

    for i, pose in enumerate(POSE_LIBRARY):
        print(f"{i}. [{pose['angle']}] [{pose['action_type']}] [{pose['camera_framing']}]")
        print(f"   身体: {pose['body_action']}")
        print(f"   手部: {pose['hand_action']}")
        print(f"   重点: {pose['visibility_focus']}")
        print()


if __name__ == '__main__':
    print("\n姿势变化系统 - 使用示例\n")
    print("="*60)
    print()

    # 运行示例
    example_basic_usage()
    print("\n" + "="*60 + "\n")

    example_compare_modes()
    print("\n" + "="*60 + "\n")

    example_different_set_sizes()
    print("\n" + "="*60 + "\n")

    example_inspect_pose_library()
