# 衣拍：手机前端与 Image2 后端

当前版本已经接入真实 Image2 生图，不再使用前端合成模拟结果。

底部导航为「创作 / 社区 / 我的」。创作页只放开拍与拍同款入口；个人信息与创作历史在「我的」，社区支持效果图、商品原图和心得的主动发布与撤回。详见 [个人页与社区说明](../衣拍_个人页与社区说明_v1.1.md)。

## 启动

在项目根目录执行：

```sh
python3 -m pip install -r requirements.txt
YIPAI_PORT=8018 python3 -m backend.server
```

打开 `http://127.0.0.1:8018/`。不要再用 `python3 -m http.server`：静态服务器没有生成接口。

在项目根目录 `.env.local` 设置服务端 API Key（文件已被 Git 忽略）：

```dotenv
IMAGE2_GATEWAY_API_KEY=<密钥>
```

也可通过 `IMAGE2_ENV_FILE=/绝对路径/.env.local` 指定已有配置文件。若网关要求接入方标识，可额外设置 `IMAGE2_UUAP_ID`。环境变量优先于文件，密钥不会返回前端。`YIPAI_PORT` 默认 `8000`；`YIPAI_DATA_DIR` 默认为 `backend/data`。

## 已实现

- 无登录的匿名会话，HttpOnly Cookie；不同访客任务和原图、成品图互相隔离。
- 上传商品原图，附加所选男女模特参考图，向指定网关发送 `gpt-image-2.5-flare` 请求。
- 开拍只需单张商品图和模特选择；拍同款支持上装、下装、连体服装，至少一张拍摄参考照，最多 8 张独立画面参考、1 张模特身份图和 4 张按商品归属的细节图。每张参考生成 1、2 或 3 张独立成片，默认 3 张，总计最多 24 张。
- 异步任务与轮询，离开页面或刷新后仍可在创作历史找回；SQLite 持久化。
- 单用户最多一个进行中任务，全局最多十个排队任务、两个并发调用。
- 幂等提交，重发相同请求编号不会再次调用模型。
- 输入格式、体积、尺寸与解码校验；原图去除附带元数据。
- 使用 `1024x1536` 竖版输出、`high` 质量及 300 秒请求超时。
- 服务端在成品像素中合成“衣拍 · 人工智能生成”水印；成功任务只交付带水印图片。
- 重新生成复用原商品、画面参考、模特身份和细节图；旧结果不覆盖。保存和分享均使用服务端成品，多图结果可逐张查看或打包下载。
- 失败状态、删除历史记录；运行中任务禁止删除。
- 服务进程重启时，把尚未完成的本地任务标为失败，不自动重复调用计费接口。
- 手机端创作工作台、图片全屏查看和任务路由恢复；页面细节和验收记录见 [前端优化验收](../testing/2026-11-11/前端优化验收.md)。

## API

| 方法与路径 | 用途 |
|---|---|
| GET `/api/session` | 建立匿名会话，返回配置是否可用，不返回密钥 |
| POST `/api/jobs` | 参数：`image` Data URL、`model` (`female` / `male`)、UUID `idempotencyKey` |
| GET `/api/jobs` | 当前访客最近 100 条任务 |
| GET `/api/jobs/{id}` | 状态：queued、running、succeeded、failed |
| GET `/api/jobs/{id}/input` | 当前访客的原商品图 |
| GET `/api/jobs/{id}/input-{n}` | 当前访客任务保存的服装、画面、人物或细节参考图 |
| GET `/api/jobs/{id}/result` | 成功任务的带水印结果 |
| GET `/api/jobs/{id}/result-{n}` | 多图任务中的第 n 张独立成片 |
| GET `/api/jobs/{id}/download.zip` | 打包下载当前任务全部独立成片 |
| DELETE `/api/jobs/{id}` | 删除当前访客的已结束任务与其图片 |

开拍使用单图 `POST /api/jobs`，不携带拍同款草稿。拍同款也使用该接口，传入 `workflowType: 'remake'` 和角色图片。`model` 只传 `female` 或 `male`；选择模特库时额外传 `modelId`。上传人物图则放入 `inputImages` 的 `model` 角色，两者只能选一个：

