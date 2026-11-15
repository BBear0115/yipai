#!/usr/bin/env python3
"""端到端测试：验证前端参数到后端的完整传递"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.workflows.remake import normalize_remake_config
from backend.workflows.shooting_plans import build_auto_shooting_plan


def test_pose_preference_validation():
    """测试姿势偏好参数验证"""
    print("测试 1: 姿势偏好参数验证")

    # 有效的姿势偏好
    valid_prefs = ['balanced', 'frontal', 'dynamic', 'side']
    for pref in valid_prefs:
        config = normalize_remake_config({
            'clothing_mode': 'multi',
            'output_count': 3,
            'shooting_style': 'auto',
            'pose_preference': pref,
            'instruction': ''
        })
        assert config['pose_preference'] == pref, f"姿势偏好 {pref} 未正确保存"
        print(f"  ✓ 姿势偏好 '{pref}' 验证通过")

    # 默认值测试
    config = normalize_remake_config({
        'clothing_mode': 'multi',
        'output_count': 3,
        'shooting_style': 'auto',
        'instruction': ''
    })
    assert config['pose_preference'] == 'balanced', "默认姿势偏好应为 'balanced'"
    print("  ✓ 默认姿势偏好 'balanced' 验证通过")

    # 无效的姿势偏好
    try:
        normalize_remake_config({
            'clothing_mode': 'multi',
            'output_count': 3,
            'shooting_style': 'auto',
            'pose_preference': 'invalid',
            'instruction': ''
        })
        assert False, "应该拒绝无效的姿势偏好"
    except ValueError as e:
        assert '姿势偏好无效' in str(e)
        print("  ✓ 无效姿势偏好正确拒绝")

    print("✅ 测试 1 通过\n")


def test_shooting_plan_generation():
    """测试拍摄方案生成包含姿势偏好"""
    print("测试 2: 拍摄方案生成")

    # 测试不同姿势偏好的方案生成
    styles = ['auto', 'studio', 'lookbook', 'lifestyle']
    preferences = ['balanced', 'frontal', 'dynamic', 'side']

    for style in styles:
        for pref in preferences:
            for index in range(3):
                plan = build_auto_shooting_plan(index, style, pref)
                assert isinstance(plan, str) and len(plan) > 0, "方案不应为空"

                # 验证非平衡模式包含姿势修饰
                if pref != 'balanced':
                    modifiers = {
                        'frontal': '以正面或接近正面的角度展示',
                        'side': '以侧身或侧面角度展示',
                        'dynamic': '以走动、转身等动态姿势展示'
                    }
                    assert modifiers[pref] in plan, f"方案应包含 {pref} 的姿势修饰"

                print(f"  ✓ {style} + {pref} (第{index+1}张): {plan[:50]}...")

    print("✅ 测试 2 通过\n")


def test_complete_workflow_config():
    """测试完整的工作流配置"""
    print("测试 3: 完整工作流配置")

    # 模拟前端发送的完整配置
    frontend_config = {
        'clothing_mode': 'multi',
        'output_count': 3,
        'shooting_style': 'lookbook',
        'pose_preference': 'dynamic',
        'instruction': '通勤风格，搭配黑色皮鞋'
    }

    config = normalize_remake_config(frontend_config)

    # 验证所有参数都正确传递
    assert config['clothing_mode'] == 'multi', "服装模式未正确传递"
    assert config['output_count'] == 3, "生成数量未正确传递"
    assert config['shooting_style'] == 'lookbook', "拍摄风格未正确传递"
    assert config['pose_preference'] == 'dynamic', "姿势偏好未正确传递"
    assert config['instruction'] == '通勤风格，搭配黑色皮鞋', "搭配要求未正确传递"

    print("  ✓ 所有参数正确传递到后端配置")
    print(f"  配置内容: {config}")
    print("✅ 测试 3 通过\n")


def test_model_selection_parameters():
    """测试模特选择参数"""
    print("测试 4: 模特选择参数")

    # 测试预设模特
    config = normalize_remake_config({
        'clothing_mode': 'single',
        'output_count': 2,
        'model_source': 'preset',
        'shooting_style': 'studio',
        'pose_preference': 'frontal',
        'instruction': ''
    })
    assert config['model_source'] == 'preset', "预设模特参数未正确传递"
    print("  ✓ 预设模特参数验证通过")

    # 测试作品模特
    config = normalize_remake_config({
        'clothing_mode': 'single',
        'output_count': 1,
        'model_source': 'work',
        'shooting_style': 'lifestyle',
        'pose_preference': 'side',
        'instruction': ''
    })
    assert config['model_source'] == 'work', "作品模特参数未正确传递"
    print("  ✓ 作品模特参数验证通过")

    print("✅ 测试 4 通过\n")


if __name__ == '__main__':
    print("=" * 60)
    print("前端到后端参数传递集成测试")
    print("=" * 60 + "\n")

    try:
        test_pose_preference_validation()
        test_shooting_plan_generation()
        test_complete_workflow_config()
        test_model_selection_parameters()

        print("=" * 60)
        print("✅ 所有测试通过！前端到后端参数传递正常工作。")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
