# 预设模特库使用指南

## 概述

生成脚本提供 8 种多样化模特配置，覆盖不同风格、年龄感和气质。这些配置不等于已生成或注册 8 张素材；现有两张模特可直接注册，新素材需另行执行生成并检查结果，本次未调用收费模型生成。

## 模特配置

### 女性模特（4个）

1. **清纯甜美女模特**
   - 年龄：20-23岁
   - 风格：清新自然，邻家少女感
   - 特征：圆润脸型，大眼睛，黑色长直发，温柔笑容

2. **优雅知性女模特**
   - 年龄：28-32岁
   - 风格：气质优雅，职业精英感
   - 特征：精致妆容，中长波浪发，自信从容的表情

3. **酷飒个性女模特**
   - 年龄：24-27岁
   - 风格：时尚个性，酷飒帅气
   - 特征：利落短发或高马尾，立体五官，微带冷感的气场

4. **健康活力女模特**
   - 年龄：23-26岁
   - 风格：健康阳光，运动感强
   - 特征：小麦肤色，马甲线身材，充满活力的神采

### 男性模特（4个）

1. **阳光少年男模特**
   - 年龄：20-24岁
   - 风格：阳光青春，清新少年感
   - 特征：清秀五官，短发整洁，温暖笑容

2. **成熟稳重男模特**
   - 年龄：30-35岁
   - 风格：成熟大气，商务精英感
   - 特征：立体五官，短发精干，沉稳自信的气质

3. **型格潮流男模特**
   - 年龄：25-28岁
   - 风格：时尚型男，潮流个性
   - 特征：个性发型，棱角分明，街头时尚感

4. **斯文儒雅男模特**
   - 年龄：26-30岁
   - 风格：温文尔雅，书卷气质
   - 特征：文艺范，戴细框眼镜或不戴，温和内敛的表情

## 初始化命令

### 仅注册现有模特（不调用收费模型）

```bash
cd /Users/dxm/Documents/yipai
python3 scripts/init_preset_models.py --existing-only
```

### 预检模式（查看将生成的模特，不实际写入）

```bash
python3 scripts/init_preset_models.py --generate 8 --dry-run
```

### 按配置生成最多 8 个多样化模特（需要 Image2 API 配置，执行会产生费用）

```bash
python3 scripts/init_preset_models.py --generate 8
```

### 生成部分模特

```bash
# 生成前 4 个（女性模特）
python3 scripts/init_preset_models.py --generate 4

# 生成前 6 个（女性模特 + 部分男性模特）
python3 scripts/init_preset_models.py --generate 6
```

## API 配置

如需生成新模特，需在 `.env.local` 中配置：

```bash
IMAGE2_GATEWAY_API_KEY=your_api_key_here
IMAGE2_UUAP_ID=your_uuap_id_here
```

## 数据库结构

模特数据存储在 `backend/data/jobs.sqlite3` 的 `models` 表中：

```sql
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    image_path TEXT NOT NULL,
    is_preset INTEGER NOT NULL DEFAULT 1,
    visitor TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL
)
```

- `is_preset=1`: 预设模特（所有用户共享）
- `is_preset=0`: 用户自定义模特

## API 端点

### 获取模特列表

```
GET /api/models
```

返回所有预设模特和当前用户的自定义模特。

### 获取模特图片

```
GET /api/models/{model_id}/image
```

## 工作流集成

模特参数通过以下路径传递：

1. 前端选择模特 → `POST /api/jobs` 顶层 `modelId`，另有 `model: 'male' | 'female'` 性别字段
2. `prepare_tryon_inputs()` 验证模特访问权限，并将该模特图片保存为任务私有 `model` 角色快照
3. `generate()` 将身份图随商品图传入图片服务，`build_tryon_prompt()` 明确其只控制人物身份
4. `model` 性别字段用于提示词的“成年男性／成年女性”描述，不能代替具体模特身份图

## 测试验证

运行测试确保模特参数正确传递：

```bash
python3 backend/test_model_selection.py
```

测试覆盖：
- ✓ 模特性别参数传递
- ✓ 模特身份图场景
- ✓ 参考图场景
- ✓ 参考图+模特身份图场景
- ✓ 多候选图姿势变化
- ✓ 多样化模特配置定义

## 注意事项

1. **不实际调用收费模型**：使用 `--dry-run` 可以预检配置而不生成图片
2. **原创提示词**：所有风格描述均为原创，未复制 Pixel 的提示词文本
3. **向后兼容**：保留现有 2 个预设模特（预设女模特、预设男模特）
4. **避免重复**：脚本会检查同名模特，避免重复注册
5. **图片格式**：所有模特图片统一转换为 JPEG 格式存储

## 扩展说明

如需添加更多模特风格，编辑 `scripts/init_preset_models.py` 中的 `diverse_configs` 列表：

```python
diverse_configs = [
    {
        'name': '模特名称',
        'gender': 'female' 或 'male',
        'desc': '年龄描述',
        'style': '风格和外貌特征描述'
    },
    # ...
]
```
