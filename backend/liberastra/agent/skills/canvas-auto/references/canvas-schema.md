# 画布节点字段

## 输入节点 `input`

```json
{"kind": "input", "mediaKind": "image|video|audio|text|character", "assetId": null, "text": "", "varName": "input_text_1", "characterId": null, "characterSlot": "front|side|back"}
```

- 图片、视频、音频用 `assetId`；文本用 `text`；角色用 `characterId` 与 `characterSlot`。
- 文本输入可被下游用 `{{varName}}` 引用。
- 角色输入在下游按槽位展开。

## 功能节点 `function`

```json
{"kind": "function", "group": "", "pack": "", "values": {}, "prompt": "", "outputKind": "image|video|audio|text", "bindings": {}, "varName": "output_image_1"}
```

- `pack` 是工作流包名，`values` 是包参数，`prompt` 是提示词。
- `bindings` 把输入槽映射到上游变量名；未绑定槽按类型顺序自动匹配。绑定不代替连线，变量来源必须是直接上游节点。
- 槽位名以 `list_workflows` 返回的 manifest 为准。

### 功能节点创建顺序

1. `canvas_add_node` 创建空白 `kind=function`，不要带 `pack`、`outputKind` 或 `menu`。
2. `list_canvas_menu` 找功能入口，`canvas_apply_menu` 套用；会自动解析工作流或模型并补建必填输入。
3. 没有合适菜单时 `list_workflows` + `canvas_apply_pack`。
4. 用 `canvas_get_node_schema` 读输入槽、参数规格和完整 `values`，再用 `canvas_update_node` 写 prompt、varName、bindings 和整份 values。
5. 不要直接改功能节点的 `pack`/`outputKind`；这两个字段由套装工具维护。

## 工具节点：拼接 `concat`

UI 显示为「工具」和「图片拼接 / 视频拼接 / 音频拼接 / 音频提取」，内部 `kind` 仍是 `concat`；这是原生工具节点，不绑定工作流，也不走 `canvas_apply_menu`。音频提取用 `data.toolId=audio_extract`、`data.audioMode=whole|tail`、`data.tailSeconds`。

```json
{"kind": "concat", "mediaKind": "image|video|audio", "order": [], "layout": "horizontal|vertical|grid", "columns": 2, "gap": 4, "gapColor": "#FFFFFF", "varName": "output_image_1"}
```

- 只接收同类型媒体。
- 图片拼接支持横排、竖排、网格；`order` 决定顺序。音频提取只接一个视频或音频输入；`whole` 保留完整音轨，`tail` 取最后 `tailSeconds` 秒。
- 网格是行优先：先连的 N 张在第一行，接着的 N 张在第二行。要 2 行 N 列（每列一个分镜的首尾帧），先连全部首帧，再连全部尾帧，`columns=N`。

## 语音节点 `speech`

```json
{"kind": "speech", "mode": "tts|asr", "text": "", "presetId": "", "voiceRecordId": null, "providerId": null, "varName": "output_audio_1"}
```

- tts 文本支持 `{{varName}}`。
- asr 接收音频或视频；其他节点连入会被拒绝。

## 连线规则

- 目标不能是输入节点。
- 拒绝自环、重复边和成环。
- 拼接节点检查来源产物类型。
- asr 只接收音频/视频。

## 预检

执行前保存画布并预检。常见失败：缺少资产、变量名重复、提示词为空、槽位类型不匹配、拼接节点类型不一致。先修节点，再重新预检。
