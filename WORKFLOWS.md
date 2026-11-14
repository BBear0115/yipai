# 衣拍工作流系统

## 概述

衣拍现已集成 8 个智能工作流，覆盖商品摄影的全流程处理需求。

## 已实现的工作流

### 1. 虚拟试穿 (tryon)
- **功能**: 上传商品图，生成模特上身效果
- **输入**: 商品平铺图 + 模特选择（男/女）
- **输出**: 1024x1536 上身效果图
- **模型**: gpt-image-2.5-flare
- **状态**: ✅ 已完成

### 2. 姿势裂变 (pose_variation)
- **功能**: 一张商品图生成多个姿势的模特效果
- **输入**: 单张上身效果图
- **配置**: pose_count (4/6/8)
- **输出**:
  - 4姿势: 1536x1536 (2x2网格)
  - 6姿势: 1536x2048 (2x3网格)
  - 8姿势: 1536x2048 (3x3网格)
- **模型**: gpt-image-2.5-flare
- **状态**: ✅ 已完成

### 3. 背景替换 (background_change)
- **功能**: 保持人物和服装不变，更换背景场景
- **输入**: 上身效果图
- **配置**: scene_type
  - `white`: 纯白色摄影背景
  - `studio_gray`: 浅灰色摄影棚
  - `outdoor_street`: 城市街道街拍
  - `indoor_minimal`: 简约室内空间
  - `beach`: 海边沙滩
  - `cafe`: 咖啡馆室内
- **输出**: 1024x1536
- **模型**: gpt-image-2.5-flare
- **状态**: ✅ 已完成

### 4. 商品精修 (product_retouch)
- **功能**: 优化商品细节，修正瑕疵
- **状态**: 🚧 基础架构已完成，提示词待优化

### 5. 服饰融合 (outfit_fusion)
- **功能**: 将多件商品组合在一起展示
- **状态**: 🚧 基础架构已完成，提示词待优化

### 6. 材质增强 (material_enhance)
- **功能**: 提升服装材质质感
- **状态**: 🚧 基础架构已完成，提示词待优化

### 7. 商品组合 (product_set)
- **功能**: 生成多角度商品套图
- **状态**: 🚧 基础架构已完成，提示词待优化

### 8. 图像转译 (image_translation)
- **功能**: 风格和场景转换（季节/风格变换）
- **状态**: 🚧 基础架构已完成，提示词待优化

## 技术架构

### 后端结构
```
backend/
├── server.py                 # 主服务器，集成所有工作流
└── workflows/
    ├── __init__.py          # 工作流注册表
    ├── pose_variation.py    # 姿势裂变
    ├── background_change.py # 背景替换
    ├── retouch.py          # 商品精修
    ├── fusion.py           # 服饰融合
    └── translation.py      # 图像转译
```

### 数据库扩展
- **workflow_types 表**: 存储工作流元数据
- **jobs 表新增字段**:
  - `workflow_type`: 工作流类型（默认 'tryon'）
  - `workflow_config`: JSON配置
  - `source_job_id`: 源任务ID
  - `input_images`: 多图输入

### 前端界面
```
mockup/
├── workflows.js             # 工作流中心和详情页
├── app.js                   # 路由集成
├── styles.css               # 工作流样式
└── index.html               # 脚本引入
```

### API 接口

#### 获取工作流列表
```bash
GET /api/workflows
```

响应：
```json
{
  "workflows": [
    {
      "id": "pose_variation",
      "name": "pose_variation",
      "displayName": "姿态变化",
      "description": "保持模特身份，改变姿势和构图",
      "icon": "🤸",
      "sortOrder": 2
    }
  ]
}
```

#### 创建工作流任务
```bash
POST /api/jobs
Content-Type: application/json

{
  "idempotencyKey": "unique-key",
  "image": "data:image/jpeg;base64,...",
  "workflowType": "pose_variation",
  "workflowConfig": {
    "pose_count": 4
  },
  "model": "female"  // 可选，部分工作流不需要
}
```

## 使用示例

### 姿势裂变
```javascript
const response = await fetch('/api/jobs', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    idempotencyKey: crypto.randomUUID(),
    image: 'data:image/jpeg;base64,...',
    workflowType: 'pose_variation',
    workflowConfig: {
      pose_count: 6  // 生成6个姿势
    }
  })
});
```

### 背景替换
```javascript
const response = await fetch('/api/jobs', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    idempotencyKey: crypto.randomUUID(),
    image: 'data:image/jpeg;base64,...',
    workflowType: 'background_change',
    workflowConfig: {
      scene_type: 'beach'  // 海边场景
    }
  })
});
```

## 测试

### 运行工作流模块测试
```bash
python3 scripts/test_workflows.py
```

### 运行完整后端测试
```bash
python3 backend/test_server.py
```

## 后续优化计划

1. **完善剩余 6 个工作流的提示词工程**
   - 商品精修: 保真精修、创意美化
   - 材质增强: 丝绸、棉麻、皮革等材质
   - 服饰融合: 上衣+下装+模特
   - 商品组合: 4角度套图
   - 图像转译: 季节/风格转换

2. **前端体验优化**
   - 工作流预览效果
   - 批量处理支持
   - 参数预设模板

3. **性能优化**
   - 工作流任务队列
   - 结果缓存策略
   - 并发控制

## 开发日志

- 2024-11-13: 完成姿势裂变和背景替换两个核心工作流
- 2024-11-13: 完成数据库扩展和前端界面集成
- 2024-11-13: 创建 8 个工作流基础架构
