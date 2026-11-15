"""测试拍同款工作流的新增功能。"""
import unittest
from backend.workflows.remake import normalize_remake_config, build_role_remake_prompt
from backend.workflows.shooting_plans import get_available_scenes


class RemakeWorkflowTests(unittest.TestCase):
    def test_normalize_remake_config_with_all_params(self):
        """测试配置规范化包含所有新参数。"""
        config = normalize_remake_config({
            'clothing_mode': 'multi',
            'output_count': 2,
            'shooting_style': 'magazine',
            'pose_preference': 'dynamic',
            'styling_preset': 'coordinated'
        })

        assert config['output_count'] == 2
        assert config['shooting_style'] == 'magazine'
        assert config['pose_preference'] == 'dynamic'
        assert config['styling_preset'] == 'coordinated'
        assert config['model_source'] == 'preset'


    def test_normalize_remake_config_defaults(self):
        """测试默认值。"""
        config = normalize_remake_config({'clothing_mode': 'multi'})

        assert config['output_count'] == 3
        assert config['shooting_style'] == 'auto'
        assert config['pose_preference'] == 'balanced'
        assert config['styling_preset'] == 'minimal'


    def test_normalize_remake_config_all_scenes(self):
        """测试所有场景ID有效。"""
        for scene_id in get_available_scenes():
            config = normalize_remake_config({
                'clothing_mode': 'multi',
                'shooting_style': scene_id
            })
            assert config['shooting_style'] == scene_id


    def test_normalize_remake_config_invalid_styling(self):
        """测试无效搭配方案。"""
        with self.assertRaisesRegex(ValueError, '搭配方案无效'):
            normalize_remake_config({
                'clothing_mode': 'multi',
                'styling_preset': 'invalid'
            })


    def test_build_role_remake_prompt_no_reference(self):
        """测试无参考图时应用场景和姿势。"""
        config = normalize_remake_config({
            'clothing_mode': 'multi',
            'shooting_style': 'lookbook',
            'pose_preference': 'frontal',
            'styling_preset': 'coordinated'
        })

        inputs = [{'role': 'upper'}, {'role': 'model'}]
        prompt = build_role_remake_prompt('female', inputs, config, None, 0)

        assert '城市 Lookbook' in prompt
        assert '搭配要求' in prompt
        assert '协调' in prompt or '呼应' in prompt


    def test_build_role_remake_prompt_with_reference(self):
        """测试有参考图时应用姿势偏好。"""
        config = normalize_remake_config({
            'clothing_mode': 'multi',
            'shooting_style': 'auto',
            'pose_preference': 'side',
            'styling_preset': 'minimal'
        })

        analysis = {
            'product_note': '目标商品是图1的上装',
            'shot': '全身景',
            'pose': '站立',
            'styling': '简约',
            'scene': '室内',
            'lighting': '自然光',
            'color': '清新',
            'mood': '轻松',
            'variants': ['正面', '侧面', '背面']
        }

        inputs = [{'role': 'upper'}, {'role': 'model'}]
        prompt = build_role_remake_prompt('female', inputs, config, analysis, 1)

        assert '搭配要求' in prompt
        assert '姿势调整要求' in prompt
        assert '侧' in prompt


    def test_styling_preset_in_prompt(self):
        """测试三种搭配方案都进入prompt。"""
        for preset in ['minimal', 'coordinated', 'seasonal']:
            config = normalize_remake_config({
                'clothing_mode': 'single',
                'styling_preset': preset
            })

            inputs = [{'role': 'single'}]
            prompt = build_role_remake_prompt('male', inputs, config, None, 0)

            assert '搭配要求' in prompt



if __name__ == '__main__':
    unittest.main()
