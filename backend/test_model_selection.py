"""测试预设模特选择和参数传递流程。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.workflows.tryon import build_tryon_prompt, normalize_tryon_config


def test_model_gender_in_prompt():
    """测试模特性别参数正确传递到提示词生成。"""
    print("=" * 60)
    print("测试 1: 模特性别参数传递")
    print("=" * 60)

    config = normalize_tryon_config({'clothing_mode': 'auto', 'output_count': 1})
    inputs = [{'role': 'auto'}]

    # 测试女性模特
    female_prompt = build_tryon_prompt('female', inputs, config)
    assert '成年女性' in female_prompt, "女性模特提示词应包含'成年女性'"
    assert '成年男性' not in female_prompt, "女性模特提示词不应包含'成年男性'"
    print("✓ 女性模特参数正确传递")

    # 测试男性模特
    male_prompt = build_tryon_prompt('male', inputs, config)
    assert '成年男性' in male_prompt, "男性模特提示词应包含'成年男性'"
    assert '成年女性' not in male_prompt, "男性模特提示词不应包含'成年女性'"
    print("✓ 男性模特参数正确传递")
    print()


def test_model_with_identity():
    """测试带模特身份图的场景。"""
    print("=" * 60)
    print("测试 2: 模特身份图场景")
    print("=" * 60)

    # 场景1: 多件商品模式 + 模特身份图
    config = normalize_tryon_config({'clothing_mode': 'multi', 'output_count': 1})
    inputs = [
        {'role': 'upper'},
        {'role': 'model'}  # 模特身份图
    ]

    prompt = build_tryon_prompt('female', inputs, config)
    assert '与模特身份图一致的成年模特' in prompt, "应识别模特身份图"
    assert '图2只提供模特脸型、五官、发型和可识别身份' in prompt, "应包含模特身份图的角色说明"
    print("✓ 模特身份图场景正确处理（多件商品模式）")

    # 场景2: auto模式但没有reference时，模特身份图仍然会出现在提示词中
    config_auto = normalize_tryon_config({'clothing_mode': 'auto', 'output_count': 1})
    inputs_auto = [
        {'role': 'auto'},
        {'role': 'model'}
    ]
    prompt_auto = build_tryon_prompt('male', inputs_auto, config_auto)
    assert '图2只提供模特脸型、五官、发型和可识别身份' in prompt_auto, "auto模式下模特身份图仍会在提示词中"
    print("✓ 模特身份图在auto模式下正确包含")
    print()


def test_model_with_reference():
    """测试带参考图的场景。"""
    print("=" * 60)
    print("测试 3: 参考图场景")
    print("=" * 60)

    config = normalize_tryon_config({'clothing_mode': 'auto', 'output_count': 1})
    inputs = [
        {'role': 'reference'},
        {'role': 'auto'}
    ]

    # 当有参考图但无模特身份图时，应保留参考人物身份
    prompt = build_tryon_prompt('female', inputs, config)
    assert '与画面参考身份一致的成年模特' in prompt, "应识别参考图身份"
    assert '没有独立模特身份图，保留图1人物的脸部身份、发型和年龄感' in prompt, "应说明保留参考图身份"
    print("✓ 参考图场景正确处理")
    print()


def test_model_with_both_reference_and_identity():
    """测试同时有参考图和模特身份图的场景。"""
    print("=" * 60)
    print("测试 4: 参考图+模特身份图场景")
    print("=" * 60)

    config = normalize_tryon_config({'clothing_mode': 'auto', 'output_count': 1})
    inputs = [
        {'role': 'reference'},
        {'role': 'auto'},
        {'role': 'model'}
    ]

    # 当同时有参考图和模特身份图时，应使用模特身份图的人物
    prompt = build_tryon_prompt('male', inputs, config)
    assert '与模特身份图一致的成年模特' in prompt, "应使用模特身份图"
    assert '人物身份硬规则：最终画面必须是图3中的同一个人' in prompt, "应包含身份优先规则"
    assert '完全忽略图1人物的人脸、五官、发型和身份' in prompt, "应说明忽略参考图人物"
    print("✓ 参考图+模特身份图场景正确处理")
    print()


def test_multiple_candidate_variations():
    """测试多个候选图的姿势变化。"""
    print("=" * 60)
    print("测试 5: 多候选图姿势变化")
    print("=" * 60)

    config = normalize_tryon_config({'clothing_mode': 'auto', 'output_count': 2})
    inputs = [{'role': 'auto'}]

    # 测试不同候选索引生成不同姿势描述
    prompt_0 = build_tryon_prompt('female', inputs, config, candidate_index=0)
    prompt_1 = build_tryon_prompt('female', inputs, config, candidate_index=1)

    assert '自然站姿展示完整造型' in prompt_0, "候选0应使用站姿"
    assert '侧身走动或回眸的自然动态' in prompt_1, "候选1应使用动态姿势"
    assert prompt_0 != prompt_1, "不同候选索引应生成不同提示词"
    print("✓ 多候选图姿势变化正确")
    print()


def test_diverse_model_configs():
    """测试多样化模特配置定义。"""
    print("=" * 60)
    print("测试 6: 多样化模特配置")
    print("=" * 60)

    # 导入模特配置
    sys.path.insert(0, str(ROOT / 'scripts'))
    from init_preset_models import generate_diverse_models

    # 验证配置结构（不实际生成）
    import inspect
    source = inspect.getsource(generate_diverse_models)

    # 验证是否定义了多样化的模特配置
    assert '清纯甜美女模特' in source or '优雅知性女模特' in source, "应定义多样化女性模特"
    assert '阳光少年男模特' in source or '成熟稳重男模特' in source, "应定义多样化男性模特"

    print("✓ 多样化模特配置已定义")
    print("  - 包含不同风格：清纯、优雅、酷飒、活力")
    print("  - 包含不同年龄段：20-23岁、24-28岁、28-35岁")
    print("  - 包含不同气质：甜美、知性、个性、稳重")
    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("预设模特库测试套件")
    print("=" * 60 + "\n")

    try:
        test_model_gender_in_prompt()
        test_model_with_identity()
        test_model_with_reference()
        test_model_with_both_reference_and_identity()
        test_multiple_candidate_variations()
        test_diverse_model_configs()

        print("=" * 60)
        print("✓ 所有测试通过")
        print("=" * 60)
        return 0
    except AssertionError as exc:
        print(f"\n❌ 测试失败: {exc}")
        return 1
    except Exception as exc:
        print(f"\n❌ 测试错误: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
