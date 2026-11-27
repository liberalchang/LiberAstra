---
title: Comfy Provider Plus 二次开发需求
note_id: agent-oc-comfy-provider-plus-requirements
type: requirement
status: draft
tags:
  - OpenClaw
  - ComfyUI
  - 插件
updated: 2026-11-28
summary: 基于官方 Comfy provider 二次开发 comfy-provider-plus，支持文生图、单图与多图参考，并评估调色和换姿。
---
# Comfy Provider Plus 二次开发需求

## 结论

在官方 `@openclaw/comfy-provider` 上开发一个替代插件，包名定为 `@openclaw/comfy-provider-plus`，插件 id 使用 `comfy-plus`。它继续把局域网 ComfyUI 当作执行后端，第一版必须完成文生图、单图编辑和最多 16 张参考图；调色与换姿先作为独立能力评估，不塞进通用出图工作流。

官方插件不修改。上线时停用官方 `comfy`，只启用 `comfy-plus`，避免两个插件同时注册图片 provider 后由模型自行猜测。

## 已核实的基础

- 官方插件版本 `2026.11.10`，安装在 `~/.openclaw/extensions/comfy`，provider id 为 `comfy`。
- 它每次只上传并注入一张参考图，配置项只有 `inputImageNodeId` 和 `inputImageInputName`。
- ComfyUI 位于 `10.10.12.140:8188`，进程工作目录是 `/home/ps/workspace/remote_bundle/ComfyUI`，输入目录是其下的 `input/`。
- `TextEncodeQwenImage21` 的 `images` 输入支持 `image_1` 到 `image_16`。没有参考图时，它输出 1024 级空 latent；有参考图时，输出与第一张图比例一致的 latent。
- 140 上已确认存在：
  - `qwen-image-2.1-UC-int8_convrot.safetensors`
  - `qwen-image-2.1-uncensored-lora.safetensors`
  - `qwen3vl_8b_int8_convrot.safetensors`
  - `qwen_image_2.1_vae_bf16.safetensors`
  - `QIE-2511-Color-Grade-Transfer-LoRA.safetensors`
  - `VNCCS_QI2_PoseStudioV1.1.safetensors`
- 当前通用工作流已验证：文生图产物 `qwen-image-uc_00060_.png`；单图编辑产物 `qwen-image-uc_00061_.png`，尺寸 704×1504。
- 当前图片超时已配置为 600 秒，默认模型为 `comfy/workflow`，回退为 `google/gemini-3.1-flash-image`。

## 目标与边界

### 第一版必须完成

- 文生图：只有提示词时不读取参考图。
- 图生图：1 到 16 张参考图全部上传到 ComfyUI，并按顺序接入 `images.image_1` 至 `images.image_16`。
- 保持官方插件现有的提交、轮询、下载和错误处理行为。
- 支持宽度、高度、采样步数、CFG、负面提示词、LoRA 开关和 LoRA 强度。
- 默认仍使用已验证的 UC 模型、UC LoRA、25 步、CFG 1、euler/simple。
- 图片任务超时默认 600 秒，且可配置。
- 提交前把提示词中明确的图片指代规范化为 `image_N`，并与实际上传槽位一致。

### 明确不在第一版

- 不改 ComfyUI 本体，不在 140 上新增自定义节点。
- 不实现视频、音乐、局部重绘、多图分别控制。
- 不把调色或换姿伪装成通用编辑提示词的自动分支。
- 不保留对官方单图配置键的兼容层；这是新插件，配置按新 schema 写。

## 插件与运行方式

- npm 包名：`@openclaw/comfy-provider-plus`
- 插件 id：`comfy-plus`
- provider id：`comfy-plus`
- 安装形态：独立 OpenClaw 插件，用官方插件代码做上游基线，不直接改 `extensions/comfy`。
- 模型引用：`comfy-plus/workflow`
- 启用后把默认图片模型改为 `comfy-plus/workflow`；官方插件停用前不得让两个 provider 同时成为默认候选。

插件只做 OpenClaw 与 ComfyUI 之间的适配：接收规范化后的图片请求、选择工作流、上传图片、填参数、提交并取回结果。模型选择、技能匹配和 MCP 选择仍由 OpenClaw 原有工具路由负责。

## 功能需求

### 工作流选择

| 条件 | 工作流 | 结果 |
|---|---|---|
| 无参考图 | `qwen-image-t2i.json` | 文生图，默认 1024×1024，可覆盖宽高 |
| 1–16 张参考图 | `qwen-image-edit.json` | 图生图，默认沿第一张图的比例，`resolution` 默认 1024 |
| `operation=color-grade` | `qwen-image-color-grade.json` | 调色，仅在能力验证通过后启用 |
| `operation=pose-transfer` | `qwen-image-pose.json` | 换姿，仅在能力验证通过后启用 |

未识别操作、缺少该操作的必填图片或图片超过 16 张时，插件必须在提交前返回明确错误，不能静默退回文生图。

### 提示词与图片槽位

图片槽位是固定的：`TextEncodeQwenImage21` 提供 `image_1` 到 `image_16`。140 上的 Qwen 编码器按这个顺序把图片放入视觉序列，模板本身不包含“图1”“第一张”等编号。因此不能假设模型能自然理解用户的图片指代，必须在提交前规范化提示词。

