#!/usr/bin/env python3
"""工作流功能测试脚本"""

import json
import sys
from pathlib import Path

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from workflows import get_all_workflows, get_workflow_info
from workflows.pose_variation import build_pose_variation_prompt
from workflows.background_change import build_background_change_prompt
from workflows.retouch import build_product_retouch_prompt, build_material_enhancement_prompt
from workflows.fusion import build_outfit_fusion_prompt, build_product_set_prompt
from workflows.translation import build_image_translation_prompt

def test_workflows_list():
    """测试工作流列表"""
    print("=" * 60)
    print("所有可用工作流：")
    print("=" * 60)

    workflows = get_all_workflows()
    for wf in workflows:
        print(f"\n{wf['sort_order']}. {wf['display_name']} ({wf['name']})")
        print(f"   {wf['description']}")
        print(f"   图标: {wf['icon']}")

    print(f"\n总计: {len(workflows)} 个工作流")

def test_pose_variation():
    """测试姿势裂变提示词"""
    print("\n" + "=" * 60)
    print("姿势裂变提示词示例（4个姿势）：")
    print("=" * 60)

    prompt = build_pose_variation_prompt(4)
    print(prompt[:500] + "...\n")

def test_background_change():
    """测试换背景提示词"""
    print("\n" + "=" * 60)
    print("换背景提示词示例（纯白背景）：")
    print("=" * 60)

    prompt = build_background_change_prompt('white')
    print(prompt[:500] + "...\n")

def test_retouch():
    """测试商品精修提示词"""
    print("\n" + "=" * 60)
    print("商品精修提示词示例（保真精修）：")
    print("=" * 60)

    prompt = build_product_retouch_prompt('faithful-retouch')
    print(prompt[:400] + "...\n")

def test_material_enhance():
    """测试材质增强提示词"""
    print("\n" + "=" * 60)
    print("材质增强提示词示例（丝绸）：")
    print("=" * 60)

    prompt = build_material_enhancement_prompt('silk')
    print(prompt[:400] + "...\n")

def test_outfit_fusion():
    """测试搭配融图提示词"""
    print("\n" + "=" * 60)
    print("搭配融图提示词示例：")
    print("=" * 60)

    items = [
        {'role': 'top', 'image_num': 1, 'desc': '白色衬衫'},
        {'role': 'bottom', 'image_num': 2, 'desc': '蓝色牛仔裤'},
        {'role': 'model', 'image_num': 3, 'desc': '女模特'}
    ]

    prompt = build_outfit_fusion_prompt(items)
    print(prompt[:500] + "...\n")

def test_product_set():
    """测试商品套图提示词"""
    print("\n" + "=" * 60)
    print("商品套图提示词示例（4角度）：")
    print("=" * 60)

    prompt = build_product_set_prompt(['front', 'side', 'back', 'detail'])
    print(prompt[:500] + "...\n")

def test_translation():
    """测试图片翻译提示词"""
    print("\n" + "=" * 60)
    print("图片翻译提示词示例（季节翻译）：")
    print("=" * 60)

    prompt = build_image_translation_prompt('season', '夏季', '秋季')
    print(prompt[:500] + "...\n")

if __name__ == '__main__':
    print("\n衣拍视觉工作流功能测试")
    print("=" * 60)

    try:
        test_workflows_list()
        test_pose_variation()
        test_background_change()
        test_retouch()
        test_material_enhance()
        test_outfit_fusion()
        test_product_set()
        test_translation()

        print("\n" + "=" * 60)
        print("✓ 所有工作流模块测试通过")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