```js
{
  image: 'data:image/jpeg;base64,...', // 第一件商品，兼容旧单图接口
  model: 'female',
  idempotencyKey: 'UUID',
  workflowType: 'remake',
  workflowConfig: {clothing_mode: 'multi', output_count: 3, instruction: ''},
  inputImages: [
    {role: 'upper', image: 'data:image/jpeg;base64,...'},
    {role: 'lower', image: 'data:image/jpeg;base64,...'},
    {role: 'reference', image: 'data:image/jpeg;base64,...'},
    {role: 'model', image: 'data:image/jpeg;base64,...'},
    {role: 'detail', garmentRole: 'upper', image: 'data:image/jpeg;base64,...'}
  ]
}
```

`clothing_mode: 'single'` 时使用一张 `single` 角色商品图；上下装模式可只上传 `upper` 或 `lower`。每张参考分别调用生成接口，不混合多张画面的场景。细节图的 `garmentRole` 必须指向本次已上传的主商品。

旧版单图拍同款 `image` / `reference` 请求和多图 `workflowType: 'tryon'` API 继续兼容。可选配置独立的 `ANALYZE_API_KEY` 分析拍法；未配置时，图片服务直接读取实际参考图。分析服务与图片服务分别使用各自的密钥。

所有图片保存在任务目录，API 返回的 `inputImages` 只包含角色和受当前会话保护的 `url`，不会把 base64 保存进任务配置。模特库照片在提交时复制为任务快照，后续删除模特库条目不会破坏旧任务的重新生成。输入总大小上限 20 MB、请求上限 30 MB；前端上传时会压缩图片。

## 验证

```sh
python3 -m unittest discover -s backend -v
node --check mockup/app.js
node --test testing/frontend.test.cjs
```

自动化测试使用隔离临时数据库和模拟网关，不产生模型费用。真实服装生成与手机端流程测试结果见 [2026 年 11 月 10 日测试报告](../testing/2026-11-10/测试报告.md)；真实测试会产生模型调用。

无费用的界面演示可运行 `python3 testing/preview_server.py --port 8019`，会显示固定样例和模拟排队/生成状态，数据存入临时目录。增加 `--empty` 查看空工作台；增加 `--large-text` 可验证 200% 根字号。演示不会处理上传图片，也不会访问图像生成服务；真实生成使用 8018 工作台服务。

## 当前边界

本地单进程版本只绑定回环地址，尚未部署公网。依赖当前浏览器会话找回历史；清除 Cookie 或换设备后无法恢复。暂不含付费额度、多人账号、自动内容审核或 HEIC 服务端转码。商品还原效果仍需人工核对，API 成功不等同于所有商品细节准确。

后端依赖 macOS 的苹方字体绘制中文水印；跨系统部署时需配置可用中文字体并验证水印。正式公开服务需另外配置 HTTPS、进程托管、持久化存储、清理策略及供应商配额。

## 模特管理

### 初始化预设模特

首次运行或重置数据库后，需要初始化预设模特：

```sh
python3 scripts/init_preset_models.py --existing-only
```

该命令将 `mockup/assets/female-model.png` 和 `male-model.png` 注册到数据库的 `models` 表，用户可在前端模特选择界面看到这两个预设模特。

脚本支持以下选项：

- `--dry-run`：预检模式，不实际写入数据库
- `--existing-only`：仅注册现有模特图片，不生成新的
- `--generate N`：通过 Image2 生成 N 个多样化预设模特（需配置 API Key）

生成多样化预设模特示例：

```sh
python3 scripts/init_preset_models.py --generate 8
```

脚本会自动检查重复，重复运行不会重复插入相同模特。

### 模特卡素材生成

`python3 scripts/generate_models.py` 使用同一网关生成主页男女模特素材；`--dry-run` 只做配置预检，已存在素材会跳过。提示词见 `scripts/model-prompts.json`。
