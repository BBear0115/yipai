"""测试场景配置和姿势规划。"""
import unittest
from backend.workflows.shooting_plans import (
    get_available_scenes, get_scene_metadata, build_scene_prompt,
    get_styling_guidance, POSE_MODIFIERS, STYLING_PRESETS
)


class SceneStylingTests(unittest.TestCase):
    def test_available_scenes(self):
        """测试所有场景ID可用。"""
        scenes = get_available_scenes()
        assert len(scenes) == 8
        assert 'studio' in scenes
        assert 'lookbook' in scenes
        assert 'lifestyle' in scenes
        assert 'magazine' in scenes
        assert 'korean' in scenes
        assert 'street' in scenes
        assert 'minimal_japanese' in scenes
        assert 'vintage' in scenes


    def test_scene_metadata(self):
        """测试场景元数据返回。"""
        meta = get_scene_metadata('studio')
        assert meta['id'] == 'studio'
        assert meta['name'] == '电商棚拍'
        assert 'description' in meta
        assert 'lighting' in meta
        assert 'composition' in meta
        assert 'mood' in meta
        assert 'styling' in meta
        assert 'variants' not in meta  # UI不需要variants


    def test_scene_metadata_invalid(self):
        """测试无效场景ID。"""
        with self.assertRaisesRegex(ValueError, '场景不存在'):
            get_scene_metadata('invalid_scene')


    def test_build_scene_prompt_all_scenes(self):
        """测试所有场景的prompt生成。"""
        for scene_id in get_available_scenes():
            for variant_idx in range(3):
                for pose_pref in POSE_MODIFIERS.keys():
                    prompt = build_scene_prompt(scene_id, variant_idx, pose_pref)
                    assert isinstance(prompt, str)
                    assert len(prompt) > 50
                    meta = get_scene_metadata(scene_id)
                    assert meta['name'] in prompt


    def test_build_scene_prompt_with_pose_modifier(self):
        """测试姿势偏好修饰符应用。"""
        prompt_balanced = build_scene_prompt('studio', 0, 'balanced')
        prompt_frontal = build_scene_prompt('studio', 0, 'frontal')

        # balanced不应有姿势要求
        assert '姿势要求' not in prompt_balanced

        # frontal应有姿势要求
        assert '姿势要求' in prompt_frontal
        assert '正面' in prompt_frontal


    def test_build_scene_prompt_invalid(self):
        """测试无效参数。"""
        with self.assertRaisesRegex(ValueError, '场景不存在'):
            build_scene_prompt('invalid', 0, 'balanced')

        with self.assertRaisesRegex(ValueError, '拍摄方案序号无效'):
            build_scene_prompt('studio', 5, 'balanced')

        with self.assertRaisesRegex(ValueError, '姿势偏好无效'):
            build_scene_prompt('studio', 0, 'invalid_pose')


    def test_styling_guidance(self):
        """测试搭配指导。"""
        for preset in STYLING_PRESETS.keys():
            guidance = get_styling_guidance(preset)
            assert isinstance(guidance, str)
            assert len(guidance) > 10

        # 默认返回minimal
        assert get_styling_guidance('invalid') == get_styling_guidance('minimal')


    def test_styling_presets_structure(self):
        """测试搭配预设结构。"""
        assert len(STYLING_PRESETS) == 3
        for preset_id, config in STYLING_PRESETS.items():
            assert 'name' in config
            assert 'description' in config
            assert 'guidance' in config
            assert isinstance(config['guidance'], str)



import unittest

from backend.workflows.remake import build_role_remake_prompt, normalize_remake_config
from backend.workflows.shooting_plans import AUTO_SHOOTING_PLANS, build_auto_shooting_plan


class ShootingPlanTests(unittest.TestCase):
    def test_auto_shooting_plans_are_distinct_and_indexed(self):
        plans = [build_auto_shooting_plan(index) for index in range(len(AUTO_SHOOTING_PLANS))]

        self.assertEqual(len(plans), 3)
        self.assertEqual(len(set(plans)), 3)
        self.assertTrue(all('完整' in plan and '商品' in plan for plan in plans))

    def test_rejects_out_of_range_plan(self):
        with self.assertRaises(ValueError):
            build_auto_shooting_plan(3)

    def test_styles_keep_three_variants_and_invalid_styles_are_rejected(self):
        for style in ('auto', 'studio', 'lookbook', 'lifestyle'):
            config = normalize_remake_config({'clothing_mode': 'multi', 'shooting_style': style})
            prompts = [build_role_remake_prompt('female', [{'role': 'upper'}], config, None, index) for index in range(3)]
            self.assertEqual(len(set(prompts)), 3)
            self.assertTrue(all('商品' in prompt for prompt in prompts))
        with self.assertRaises(ValueError):
            normalize_remake_config({'clothing_mode': 'multi', 'shooting_style': 'unknown'})




if __name__ == '__main__':
    unittest.main()
