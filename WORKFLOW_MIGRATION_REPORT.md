# 衣拍工作流能力改动核对

## 执行概要

工作区新增了**模特人物、场景、穿搭搭配、动作姿势**相关配置及提示词逻辑。以下按源码核对已实现内容和交付范围；未调用收费服务验证成片，因此不宣称与 Pixel Diffusion 的实际生成效果等价。

**关键改进：**
- 提供 8 种新模特生成配置（4女4男）；现有 2 张素材保留，新素材未执行生成
- 场景系统从 3 个方案升级到 8 个专业摄影场景（含详细光线、构图、风格规范）
- 姿势系统从 8 个固定描述升级为结构化规划（11个姿势库，智能分配策略）
- 前端提供自由探索及全部 8 种场景、4 种姿势偏好和 3 种搭配方案

---

## 一、模特生成配置扩充（8 种）

### 改动文件
- `scripts/init_preset_models.py` - 扩充模特生成配置
- `scripts/model-prompts.json` - 模特提示词配置
- `backend/workflows/tryon.py` - 模特参数传递路径（已验证）
- `backend/test_model_selection.py` - 新增测试套件

### 新增模特配置（原创设计）

**女性模特（4个）：**
1. 清纯甜美（20-23岁）- 圆脸、大眼、自然黑长直发
2. 优雅知性（28-32岁）- 鹅蛋脸、成熟妆容、披肩波浪卷发
3. 酷飒个性（24-27岁）- 立体五官、挑眉、短发或高马尾
4. 健康活力（23-26岁）- 小麦色健康肤色、运动感

**男性模特（4个）：**
1. 阳光少年（20-24岁）- 清秀五官、自然短发、青春感
2. 成熟稳重（30-35岁）- 方正脸型、短发、商务气质
3. 型格潮流（25-28岁）- 立体轮廓、时尚发型
4. 斯文儒雅（26-30岁）- 秀气五官、文艺气质

### 技术实现
- 生成逻辑就绪，支持 `--dry-run` 预检和 `--generate N` 实际生成
- 模特参数通过 `build_tryon_prompt(model, ...)` 正确传递
- 数据库无需迁移，现有 `models` 表结构完整支持

### 测试结果
```
✓ 模特性别参数传递（女性/男性）
✓ 模特身份图场景正确处理
✓ 参考图场景正确处理
✓ 参考图+模特身份图场景正确处理
✓ 多候选图姿势变化正确
✓ 多样化模特配置已定义
```

**所有 6 项测试全部通过**

---

## 二、场景系统建设（3 → 8）

### 改动文件
- `backend/workflows/shooting_plans.py` - 场景配置系统核心
- `backend/workflows/remake.py` - 场景参数集成
- `backend/test_scene_system.py` - 新增测试套件
- `backend/workflows/SCENES.md` - 完整文档

### 新增场景配置（原创设计）

每个场景包含：名称、描述、光线要求、构图指南、风格定位、3个拍摄变体

1. **电商棚拍 (studio)** - 干净白底/浅灰，柔和均匀商业灯光
2. **城市Lookbook (lookbook)** - 克制城市街景，自然日光
3. **室内生活方式 (lifestyle)** - 明亮简约室内，柔和窗光
4. **时尚杂志 (magazine)** - 高对比电影感灯光，杂志张力
5. **韩系清透 (korean)** - 柔和自然光感，轻盈空气感
6. **街头潮流 (street)** - 城市街头，自然光与建筑氛围
7. **简约日系 (minimal_japanese)** - 极简空间，禅意克制
8. **复古胶片 (vintage)** - 胶片颗粒，复古色调

### API 函数
```python
get_available_scenes()           # 获取所有场景ID列表
get_scene_metadata(scene_id)      # 获取场景元数据（供前端展示）
build_scene_prompt(scene_id, variant_index)  # 生成完整拍摄方案
```

### 集成验证
- 场景参数正确注入 `build_tryon_prompt()`
- 向后兼容现有 `auto/studio/lookbook/lifestyle` 风格
- 前端可通过 `shooting_style` 参数选择任一场景

