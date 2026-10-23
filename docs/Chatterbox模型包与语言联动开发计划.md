# Chatterbox 模型包与语言联动开发计划

> 状态：待开发。按本方案实施，未知 `model` 直接返回错误，不回退到 `multilingual_v3`。

在 `services/speech` 中支持 11 个 Chatterbox 模型与语言包，并在系统设置与全部 TTS / 配音页面做模型包和语言联动。

## 一、模型与语言矩阵

统一 11 个 TTS 模型包 ID。兼容旧值 `multilingual`（等同 `multilingual_v2`）和 `standard`。

| 模型包 ID | 界面名称 | 底层类 / 权重 | 支持语言 |
|---|---|---|---|
| `multilingual_v3` | Chatterbox-Multilingual V3 | `ChatterboxMultilingualTTS` (`t3_mtl23ls_v3.safetensors`) | 23 种语言 |
| `multilingual_v2` | Chatterbox-Multilingual V2 | `ChatterboxMultilingualTTS` (`t3_mtl23ls_v2.safetensors`) | 23 种语言 |
| `turbo` | Chatterbox-Turbo | `ChatterboxTurboTTS(nano=False)` (`ResembleAI/chatterbox-turbo`) | `en` |
| `nano` | Chatterbox-Nano | `ChatterboxTurboTTS(nano=True)` (`ResembleAI/chatterbox-nano`) | `en` |
| `standard` | Chatterbox | `ChatterboxTTS` (`ResembleAI/chatterbox` 英文权重) | `en` |
| `zh-cmn` | Chinese (zh-CMN) | `ResembleAI/Chatterbox-Multilingual-zh-cmn` (`t3_zh_cmn.safetensors` + `s3gen_v3.pt`) | `zh` |
| `es-mx` | Latam Spanish (es-MX) | `ResembleAI/Chatterbox-Multilingual-es-mx-latam` (`t3_es_mx_latam.safetensors` + `s3gen_v3.pt`) | `es` |
| `pt-br` | Brazilian Portuguese (pt-BR) | `ResembleAI/Chatterbox-Multilingual-pt-br` (`t3_pt_br.safetensors` + `s3gen_v3.pt`) | `pt` |
| `es-es` | Spain Spanish (es-ES) | `ResembleAI/Chatterbox-Multilingual-es-es` (`t3_es_es.safetensors` + `s3gen_v3.pt`) | `es` |
| `pt-pt` | Portugal Portuguese (pt-PT) | `ResembleAI/Chatterbox-Multilingual-pt-pt` (`t3_pt_pt.safetensors` + `s3gen_v3.pt`) | `pt` |
| `hi` | Hindi (hi) | `ResembleAI/Chatterbox-Multilingual-hi` (`t3_hi.safetensors` + `s3gen_v3.pt`) | `hi` |

## 二、Speech 后端服务改造（`services/speech`）

1. **依赖版本固定**（`services/speech/requirements.txt` 与 `services/speech/Dockerfile`）：
   - PyPI 上的 `chatterbox-tts==0.1.7` 发布于 2026-03，尚未包含 Nano 与 Multilingual V3。需要将 `chatterbox-tts` 指向 GitHub 主分支源码安装（并保留随后钉回 CUDA 版 `torch` / `torchaudio` 的步骤），确保 `ChatterboxTurboTTS(nano=True)` 与 V3 权重加载可用。
2. **模型目录组装与加载器**（`services/speech/engine.py`）：
   - 移除 `kind = model if model in ... else "multilingual"` 的静默回退；未知 `model` 直接抛出 `ValueError`（由 `server.py` 转为 HTTP 400）。
   - **关键细节**：6 个单语言包中，除 `zh-cmn` 外，其余 5 个仓库只放了 `t3_*.safetensors`、`s3gen_v3.pt` 和分词器，**没有放 `ve.pt` 和 `conds.pt`**（官方 Space 也是先从 `ResembleAI/chatterbox` 下载这两个底座文件再合并）。
   - 为每个单语言包在 `HF_HOME` 下准备独立组装目录：从 `ResembleAI/chatterbox` 拉取 `ve.pt`、`conds.pt`、`grapheme_mtl_merged_expanded_v1.json`、`Cangjie5_TC.json`，从对应单语言包仓库拉取 `t3_<pack>.safetensors` 与 `s3gen_v3.pt`，在该组装目录内把 `s3gen_v3.pt` 软链/复制为 `s3gen.pt`，再调用 `ChatterboxMultilingualTTS.from_local(assembled_dir, device, t3_model=t3_filename)`。
   - **显存管理**：11 个模型每个约 1–2GB，不能全部常驻显存。`_tts` 改为最多保留 1 个已加载的 TTS 引擎；切换模型包时先卸载旧模型并执行 `torch.cuda.empty_cache()`，再加载新模型。
   - **语言校验与注入**：
     - `multilingual_v2` / `multilingual_v3`：校验 `language` 在 23 种语言内，传 `language_id=language`。
     - 6 个单语言包：强制使用该包的固定 `language_id`（`zh` / `es` / `pt` / `hi`）；若调用方传了不匹配的语言则报错。
     - `turbo` / `nano` / `standard`：仅支持英文，不向 `generate()` 传 `language_id`（这三个类的 `generate` 不接收该参数）。
     - **参考音频时长校验**：`Turbo` / `Nano` 内部要求参考音频 `> 5.0s`，若不足 5 秒捕获异常并转成可读的 400 错误提示。
