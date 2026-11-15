# 前端选择界面到后端对接说明

## 完成时间
2026-11-15

## 完成的功能

### 1. 模特选择器 ✅
**前端 (`mockup/models.js`)**
- 已实现模特库管理界面
- 支持从预设模特库选择
- 支持上传自定义模特
- 模特ID通过 `selectedModelId` 全局变量传递

**后端 (`backend/server.py`)**
- `/api/models` - 获取模特列表
- `/api/models` (POST) - 上传自定义模特
- `/api/models/:id` (DELETE) - 删除自定义模特
- 在 `prepare_tryon_inputs` 中验证 `modelId` 参数

**参数传递链路**
```
前端选择 → selectedModelId → buildTryonWorkflow() →
POST /api/jobs 顶层 modelId → 后端接收验证 → 保存模特身份图快照 → 传入生成流程
```

### 2. 场景模式选择器 ✅
**前端 (`mockup/tryon.js`)**
- 拍摄方向选择器提供自由探索 (`auto`) 和 8 种场景：电商棚拍、城市 Lookbook、室内生活、时尚杂志、韩系清透、街头潮流、简约日系、复古胶片。
- 保存在 `tryonDraftState.shootingStyle`

**后端 (`backend/workflows/remake.py`)**
- `normalize_remake_config` 验证 `shooting_style` 参数
- 支持 `auto` 和 8 个场景 ID，前端选项通过 `workflowConfig.shooting_style` 传入。

**参数传递链路**
```
前端选择 → shootingStyle → buildTryonWorkflow() →
workflowConfig.shooting_style → normalize_remake_config() →
build_role_remake_prompt() → build_scene_prompt() 或 build_auto_shooting_plan()
```

### 3. 姿势偏好设置 ✅ (新增)
**前端 (`mockup/tryon.js`)**
- 新增姿势偏好选择器（4个选项）
  - 均衡展示 (balanced) - 默认，混合多种角度
  - 更多正面 (frontal) - 以正面或接近正面角度展示
  - 更多动态 (dynamic) - 以走动、转身等动态姿势展示
  - 更多侧面 (side) - 以侧身或侧面角度展示
- 保存在 `tryonDraftState.posePreference`
- 添加到界面渲染和事件处理

**后端验证 (`backend/workflows/remake.py`)**
```python
pose_preference = value.get('pose_preference', 'balanced')
if pose_preference not in ('balanced', 'frontal', 'dynamic', 'side'):
    raise ValueError('姿势偏好无效')
config.update(..., pose_preference=pose_preference)
```

**后端应用 (`backend/workflows/shooting_plans.py`)**
```python
POSE_MODIFIERS = {
    'frontal': '以正面或接近正面的角度展示，',
    'side': '以侧身或侧面角度展示，',
    'dynamic': '以走动、转身等动态姿势展示，',
    'balanced': '',
}

def build_auto_shooting_plan(index, style='auto', pose_preference='balanced'):
    # 将姿势修饰添加到拍摄方案描述中
    modifier = POSE_MODIFIERS[pose_preference]
    if modifier:
        description = modifier + description
    return f'{name}：{description}'
```

**参数传递链路**
```
前端选择 → posePreference → buildTryonWorkflow() →
workflowConfig.pose_preference → normalize_remake_config() →
build_role_remake_prompt() → build_auto_shooting_plan(pose_preference)
```

### 4. 搭配方案

界面提供极简搭配 (`minimal`)、协调搭配 (`coordinated`)、应季搭配 (`seasonal`) 三个选项；`stylingPreset` 通过 `workflowConfig.styling_preset` 传入，后端验证并将搭配要求加入提示词。搭配不能替换已上传商品。

## 修改的文件

### 前端文件
1. `/Users/dxm/Documents/yipai/mockup/tryon.js`
   - `freshTryonDraft()`: 添加 `posePreference: 'balanced'`
   - `buildTryonWorkflow()`: 添加 `pose_preference` 参数传递
   - `renderTryonStudio()`: 添加姿势偏好选择器UI
   - 事件处理: 添加 `data-pose-preference` 点击处理

### 后端文件
1. `/Users/dxm/Documents/yipai/backend/workflows/remake.py`
   - `normalize_remake_config()`: 添加 `pose_preference` 参数验证
   - `build_role_remake_prompt()`: 传递 `pose_preference` 到拍摄方案生成

