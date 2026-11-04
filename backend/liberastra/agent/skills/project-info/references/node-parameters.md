# 节点属性

改参数前先 `canvas_get_node_schema(node_id)`。它返回当前 `data`、解析后的执行目标、媒体槽、完整输入规格和当前 `values`。

## 功能节点（function）

常用字段：

| 字段 | 说明 |
|---|---|
| `pack` | 工作流包名；由 `canvas_apply_menu` / `canvas_apply_pack` 设置 |
| `presetId` / `presetTitle` | 菜单项 id 和简称 |
| `subCapability` | 能力，如 `t2i`、`i2v_first`、`v2v_ref` |
| `targetType` / `targetId` / `providerId` | 当前执行目标 |
| `values` | 工作流参数，键值都是字符串；整份替换 |
| `prompt` | 提示词，支持 `{{变量名}}` 和 `<Picture n>` |
| `bindings` | 输入槽 → 直接上游变量名，如 `{"first_frame": "output_image_kf_1_1"}`；必须先连线 |
| `varName` | 输出变量名，全画布唯一 |
| `audioMode` | 数字人/动作迁移的声音来源 |
| `bgmPath` / `bgmVolume` | 背景音乐，`bgm/<文件名>`，音量 0–1 |

功能在创建时确定：`presetId` 已存在时，`canvas_apply_menu` 不能换功能，只能通过菜单允许的目标换工作流/模型；没有 `presetId` 但有 `pack` 或 `targetType/targetId` 的通用节点可以继续用 `canvas_apply_pack` 换工作流。语音节点的 `mode` 不能通过 `canvas_update_node` 修改。

修改 `values` 时：

1. `canvas_get_node_schema` 读出完整 `values`。
2. 只改目标键，保留其余键。
3. 整份写回：`canvas_update_node(node_id, {"values": {...完整值...}})`。

不要只传 `{"values": {"length": "124"}}`，否则其他参数会丢。

## 输入节点（input）

| 字段 | 说明 |
|---|---|
| `mediaKind` | `image` / `video` / `audio` / `text` / `character` |
| `assetId` / `assetName` | 媒体资产 |
| `maskAssetId` | 局部重绘蒙版 |
| `text` | 文本正文 |
| `varName` | 输出变量 |
| `characterId` / `characterSlot` | 角色输入；视角 `front/side/back/portrait/turnaround` |

## 工具节点：拼接（concat）

UI 显示为「工具」和「图片拼接 / 视频拼接 / 音频拼接」；内部 `kind` 仍是 `concat`，不绑定工作流，也不走 `canvas_apply_menu`。

| 字段 | 说明 |
|---|---|
| `mediaKind` | `image` / `video` / `audio` |
| `order` | 上游节点 id 顺序；连线时自动追加 |
| `layout` | 图片：`horizontal` / `vertical` / `grid` |
| `columns` | 网格列数 |
| `gap` / `gapColor` | 间隔像素、颜色 |
| `varName` | 输出变量 |

图片网格是行优先。要得到 2 行 N 列（每列上下是一个分镜的首尾帧），先连该组全部首帧，再连全部尾帧，`columns=N`。只生成首帧时，一行 N 张，第 N 张对应第 N 个分镜。

## 语音节点（speech）

| 字段 | 说明 |
|---|---|
| `mode` | `tts` / `asr` |
| `text` | TTS 文本，支持 `{{变量名}}` |
| `providerId` | 服务商 |
| `voiceRecordId` | 音色库条目 |
| `voice` / `model` | 服务商原生音色/模型 |
| `workflow` | Comfy 语音工作流 |
| `language` / `format` | 语言、输出格式 |
| `varName` | 输出变量 |

## 常见修改配方

### 改视频时长

1. `canvas_get_node_schema` 找 `values` 里的 `length`（帧）或 `duration`（秒）。
2. 读目标规格的 `fps`、`min`、`max`、`align_base`、`align_offset`。
3. 本地帧数：`frames = seconds * fps`，取最小满足 `k * align_base + align_offset >= frames` 的值，夹到 min/max。
4. 整份 `values` 写回。

### 换工作流

1. `list_canvas_menu(menu_id)` 看 `available_targets`。
2. `list_workflows(name)` 看输入规格。
3. `canvas_apply_menu` / `canvas_apply_pack` 绑定目标；已有上游时同时传 `bindings`（槽位 → 上游变量名），避免自动补建空输入节点。
4. 重新读 `canvas_get_node_schema`，补齐 `values` 和 `bindings`。

### 改图片拼接布局

`canvas_update_node(node_id, {"layout": "grid", "columns": 3, "gap": 4, "gapColor": "#FFFFFF"})`。

### 给视频节点加背景音乐

1. `list_music` 找文件名。
2. `canvas_update_node(node_id, {"bgmPath": "bgm/文件名.mp3", "bgmVolume": 0.2})`。

### 给语音节点选音色

1. `list_voices` 找 `id`。
2. `canvas_update_node(node_id, {"voiceRecordId": id, "providerId": provider_id})`。
3. 如果用的是服务商原生音色，改 `voice` / `model`，不要同时写 `voiceRecordId`。
