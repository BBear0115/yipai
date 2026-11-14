"""工作流引擎基础模块"""

# 工作流类型定义
WORKFLOW_TYPES = {
    'tryon': {
        'name': 'tryon',
        'display_name': '服装上身',
        'description': '上传商品图，生成模特上身效果',
        'icon': 'camera',
        'sort_order': 1
    },
    'pose_variation': {
        'name': 'pose_variation',
        'display_name': '姿势裂变',
        'description': '一张图生成多个姿势',
        'icon': 'users',
        'sort_order': 2
    },
    'background_change': {
        'name': 'background_change',
        'display_name': '换背景',
        'description': '更换背景场景',
        'icon': 'image',
        'sort_order': 3
    },
    'product_retouch': {
        'name': 'product_retouch',
        'display_name': '商品精修',
        'description': '去瑕疵、提亮',
        'icon': 'sparkles',
        'sort_order': 4
    },
    'outfit_fusion': {
        'name': 'outfit_fusion',
        'display_name': '搭配融图',
        'description': '多件商品搭配',
        'icon': 'layers',
        'sort_order': 5
    },
    'material_enhance': {
        'name': 'material_enhance',
        'display_name': '材质增强',
        'description': '提升质感',
        'icon': 'feather',
        'sort_order': 6
    },
    'product_set': {
        'name': 'product_set',
        'display_name': '商品套图',
        'description': '多角度套图',
        'icon': 'grid',
        'sort_order': 7
    },
    'image_translation': {
        'name': 'image_translation',
        'display_name': '图片翻译',
        'description': '风格场景转换',
        'icon': 'shuffle',
        'sort_order': 8
    }
}

def get_workflow_info(workflow_type: str) -> dict:
    """获取工作流信息"""
    return WORKFLOW_TYPES.get(workflow_type, WORKFLOW_TYPES['tryon'])

def get_all_workflows() -> list:
    """获取所有工作流类型"""
    return sorted(WORKFLOW_TYPES.values(), key=lambda x: x['sort_order'])
