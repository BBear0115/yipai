import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.workflows.shooting_plans import (
    SCENE_CONFIGS,
    get_available_scenes,
    get_scene_metadata,
    build_scene_prompt,
    build_auto_shooting_plan,
    POSE_MODIFIERS,
)
from backend.workflows.remake import normalize_remake_config, build_role_remake_prompt


class SceneSystemTests(unittest.TestCase):
    def test_all_scenes_have_required_fields(self):
        """Verify every scene configuration has complete metadata."""
        required_fields = {'name', 'description', 'lighting', 'composition', 'mood', 'styling', 'variants'}
        for scene_id, config in SCENE_CONFIGS.items():
            with self.subTest(scene=scene_id):
                self.assertEqual(set(config.keys()), required_fields, f'{scene_id} missing or has extra fields')
                self.assertIsInstance(config['name'], str)
                self.assertIsInstance(config['description'], str)
                self.assertIsInstance(config['lighting'], str)
                self.assertIsInstance(config['composition'], str)
                self.assertIsInstance(config['mood'], str)
                self.assertIsInstance(config['styling'], str)
                self.assertIsInstance(config['variants'], list)
                self.assertEqual(len(config['variants']), 3, f'{scene_id} must have exactly 3 variants')
                self.assertTrue(all(isinstance(v, str) and len(v) > 0 for v in config['variants']))

    def test_get_available_scenes(self):
        """Verify scene listing returns all scene IDs."""
        scenes = get_available_scenes()
        self.assertIsInstance(scenes, list)
        self.assertGreaterEqual(len(scenes), 8, 'Should have at least 8 scenes')
        self.assertIn('studio', scenes)
        self.assertIn('lookbook', scenes)
        self.assertIn('lifestyle', scenes)
        self.assertIn('magazine', scenes)
        self.assertIn('korean', scenes)
        self.assertIn('street', scenes)
        self.assertIn('minimal_japanese', scenes)
        self.assertIn('vintage', scenes)

    def test_get_scene_metadata(self):
        """Verify scene metadata extraction excludes variants."""
        metadata = get_scene_metadata('magazine')
        self.assertEqual(metadata['id'], 'magazine')
        self.assertEqual(metadata['name'], '时尚杂志')
        self.assertIn('description', metadata)
        self.assertIn('lighting', metadata)
        self.assertIn('composition', metadata)
        self.assertIn('mood', metadata)
        self.assertIn('styling', metadata)
        self.assertNotIn('variants', metadata, 'Metadata should not include variants')

    def test_get_scene_metadata_invalid_scene(self):
        """Verify error handling for invalid scene ID."""
        with self.assertRaises(ValueError) as cm:
            get_scene_metadata('nonexistent')
        self.assertIn('场景不存在', str(cm.exception))

    def test_build_scene_prompt_all_scenes(self):
        """Verify scene prompt generation for all scenes and variants."""
        for scene_id in get_available_scenes():
            for variant_index in range(3):
                with self.subTest(scene=scene_id, variant=variant_index):
                    prompt = build_scene_prompt(scene_id, variant_index)
                    self.assertIsInstance(prompt, str)
                    self.assertGreater(len(prompt), 50, 'Prompt should be substantial')
                    # Verify key components are present
                    scene = SCENE_CONFIGS[scene_id]
                    self.assertIn(scene['name'], prompt)
                    self.assertIn(scene['variants'][variant_index], prompt)
                    self.assertIn('光线', prompt)
                    self.assertIn('构图', prompt)
                    self.assertIn('氛围', prompt)

    def test_build_scene_prompt_invalid_index(self):
        """Verify error handling for invalid variant index."""
        with self.assertRaises(ValueError) as cm:
            build_scene_prompt('studio', 3)
        self.assertIn('拍摄方案序号无效', str(cm.exception))

        with self.assertRaises(ValueError):
            build_scene_prompt('studio', -1)

    def test_backward_compatibility_with_legacy_styles(self):
        """Verify legacy shooting plan functions still work."""
        for index in range(3):
            plan = build_auto_shooting_plan(index)
            self.assertIsInstance(plan, str)
            self.assertIn('：', plan)

        for style in ('studio', 'lookbook', 'lifestyle'):
            for index in range(3):
                plan = build_auto_shooting_plan(index, style)
                self.assertIsInstance(plan, str)

    def test_normalize_remake_config_accepts_new_scenes(self):
        """Verify remake config normalization accepts all scene IDs."""
        base_config = {
            'clothing_mode': 'multi',
            'output_count': 3,
            'model_source': 'preset',
        }

        for scene_id in get_available_scenes():
            with self.subTest(scene=scene_id):
                config = normalize_remake_config({**base_config, 'shooting_style': scene_id})
                self.assertEqual(config['shooting_style'], scene_id)

    def test_normalize_remake_config_rejects_invalid_scene(self):
        """Verify remake config rejects invalid scene IDs."""
        with self.assertRaises(ValueError) as cm:
            normalize_remake_config({
                'clothing_mode': 'multi',
                'output_count': 3,
                'model_source': 'preset',
                'shooting_style': 'invalid_scene',
            })
        self.assertIn('拍摄方向无效', str(cm.exception))

    def test_build_role_remake_prompt_with_new_scene(self):
        """Verify remake prompt generation uses new scene system."""
        config = normalize_remake_config({
            'clothing_mode': 'auto',
            'output_count': 3,
            'model_source': 'preset',
            'shooting_style': 'korean',
        })
        inputs = [{'role': 'auto'}]

        for index in range(3):
            with self.subTest(index=index):
                prompt = build_role_remake_prompt('female', inputs, config, None, index)
                self.assertIsInstance(prompt, str)
                # Verify Korean scene specifics appear
                self.assertIn('韩系清透', prompt)
                self.assertIn('本张拍摄方案', prompt)

    def test_scene_variants_are_distinct(self):
        """Verify each scene has 3 distinct variants."""
        for scene_id, config in SCENE_CONFIGS.items():
            with self.subTest(scene=scene_id):
                variants = config['variants']
                self.assertEqual(len(variants), len(set(variants)),
                               f'{scene_id} has duplicate variants')

    def test_scene_prompts_honor_selected_pose_for_every_variant(self):
        for scene_id in get_available_scenes():
            for preference, modifier in POSE_MODIFIERS.items():
                config = normalize_remake_config({'clothing_mode':'multi', 'shooting_style':scene_id,
                                                  'pose_preference':preference})
                for index in range(3):
                    with self.subTest(scene=scene_id, preference=preference, index=index):
                        prompt = build_role_remake_prompt('female', [{'role':'upper'}], config, None, index)
                        if modifier:
                            self.assertIn(modifier, prompt)
                            self.assertIn('冲突时优先遵守', prompt)
                        else:
                            self.assertNotIn('姿势要求：', prompt)

    def test_scene_names_are_unique(self):
        """Verify scene names are unique across all scenes."""
        names = [config['name'] for config in SCENE_CONFIGS.values()]
        self.assertEqual(len(names), len(set(names)), 'Scene names must be unique')


if __name__ == '__main__':
    unittest.main()