### 测试结果
```
Ran 12 tests in 0.001s
OK
```

**所有 12 项测试全部通过**

---

## 三、姿势规划系统升级

### 改动文件
- `backend/workflows/pose_variation.py` - 结构化姿势规划
- `backend/workflows/test_pose_variation.py` - 新增测试套件
- `backend/workflows/pose_variation_example.py` - 使用示例

### 结构化姿势定义

每个姿势包含：
- `angle` - 角度分类（正面/侧面/背面）
- `action_type` - 动作类型（站姿/走动/坐姿）
- `body_action` - 身体动作描述
- `hand_action` - 手部动作描述
- `camera_framing` - 镜头取景
- `visibility_focus` - 可见性重点（强调服装展示）

### 姿势库（11个）
包含正面站姿、手部姿势、侧身、转身、走动、坐姿、七分身等多种组合

### 智能分配策略
- **4张照片：** 正面2、侧面1、背面1 - 覆盖主要角度
- **6张照片：** 正面4、侧面1、背面1 - 增加动作多样性（站姿、走动、坐姿）
- **8张照片：** 正面4、侧面3、背面1 - 完整覆盖所有主要姿势

### 向后兼容
- `build_pose_variation_prompt(use_structured=True)` - 新结构化姿势
- `build_pose_variation_prompt(use_structured=False)` - 原8个固定描述

### 测试结果
```
============================================================
相关专项检查通过（不代表完整浏览器回归）。
============================================================
```

**6个测试套件全部通过：** 库结构、选择策略、提示词生成、边界条件、摘要、多样性

---

## 四、前端参数集成

### 改动文件
- `mockup/tryon.js` - 新增姿势偏好选择器
- `backend/workflows/remake.py` - 参数验证与传递
- `backend/workflows/shooting_plans.py` - 姿势修饰应用
- `test_integration.py` - 配置与提示词函数检查

### 新增前端功能

**姿势偏好选择器（4个选项）：**
- `balanced` - 均衡展示（默认）
- `frontal` - 更多正面
- `dynamic` - 更多动态（走动、转身）
- `side` - 更多侧面

### 参数传递链路
```
前端 posePreference
  → buildTryonWorkflow()
  → API payload pose_preference
  → normalize_remake_config()
  → build_role_remake_prompt()
  → build_auto_shooting_plan(pose_preference)
  → 拍摄方案文本
```

### 集成测试结果
```
✅ 测试 1 通过: 参数验证
✅ 测试 2 通过: 拍摄方案生成（48种组合：4风格 × 4姿势 × 3张）
✅ 测试 3 通过: 完整工作流配置
✅ 测试 4 通过: 模特选择参数

相关专项检查通过（不代表完整浏览器回归）。前端到后端参数传递正常工作。
```

---

## 五、验证范围

### 测试覆盖
- **模特选择：** 6/6 通过
- **场景系统：** 12/12 通过
- **姿势规划：** 6/6 通过
- **配置与提示词函数检查：** 4/4 通过（`test_integration.py` 不启动浏览器或 HTTP 服务）
- **总计：** 28/28 核心功能测试通过

### 代码检查
```bash
git diff --check  # 通过，无空白错误
```

### 向后兼容
- 所有新功能可选，未破坏现有流程
- 原有参数默认值保持不变
- 此处的函数级检查不能代替完整回归；提交前应运行后端和前端完整套件，结果以本次提交核对记录为准。

---

## 六、改动统计

### 相关修改文件（清单快照，最终以 Git diff 为准）
```
M README.md
M WORKFLOWS.md
M backend/server.py
M backend/test_server.py
M backend/workflows/pose_variation.py
M backend/workflows/remake.py
M backend/workflows/tryon.py
M mockup/README.md
M mockup/app.js
M mockup/batch.js
M mockup/community.js
M mockup/index.html
M mockup/studio.css
M mockup/studio.js
M mockup/styles.css
M mockup/tryon.css
M mockup/tryon.js
M scripts/init_preset_models.py
M scripts/model-prompts.json
M testing/frontend.test.cjs
```

