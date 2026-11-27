# 自测报告（验收矩阵 10 条）

> 日期：2026-11-28  
> 命令基线：`cd plugins/comfy-provider-plus && npm test`  
> 140 联调：`RUN_COMFY_140=1 npm test -- test/integration-140.test.ts`

| # | 验收标准 | 结果 | 命令 / 产物 | 证据摘要 |
|---|---|---|---|---|
| 1 | 无参考图生图，历史无 LoadImage | **通过** | `npm test` → `workflow-injector`；`RUN_COMFY_140=1` T2I | 单测断言 T2I JSON 无 LoadImage/images.*；140 history 实跑约 40s 通过 |
| 2 | 1/2/16 接线；17 本地拒绝 | **部分通过** | `workflow-injector` + `upload-and-errors`；140 单图 | N=1/2/16 接线单测通过；N=17 0 网络拒绝；140 实跑 N=1；**未实跑 N=2/16 满载** |
| 3 | 非方形首图比例跟随 | **通过（结构）** | `workflow-injector`；Phase0 `00061` 704×1504 | Edit `KSampler.latent_image=[5,2]` 断言通过；140 output2=LATENT 已取证 |
| 4 | 「第二张图…第一张人物」→ image_2/1 | **通过** | `slot-normalizer.test.ts` | 规范化含 `image_2`/`image_1`，`referencedSlots=[1,2]` |
| 5 | 图3+2 张拒绝；两个人/1024 宽保护 | **通过** | `slot-normalizer.test.ts` | 越界抛错；数量/尺寸不替换；桌子/左边那张边界覆盖 |
| 6 | 参数与 LoRA 旁路可核对 | **通过** | `workflow-injector.test.ts` | steps/cfg/seed/宽高/负面词写入断言；`loraEnabled=false` 删节点并重连 |
| 7 | 四类错误 + 脱敏 | **通过** | `upload-and-errors.test.ts` | 四码覆盖；路径/密钥脱敏正则断言；上传事务失败 |
| 8 | 真实 `600000` 超时配置 | **通过** | `timeout-600s.test.ts` | defaults/parse=`600000`；注入时钟跑满 deadline，错误含 `600s` 与 `timeoutMs:600000` |
| 9 | 停用 comfy 后命中 comfy-plus；回退不丢 | **通过（设计校验）** | `config-switch.test.ts`；`scripts/switch-to-comfy-plus.md` | primary=`comfy-plus/workflow`；fallbacks 含 `google/gemini-3.1-flash-image`；**未在本机改真实 OpenClaw 配置** |
| 10 | 调色/换姿关闭不可调用 | **通过** | `upload-and-errors` 路由；`docs/phase5-evaluation.md` | `enabled:false` 返回未验证错误；评估报告标明未实测归档 |

## 汇总

- 单元测试：`23 passed | 2 skipped`（无 `RUN_COMFY_140` 时集成跳过）
- 140 集成：`3 passed`（含 T2I + 单图 Edit）
- Phase 0：`docs/phase0-evidence.md`（门禁通过）
- Phase 5：保持关闭