- 上传顺序就是槽位编号：第一张附件进入 `image_1`，第二张进入 `image_2`，依次类推。
- “第一张、图一、图片1、第二张参考图”等明确序号，统一替换成对应的 `image_N`。
- “左边那张、衣服那张”等没有结构位置的描述不得猜测。调用方另外提供图片角色时按角色映射；否则保留原词，要求调用方改成明确序号。
- 提示词中的图片序号大于实际上传数量时，提交前拒绝并说明缺少的槽位。
- 替换只处理明确的图片指代，不改普通句子中的数字、数量或尺寸。
- 提交记录保留原始提示词、规范化后的提示词和附件到 `image_N` 的映射，便于核对错图。

### 多图输入

- 按调用方给定顺序上传，上传文件名保持唯一且可追溯。
- 空文件、超过配置大小的文件、ComfyUI 拒绝的格式要返回具体序号和原因。
- 一张上传失败则取消整次请求，不提交不完整工作流。
- 图生图工作流只连接实际存在的图片输入，不能把空路径送进 Qwen 编码器。

### 可配置参数

通用参数：`prompt`、`negativePrompt`、`seed`、`steps`、`cfg`、`width`、`height`、`timeoutMs`。

模型参数：`unetName`、`clipName`、`vaeName`、`loraName`、`loraStrength`、`loraEnabled`。

图生图参数：`resolution`、`imageCount`。`imageCount` 必须等于实际图片数。

参数写入必须通过节点 id 和输入名配置，不允许在代码里搜索整个工作流 JSON 做模糊替换。

## 调色与换姿评估

两者都有现成模型资产，但还没有被当前通用工作流验证，因此第一阶段只做可行性结论。

### 调色

- 候选资产：`QIE-2511-Color-Grade-Transfer-LoRA.safetensors`。
- 需要的输入预计为“原图 + 色彩参考图 + 可选保护说明”。仅有一张图时不能称为调色。
- 验证标准：同一原图在两个明显不同的色彩参考下产生可辨识的色彩变化，人物身份、构图和主要物体不漂移。
- 未达到标准则保持 `enabled: false`，调用时返回“调色工作流未验证”，不要用普通编辑顶替。

### 换姿

- 候选资产：`VNCCS_QI2_PoseStudioV1.1.safetensors`。
- 需要的输入预计为“人物原图 + 姿态参考图”。姿态图不能只靠文字描述冒充。
- 验证标准：输出姿态接近姿态参考，同时人物身份明显保留；失败时记录是身份漂移、姿态不生效，还是工作流节点不兼容。
- 换姿可能需要独立的姿态预处理节点或不同模型家族。若 140 当前节点不满足，结论写为“缺节点”，不临时安装未审核节点。

评估产出一份记录：所用工作流、输入输出路径、成功或失败、显存峰值、耗时和不可用原因。通过后才把操作暴露给插件。

## 配置草案

```yaml
plugins:
  entries:
    comfy:
      enabled: false
    comfy-plus:
      enabled: true
      config:
        mode: local
        baseUrl: http://10.10.12.140:8188
        timeoutMs: 600000
        workflows:
          t2i: /Users/liber/.openclaw/workspace/workflows/comfy-plus/qwen-image-t2i.json
          edit: /Users/liber/.openclaw/workspace/workflows/comfy-plus/qwen-image-edit.json
          colorGrade: /Users/liber/.openclaw/workspace/workflows/comfy-plus/qwen-image-color-grade.json
          pose: /Users/liber/.openclaw/workspace/workflows/comfy-plus/qwen-image-pose.json
        operations:
          colorGrade:
            enabled: false
          pose:
            enabled: false
```

实际字段名以插件 schema 为准。密钥、局域网地址和启用状态通过 OpenClaw 配置命令修改，不手改不受校验的配置副本。

## 验收

1. 无参考图生成一张图，ComfyUI 历史记录中没有图片加载节点执行。
2. 1、2、16 张参考图均能按顺序进入编码器；17 张在本地被拒绝。
3. 第一张参考图为非方形时，输出比例跟随该图，而不是固定 1024×1024。
4. “把第二张图的衣服换到第一张人物身上”被规范化为 `image_2` 和 `image_1`，且实际接线顺序与之一致。
5. “图3”在只上传两张时被拒绝；“两个人”“1024 宽”等非图片指代不被替换。
6. 宽高、步数、CFG、负面提示词、种子和 LoRA 强度能在结果元数据或工作流提交体中核对。
7. ComfyUI 不可达、上传失败、执行失败、超时四类错误都能返回不含密钥和本地敏感路径的明确原因。
8. 600 秒超时测试使用真实配置值，不依赖临时改小的测试超时。
9. 官方 `comfy` 停用后，默认请求命中 `comfy-plus/workflow`；启用前的回退模型配置不丢失。
10. 调色和换姿在验证开关关闭时不可调用，开启前各有一组成功样本和失败边界记录。

## 实施顺序

1. 复制官方插件为独立包，改插件 id、包名和 provider 注册点。
2. 先把现有已验证的单图工作流迁入新包并跑通，保证替换官方插件后无功能倒退。
3. 扩展为真实多图上传和按数量接线。
4. 补参数化节点映射、错误分类和 1/2/16 张回归测试。
5. 用 140 现有资产分别验证调色、换姿；只有满足验收标准才打开操作开关。