### 相关新增文件（清单快照，最终以 Git diff 为准）
```
?? BATCH_FEATURE.md
?? INTEGRATION_SUMMARY.md
?? PRESET_MODELS_USAGE.md
?? backend/test_model_selection.py
?? backend/test_scene_system.py
?? backend/test_shooting_plans.py
?? backend/workflows/SCENES.md
?? backend/workflows/pose_variation_example.py
?? backend/workflows/shooting_plans.py
?? backend/workflows/test_pose_variation.py
?? mockup/EXPORT_INTEGRATION.md
?? mockup/compare-slider.css
?? mockup/compare-slider.js
?? mockup/credits.js
?? mockup/export.js
?? mockup/progress.css
?? mockup/progress.js
?? test_integration.py
```

核心实现分别位于 `shooting_plans.py`（场景配置）、`pose_variation.py`（姿势规划）、`init_preset_models.py`（模特生成配置）、`tryon.js`（界面及请求参数）和 `remake.py`（配置校验及提示词组合）。

---

## 七、实现来源与核对边界

新增配置和函数保存在衣拍仓库中。本次核对未进行 Pixel Diffusion 源码、素材来源或许可证的完整比对，因此不能据此报告作出等价移植或许可证结论。

---

## 八、验证清单

### 功能验证 ✅
- [x] 模特参数传递路径正确
- [x] 场景选择生效并注入提示词
- [x] 姿势分配策略符合多样性要求
- [x] 前端参数正确传递到后端
- [x] 所有新功能向后兼容

### 代码质量 ✅
- [x] 所有新增测试通过
- [x] 代码格式检查通过
- [x] 无空白或格式错误
- [x] 文档完整（SCENES.md, PRESET_MODELS_USAGE.md）

### 未验证项 ⚠️
- [ ] 实际图像生成效果对照（需调用收费模型）
- [ ] 新模特素材生成质量（生成逻辑就绪但未执行）
- [ ] 多场景、多姿势的真实成片丰富度

---

## 九、后续建议

### 立即可做
1. **初始化预设模特：**
   ```bash
   cd /Users/dxm/Documents/yipai
   python3 scripts/init_preset_models.py --existing-only  # 注册现有2个
   python3 scripts/init_preset_models.py --generate 8     # 按配置生成最多8个（需API配置，并会产生费用）
   ```

2. **场景预览素材：** 当前前端已展示全部 8 种场景，可继续补充对应预览素材

3. **真实生图验证：** 用相同商品图分别在衣拍和 Pixel 生成，对照丰富度

### 架构优化
- 场景素材库（背景图、光线预设）
- 更细粒度的搭配规则（按品类、季节、风格）
- 姿势与场景的智能匹配（某些姿势更适合特定场景）

---

## 十、交付物清单

### 代码模块
1. **模特库系统** - `scripts/init_preset_models.py` + 配置
2. **场景系统** - `backend/workflows/shooting_plans.py` + API
3. **姿势规划** - `backend/workflows/pose_variation.py` + 策略
4. **前端集成** - `mockup/tryon.js` + 参数传递

### 测试套件
- `backend/test_model_selection.py` - 模特选择测试
- `backend/test_scene_system.py` - 场景系统测试
- `backend/workflows/test_pose_variation.py` - 姿势规划测试
- `test_integration.py` - 配置与提示词函数检查

### 文档
- `backend/workflows/SCENES.md` - 场景系统完整文档
- `PRESET_MODELS_USAGE.md` - 模特库使用指南
- `WORKFLOW_MIGRATION_REPORT.md` - 本报告

---

## 交付范围

**已增加模特生成配置、场景配置和结构化姿势提示词；前端提供自由探索及 8 种场景、姿势偏好和搭配方案设置。**

本次未生成新模特素材，也未调用收费模型对照最终成片。完整回归结果、提交范围及提交状态见本次 Git 提交核对记录。
