# Phase 5 评估门禁（默认关闭）

> 状态：**未开启**（`operations.colorGrade.enabled=false`，`operations.pose.enabled=false`）  
> 本文件为评估材料与风险记录，**不是**上线授权。

## 调色（color-grade）

| 项 | 结论 |
|---|---|
| 候选 LoRA | `QIE-2511-Color-Grade-Transfer-LoRA.safetensors`（140 已有） |
| 模型家族 | **Qwen-Image-Edit-2511**：需 `qwen_image_edit_2511_fp8mixed` + `qwen_2.5_vl_7b_fp8_scaled` + `qwen_image_vae` |
| 节点 | `ColorMatch` / `ColorMatchV2` 在 140 `/object_info` 中存在 |
| 与 2.1 UC | **不兼容**，不可塞进通用 edit |
| 模板 | `workflows/qwen-image-color-grade.json`（评估草稿） |
| 140 实测归档 | **未做**（输入/输出路径、显存峰值、成功/失败样本待补） |
| 开关 | 保持 `enabled: false`；调用返回「调色工作流未验证」 |

## 换姿（pose-transfer）

| 项 | 结论 |
|---|---|
| 候选 LoRA | `VNCCS_QI2_PoseStudioV1.1.safetensors`（140 已有） |
| 槽位 | **反序**：`image_1=姿态图`，`image_2=人物原图` |
| 预处理 | LiberAstra 依赖透明底压白；OpenClaw 侧尚无等价节点保证 |
| 模板 | `workflows/qwen-image-pose.json`（评估草稿，默认 UC 底模待验证身份保持） |
| 140 实测归档 | **未做** |
| 开关 | 保持 `enabled: false`；调用返回「换姿工作流未验证」 |

## 开启前置条件

1. 在 140 完成至少一组成功样本 + 失败边界记录（路径、耗时、显存、原因）。  
2. 终审（Antigravity）确认评估报告完整。  
3. 才允许把对应 `operations.*.enabled` 设为 `true`。