3. **模型列表接口扩展**（`services/speech/server.py` `GET /api/v1/models`）：
   - 保留原有 `models` 数组兼容已有健康检查，同时返回完整目录 `tts_models`（含 `id`、`label`、`group`、`languages`）以及当前服务端默认模型。

## 三、LiberAstra 主后端改造（`backend/liberastra`）

1. **系统设置新增默认 Speech 模型包**：
   - `backend/liberastra/services/preferences.py`：`STR_SPECS` 增加 `"default_speech_model": "multilingual_v3"`（校验合法 ID）。
   - `backend/liberastra/api/routes/system.py`：`PreferencesUpdate` 增加 `default_speech_model: str | None`。
2. **模型透传与回退优先级**：
   - 优先级：**系统设置 `default_speech_model` > Provider 的 `extra.model` > `"multilingual_v3"`**。功能页不传模型名。
   - `backend/liberastra/services/providers.py`：`build_tts_adapter(record, db=db)` 在构造 `LiberSpeech` 时读取 `default_speech_model` 作为 `default_model`。
   - `backend/liberastra/providers/speech/liber_speech.py`：
     - 维护与 Speech 服务一致的模型包语言表；
     - `synthesize()` 根据当前 `model` 决定 `language`：单语言包固定为对应语言，英文模型固定为 `en`，多语言模型走 `language_from_voice(voice, params.get("language"))`。
   - **任务与路由透传**：
     - 文字转语音、快速创作、自定义素材、数字人口播都不在页面上选择模型。`TTSRequest.model` 留空时由适配器取系统默认。`quick.py` 与 `simple.py` 不新增 `tts_model`。

## 四、前端与 UI 设计（`frontend/src`）

1. **统一语言元数据**（升级 `frontend/src/components/SpeechLanguageSelect.tsx`）：
   - 集中定义 `SPEECH_MODELS`（分三组：**多语言模型**、**单语言精调包**、**英文专用模型**）及每个模型的 `languages` 列表。
   - `SpeechLanguageSelect` 接收系统设置里的默认模型包：
     - 若模型支持 23 种语言：下拉展示全部 23 种语言；
     - 若模型仅支持 1 种语言（如 `Chinese (zh-CMN)` 仅 `zh`，`Turbo` 仅 `en`）：下拉列表只展示该语言并自动选中，若原先选中的语言不在支持列表内则自动切回该模型唯一支持的语言。
   - 功能页不提供模型包下拉。系统设置页自己用分组下拉选择默认模型包。
2. **系统设置页**（`frontend/src/pages/SystemSettingsPage.tsx`）：
   - 新增卡片 **「默认语音合成（Liber Speech）」**：
     - 下拉框「默认模型包」：分组列出 11 个模型包，默认 `Chatterbox-Multilingual V3`。
     - 下方静态提示展示当前所选模型包支持的语言范围与特点（例如多语言 23 语种、中文精调包、Turbo 英文低延迟且支持 `[laugh]` 等副语言标签且克隆参考音频需大于 5 秒）。
3. **功能页只保留音色和语言**（`TtsPage.tsx`、`VideoQuickPage.tsx`、`VideoAssetsPage.tsx`、`VideoPackPage.tsx` 数字人口播）：
   - 配音服务选为 Liber Speech 时，界面仍然只有音色和语言，不增加模型包控件。
   - 现有缺口：快速创作、自定义素材、数字人口播只有「使用默认声音」时才显示语言；选了音色库后语言控件消失。文字转语音在选了音色库后改成只有 7 种语言的「朗读语言」。
   - 这四处在选中 Liber Speech 时，无论是否选用音色库，都显示按系统默认模型包过滤后的语言下拉。克隆音色仍传参考音频，语言只决定 `language_id`。
4. **文档与国际化**：
   - 更新 `frontend/src/i18n/ui-en.ts` 与 `docs/使用文档.md`，补充 11 个模型包的说明与语言对应关系。

## 五、涉及文件清单

- `services/speech/requirements.txt`、`services/speech/Dockerfile`
- `services/speech/engine.py`、`services/speech/server.py`
- `backend/liberastra/services/preferences.py`、`backend/liberastra/api/routes/system.py`
- `backend/liberastra/providers/speech/liber_speech.py`、`backend/liberastra/services/providers.py`
- `backend/liberastra/schemas/video.py`、`backend/liberastra/api/routes/videos.py`、`backend/liberastra/pipelines/quick.py`、`backend/liberastra/pipelines/simple.py`
- `frontend/src/api/client.ts`、`frontend/src/components/SpeechLanguageSelect.tsx`
- `frontend/src/pages/SystemSettingsPage.tsx`、`frontend/src/pages/TtsPage.tsx`、`frontend/src/pages/VideoQuickPage.tsx`、`frontend/src/pages/VideoAssetsPage.tsx`、`frontend/src/pages/VideoPackPage.tsx`
- `frontend/src/i18n/ui-en.ts`、`docs/使用文档.md`
- `backend/tests/test_speech_adapters.py`、`backend/tests/test_speech.py`
