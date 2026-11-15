# 场景选择系统 Scene Selection System

## 概述

衣拍场景系统提供结构化的拍摄风格配置，将原有的3种拍摄方案扩展为8种完整场景，每种场景包含详细的光线、构图、氛围和搭配建议。

前后端均支持 8 个场景 ID，拍同款界面另提供“自由探索”。选择通过 `POST /api/jobs` 的 `workflowConfig.shooting_style` 传入；姿势偏好及搭配方案分别使用 `pose_preference` 和 `styling_preset`。

## 可用场景

### 1. 电商棚拍 (studio)
- **定位**: 商业产品摄影标准
- **光线**: 柔和均匀的三点式商业布光，消除阴影
- **构图**: 正面或轻微侧身，视觉中心集中在商品
- **氛围**: 专业、干净、客观
- **适用**: 电商主图、产品展示、白底图需求

### 2. 城市 Lookbook (lookbook)
- **定位**: 都市时尚街拍
- **光线**: 自然日光或黄金时段柔和光线
- **构图**: 环境与人物平衡，利用建筑线条
- **氛围**: 轻松、真实、有态度
- **适用**: 品牌lookbook、街拍风格、lifestyle展示

### 3. 室内生活方式 (lifestyle)
- **定位**: 生活场景穿搭
- **光线**: 柔和窗光或室内自然光
- **构图**: 环境营造生活感，人物姿态自然
- **氛围**: 亲和、松弛、有温度
- **适用**: 日常穿搭、居家场景、咖啡厅等生活化内容

### 4. 时尚杂志 (magazine)
- **定位**: 专业时尚大片
- **光线**: 戏剧性光影对比或柔和高调光线
- **构图**: 讲究构图，利用环境元素和光影层次
- **氛围**: 高级、有张力、艺术化
- **适用**: 杂志内页、品牌大片、高端时尚内容

### 5. 韩系清透 (korean)
- **定位**: 韩式明亮摄影
- **光线**: 高调柔光，微微过曝的清透感
- **构图**: 简洁背景，人物居中或留白
- **氛围**: 清新、柔和、少女感
- **适用**: 韩风服装、少女系品牌、清新风格

### 6. 街头潮流 (street)
- **定位**: 都市街头文化
- **光线**: 自然光或城市环境光
- **构图**: 街头元素，构图大胆有冲击力
- **氛围**: 酷、有态度、年轻化
- **适用**: 潮牌、街头服饰、urban风格

### 7. 简约日系 (minimal_japanese)
- **定位**: 日式极简美学
- **光线**: 柔和自然光，保留细腻层次
- **构图**: 大量留白，构图克制
- **氛围**: 平静、内敛、有质感
- **适用**: 基础款、极简品牌、无印良品风格

### 8. 复古胶片 (vintage)
- **定位**: 胶片摄影质感
- **光线**: 温暖色温或冷调胶片感
- **构图**: 略带颗粒感，色彩饱和度适中
- **氛围**: 怀旧、温暖、有故事感
- **适用**: 复古服装、vintage品牌、怀旧风格

## API 使用

### 获取所有场景列表

```python
from backend.workflows.shooting_plans import get_available_scenes

scenes = get_available_scenes()
# ['studio', 'lookbook', 'lifestyle', 'magazine', 'korean', 'street', 'minimal_japanese', 'vintage']
```

### 获取场景元数据（用于前端展示）

```python
from backend.workflows.shooting_plans import get_scene_metadata

metadata = get_scene_metadata('korean')
# {
#     'id': 'korean',
#     'name': '韩系清透',
#     'description': '明亮通透的韩式摄影，色调清新柔和',
#     'lighting': '高调柔光，微微过曝的清透感，减弱阴影',
#     'composition': '简洁背景，人物居中或留白，营造轻盈空气感',
#     'mood': '清新、柔和、少女感，传达轻松愉悦的情绪',
#     'styling': '浅色系或柔和色彩搭配，简约配饰，整体干净清透'
# }
```

### 生成场景拍摄提示词

```python
from backend.workflows.shooting_plans import build_scene_prompt

# 生成韩系清透场景的第一个拍摄变体
prompt = build_scene_prompt('korean', 0)
# 包含完整的场景描述、光线、构图、氛围、搭配和具体拍法
```

### 在拍同款工作流中使用

```python
from backend.workflows.remake import normalize_remake_config

config = normalize_remake_config({
    'clothing_mode': 'auto',
    'output_count': 3,
    'model_source': 'preset',
    'shooting_style': 'magazine',  # 使用场景ID
})
```

## 场景变体 (Variants)

每个场景包含3个不同的拍摄变体，确保同一场景下生成多样化的构图和姿势：

- **变体0**: 基础经典构图
- **变体1**: 动态或侧面变化
- **变体2**: 角度或姿势进一步变化

无参考图时，根据本组第 1、2、3 张输出选择对应变体；每组最多 3 张。

## 向后兼容

系统完全兼容原有的 `auto`、`studio`、`lookbook`、`lifestyle` 拍摄风格：

```python
# 旧代码继续工作
plan = build_auto_shooting_plan(0, 'studio')

# 新场景系统
prompt = build_scene_prompt('studio', 0)
```

## 扩展场景

添加新场景只需在 `SCENE_CONFIGS` 中定义：

```python
SCENE_CONFIGS['new_scene'] = {
    'name': '场景名称',
    'description': '场景描述',
    'lighting': '光线要求',
    'composition': '构图建议',
    'mood': '氛围定义',
    'styling': '搭配建议',
    'variants': [
        '第一种拍法',
        '第二种拍法',
        '第三种拍法',
    ],
}
```

## 前端集成建议

### 扩展场景选择UI（示意，尚未提供场景列表 HTTP 接口）

```typescript
// 当前可在前端定义与后端一致的选项；如需动态元数据，先实现相应 HTTP 接口。
const scenes = ['studio', 'lookbook', 'lifestyle', 'magazine', 'korean', 'street', 'minimal_japanese', 'vintage'];

// 用户选择场景后
const workflowConfig = {
  clothing_mode: 'auto',
  output_count: 3,
  model_source: 'preset',
  shooting_style: selectedSceneId, // 'magazine', 'korean' 等
};
```

### 场景预览

为每个场景提供示例图片，放置在：
- `mockup/assets/scenes/{scene_id}/preview.jpg`（服务访问路径为 `assets/scenes/...`）
- 或前端 assets 目录

## 测试

运行完整测试套件：

```bash
python -m unittest backend.test_scene_system -v
```

测试覆盖：
- ✅ 所有场景配置完整性
- ✅ 场景元数据提取
- ✅ 提示词生成
- ✅ 拍同款工作流集成
- ✅ 向后兼容性
- ✅ 错误处理

## 注意事项

1. **商品保真优先**: 所有场景拍摄方案都必须确保目标商品完整展示，不得遮挡或改变商品结构
2. **场景ID稳定性**: 场景ID一旦定义不应更改，前端可能硬编码引用
3. **变体数量**: 每个场景必须提供恰好3个变体
4. **中文描述**: 所有场景描述使用中文，与生图提示词一致