2. `/Users/dxm/Documents/yipai/backend/workflows/shooting_plans.py`
   - 添加 `POSE_MODIFIERS` 字典
   - 更新 `build_auto_shooting_plan()`: 接受并应用 `pose_preference` 参数

### 测试文件
1. `/Users/dxm/Documents/yipai/test_integration.py` (新建)
   - 姿势偏好参数验证测试
   - 拍摄方案生成测试
   - 完整工作流配置测试
   - 模特选择参数测试

## 测试验证

运行集成测试：
```bash
cd /Users/dxm/Documents/yipai
python3 test_integration.py
```

脚本检查范围（不代表浏览器或 HTTP 端到端验收）：
- ✓ 姿势偏好参数验证（有效值、默认值、无效值拒绝）
- ✓ 拍摄方案生成（48种组合：4种风格 × 4种姿势 × 3张图）
- ✓ 完整工作流配置（所有参数正确传递）
- ✓ 模特选择参数（预设模特、作品模特）

## 使用示例

### 前端调用
```javascript
// 用户在界面选择后，状态自动更新
tryonDraftState = {
  clothingMode: 'multi',
  garments: {upper: image, lower: null, single: null},
  references: [],
  shootingStyle: 'lookbook',        // 城市 Lookbook
  posePreference: 'dynamic',        // 更多动态姿势
  modelImage: null,
  modelFromWork: false,
  detailsEnabled: false,
  details: {upper:[], lower:[], single:[]},
  outputCount: 3,
  instruction: '通勤风格'
};

// 提交时自动构建工作流
const workflow = buildTryonWorkflow();
// 提交到 POST /api/jobs，包含 workflowType: 'remake'、workflowConfig、inputImages 和顶层 modelId
```

### 后端处理
```python
# server.py 接收参数
config = normalize_remake_config(payload.get('workflowConfig'))
# config = {
#     'clothing_mode': 'multi',
#     'output_count': 3,
#     'shooting_style': 'lookbook',
#     'pose_preference': 'dynamic',
#     'instruction': '通勤风格',
#     'model_source': 'preset'
# }

# 生成提示词时应用姿势偏好
for index in range(config['output_count']):
    prompt = build_role_remake_prompt(model, inputs, config, analysis, index)
    # 包含: "城市 Lookbook：以走动、转身等动态姿势展示，克制的城市街景..."
```

## 兼容性保证

- ✅ 保持与现有未提交改动的兼容
- ✅ 新UI元素不打乱现有布局（插入在拍摄方向选择器下方）
- ✅ 默认值 'balanced' 保持原有行为
- ✅ 后端向后兼容：未传 `pose_preference` 时默认为 'balanced'

## 参数完整性验证

参数传递结构如下；`test_integration.py` 检查配置和提示词函数，不启动浏览器或 HTTP 服务。真实 API 快照及生成请求由 `backend/test_server.py` 验证：

1. **服装类型** (clothingMode) → clothing_mode ✅
2. **商品图片** (garments) → inputImages ✅
3. **参考图片** (references) → inputImages ✅
4. **拍摄方向** (shootingStyle) → shooting_style ✅
5. **姿势偏好** (posePreference) → pose_preference ✅ (新增)
6. **模特选择** (selectedModelId) → 请求顶层 modelId ✅
7. **生成数量** (outputCount) → output_count ✅
8. **搭配要求** (instruction) → instruction ✅
9. **细节图开关** (detailsEnabled) → inputImages 中的 detail 角色及 garmentRole ✅

## 下一步建议

1. **前端UI优化**
   - 为姿势偏好选项添加图标示意
   - 添加tooltip说明每个选项的效果

2. **扩展场景库**
   - 后端已支持8种场景（studio, lookbook, lifestyle, magazine, korean, street, minimal_japanese, vintage）
   - 前端已提供全部 8 种场景，后续可补充对应的预览素材

3. **用户测试**
   - 验证姿势偏好在实际生成中的效果
   - 收集用户反馈调整修饰文案

4. **性能监控**
   - 监控不同参数组合的生成质量
   - 记录用户最常用的参数组合
