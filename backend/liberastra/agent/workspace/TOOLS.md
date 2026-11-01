# 工具

## 画布工具（浏览器执行）

- `canvas_get_graph` / `canvas_get_node`：读取画布结构。改之前先读。
- `canvas_get_node_schema`：读取节点当前数据、执行目标、输入槽和参数规格。改属性前先读，避免猜字段名。
- `canvas_add_node`：加输入、功能、合成或语音节点。常用参数 `kind`、`media_kind`、`x`、`y`。
- `canvas_update_node`：改节点 data 字段，例如 `prompt`、`varName`、`text`、`values`、`bindings`。
- `canvas_connect` / `canvas_disconnect`：连线与断线。
- `canvas_set_binding`：把功能节点的输入槽绑定到某个上游变量名。
- `canvas_layout`：自动整理布局。
- `canvas_delete_nodes`：删除节点（需确认）。
- `canvas_run_nodes`：保存并提交生成任务（需确认，占用 GPU）。

画布工具由用户的浏览器立即执行，结果会回到这里。执行失败时看返回的 `error`，不要假设成功。

## 服务端工具

- `ask_user`：结构化提问，发出去后本轮结束，等用户回答。
- `load_skill` / `read_skill_file`：读取技能正文和参考文档。
- `save_skill`：保存用户技能（只写 SKILL.md）。
- `update_session_state`：记录技能进度和已确认内容，刷新后据此继续。
- `list_assets` / `get_asset` / `read_asset_text` / `list_characters`：查资源库、资产详情和角色库。
- `list_voices` / `list_music`：查音色库和背景音乐库。
- `list_canvas_menu` / `list_workflows` / `list_execution_specs`：查画布菜单实际配置、可用/默认工作流和完整参数规格。
- `generate_image` / `edit_image` / `generate_video` / `tts` / `asr`：一次性生成（需确认，走任务队列）。

## 约定

- 一次可以调多个工具，但彼此有依赖时分步做。
- 工具参数用 JSON。不要把自然语言塞进 `patch` 这类对象参数。
- 拿不到工具或模型不支持原生工具调用时，按系统提示里的 `<tool_call>` 文本协议输出。
- 工具结果里出现 `error` 时，把原因转述给用户，不要继续编造。
