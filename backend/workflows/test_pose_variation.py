"""测试姿势变化系统"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflows.pose_variation import (
    build_pose_variation_prompt,
    get_pose_set_summary,
    select_poses_for_set,
    POSE_LIBRARY
)


def test_pose_library_structure():
    """测试姿势库结构完整性"""
    print("=== 测试姿势库结构 ===")
    print(f"姿势库总数: {len(POSE_LIBRARY)}")

    required_keys = {'angle', 'action_type', 'body_action', 'hand_action',
                     'camera_framing', 'visibility_focus'}

    for i, pose in enumerate(POSE_LIBRARY):
        assert set(pose.keys()) == required_keys, f"姿势 {i} 缺少必需字段"
        assert pose['angle'] in ['正面', '侧面', '背面', '细节'], f"姿势 {i} 角度无效"
        assert pose['action_type'] in ['站姿', '走动', '坐姿', '动态'], f"姿势 {i} 动作类型无效"
        assert pose['camera_framing'] in ['全身', '七分身', '半身', '特写'], f"姿势 {i} 取景无效"

    print("✓ 姿势库结构验证通过\n")


def test_pose_selection():
    """测试姿势选择策略"""
    print("=== 测试姿势选择策略 ===")

    for count in [4, 6, 8]:
        selected = select_poses_for_set(count)
        print(f"\n{count}张照片选择的姿势索引: {selected}")

        assert len(selected) == count, f"{count}张照片应选择{count}个姿势"
        assert len(set(selected)) == count, f"{count}张照片不应有重复姿势"
        assert all(0 <= idx < len(POSE_LIBRARY) for idx in selected), "索引超出范围"

        # 检查多样性
        poses = [POSE_LIBRARY[i] for i in selected]
        angles = set(p['angle'] for p in poses)
        action_types = set(p['action_type'] for p in poses)

        print(f"  角度覆盖: {angles}")
        print(f"  动作类型覆盖: {action_types}")

        # 至少应该有2种不同角度
        assert len(angles) >= 2, f"{count}张照片应覆盖至少2种角度"

    print("\n✓ 姿势选择策略验证通过\n")


def test_prompt_generation():
    """测试提示词生成"""
    print("=== 测试提示词生成 ===")

    # 测试结构化模式
    prompt = build_pose_variation_prompt(pose_count=4, pose_index=0, use_structured=True)
    print("\n结构化姿势提示词示例（4张中的第1张）:")
    print("-" * 60)
    print(prompt)
    print("-" * 60)

    assert "图1是唯一人物和服装参考" in prompt
    assert "第 1 张独立成片" in prompt
    assert "镜头取景" in prompt  # 结构化姿势特有
    assert len(prompt) > 100

    # 测试兼容模式
    legacy_prompt = build_pose_variation_prompt(pose_count=4, pose_index=0, use_structured=False)
    print("\n兼容模式提示词示例:")
    print("-" * 60)
    print(legacy_prompt)
    print("-" * 60)

    assert "正面自然站立" in legacy_prompt
    assert "镜头取景" not in legacy_prompt  # 兼容模式不包含结构化字段

    print("\n✓ 提示词生成验证通过\n")


def test_pose_set_summary():
    """测试姿势集摘要"""
    print("=== 测试姿势集摘要 ===")

    for count in [4, 6, 8]:
        summary = get_pose_set_summary(count)
        print(f"\n{count}张姿势集摘要:")
        print(f"  角度分布: {summary['angle_distribution']}")
        print(f"  动作类型分布: {summary['action_type_distribution']}")
        print(f"  取景分布: {summary['framing_distribution']}")
        print(f"  姿势列表: {len(summary['poses'])} 个")

        assert summary['total_count'] == count
        assert len(summary['poses']) == count
        assert sum(summary['angle_distribution'].values()) == count
        assert sum(summary['action_type_distribution'].values()) == count

    print("\n✓ 姿势集摘要验证通过\n")


def test_edge_cases():
    """测试边界条件"""
    print("=== 测试边界条件 ===")

    # 测试无效的 pose_count
    try:
        build_pose_variation_prompt(pose_count=5, pose_index=0)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        print(f"✓ 正确拒绝无效 pose_count: {e}")

    # 测试无效的 pose_index
    try:
        build_pose_variation_prompt(pose_count=4, pose_index=4)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        print(f"✓ 正确拒绝无效 pose_index: {e}")

    # 测试负数索引
    try:
        build_pose_variation_prompt(pose_count=4, pose_index=-1)
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        print(f"✓ 正确拒绝负数索引: {e}")

    print("\n✓ 边界条件验证通过\n")


def test_diversity_in_sets():
    """测试姿势集的多样性"""
    print("=== 测试姿势集多样性 ===")

    for count in [4, 6, 8]:
        selected = select_poses_for_set(count)
        poses = [POSE_LIBRARY[i] for i in selected]

        angles = [p['angle'] for p in poses]
        action_types = [p['action_type'] for p in poses]
        framings = [p['camera_framing'] for p in poses]

        print(f"\n{count}张姿势集:")
        print(f"  角度: {angles}")
        print(f"  动作: {action_types}")
        print(f"  取景: {framings}")

        # 验证多样性指标
        unique_angles = len(set(angles))
        unique_actions = len(set(action_types))

        assert unique_angles >= 2, f"{count}张应包含至少2种角度"

        if count >= 6:
            assert unique_actions >= 2, f"{count}张应包含至少2种动作类型"

        # 不应该有完全相同的姿势
        assert len(selected) == len(set(selected)), "不应有重复姿势"

    print("\n✓ 多样性验证通过\n")


if __name__ == '__main__':
    print("开始测试姿势变化系统\n")

    test_pose_library_structure()
    test_pose_selection()
    test_prompt_generation()
    test_pose_set_summary()
    test_edge_cases()
    test_diversity_in_sets()

    print("=" * 60)
    print("所有测试通过！")
    print("=" * 60)
