# LiberAstra 部署相关资源下载

## 1. 所有资源整合

仓库里没有记录百度网盘分享地址。整合包链接和提取码待补：

- 链接：待补充
- 提取码：待补充

## 2. LiberAstra 项目与 Windows 安装包

- 项目地址：<https://github.com/liberalchang/LiberAstra>
- Windows 安装包：<https://github.com/liberalchang/LiberAstra/releases/latest/download/LiberAstra-Setup.exe>
- 发布页：<https://github.com/liberalchang/LiberAstra/releases>

安装包自带 Python 运行时和已构建页面，目标电脑不用另装 Python 或 Node。装完后浏览器打开 `http://127.0.0.1:8000`。Ollama、ComfyUI 和语音插件不在这个安装包里。

语音插件另下 [LiberSpeech-Setup.exe](https://github.com/liberalchang/LiberAstra/releases/latest/download/LiberSpeech-Setup.exe)。

## 3. Ollama

安装包下载页：<https://ollama.com/download>

Windows 安装程序：<https://ollama.com/download/OllamaSetup.exe>

装好后默认地址是 `http://<主机>:11434`。在 LiberAstra 里添加类型为 Ollama 的服务提供方。下面两套是当前文档里用来写脚本和优化提示词的模型，用 `ollama pull` 拉取。

| 模型名 | 描述 | 下载链接 |
| --- | --- | --- |
| `orcarouter/Qwen3.8-27B-Uncensored:q4_K_M` | 27B 量化权重，用于脚本和提示词 | <https://ollama.com/orcarouter/Qwen3.8-27B-Uncensored> |
| `huihui_ai/gemma-4-abliterated:12b` | 12B 权重，用于脚本和提示词 | <https://ollama.com/huihui_ai/gemma-4-abliterated> |

```bash
ollama pull orcarouter/Qwen3.8-27B-Uncensored:q4_K_M
ollama pull huihui_ai/gemma-4-abliterated:12b
```

## 4. ComfyUI 桌面版

- 下载页：<https://www.comfy.org/download/>
- Windows 安装包：<https://download.comfy.org/windows/nsis/x64>

默认地址是 `http://<主机>:8188`。绿色便携包说明见 <https://docs.comfy.org/installation/comfyui_portable_windows>，发布页见 <https://github.com/Comfy-Org/ComfyUI/releases>。

FLUX.3 Klein 工作流需要 ComfyUI 0.41 或更高版本。

## 5. 工作流与 Comfy 模型

目录都相对于 ComfyUI 的 `models/`。桌面版和便携版都是 `ComfyUI\models\` 下面的同名子目录。

同一套权重会被多个工作流共用。下表按内置包的默认文件列出。官方图像包和越狱图像包共用文本编码器与 VAE，差别在 UNET，越狱包还可以再挂 LoRA。

| 工作流名称 | 类型 | 描述 | 需要的模型与下载链接 | 放到 Comfy 的目录 |
| --- | --- | --- | --- | --- |
| `qwen_image_21` | t2i | Qwen-Image 2.1 文生图，默认官方 INT8 | [UNET `qwen_image_2.1_int8_convrot.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/diffusion_models/qwen_image_2.1_int8_convrot.safetensors)<br>[TE `qwen3vl_8b_int8_convrot.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_int8_convrot.safetensors)<br>[VAE `qwen_image_2.1_vae_bf16.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors) | `diffusion_models/`<br>`text_encoders/`<br>`vae/` |
| `qwen_image_21_edit` | i2i | 整图编辑，1 张原图 | 与 `qwen_image_21` 相同三件套 | 同上 |
| `qwen_image_21_edit_multi` | i2i | 多参考编辑，2 到 4 张图 | 与 `qwen_image_21` 相同三件套 | 同上 |
| `qwen_image_21_inpaint` | i2i | 蒙版重绘 | 与 `qwen_image_21` 相同三件套 | 同上 |
| `qwen_image_21_uncensored` | t2i | 越狱文生图。默认 UC UNET，可开关 Uncensored LoRA | [UC UNET `qwen-image-2.1-UC-int8_convrot.safetensors`](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/blob/main/qwen-image-2.1-UC-int8_convrot.safetensors)<br>TE、VAE 与官方包相同<br>[LoRA `qwen-image-2.1-uncensored-lora.safetensors`](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/blob/main/qwen-image-2.1-uncensored-lora.safetensors) | UNET：`diffusion_models/`<br>TE：`text_encoders/`<br>VAE：`vae/`<br>LoRA：`loras/` |
| `qwen_image_21_edit_uncensored` | i2i | 越狱整图编辑 | 与 `qwen_image_21_uncensored` 相同 | 同上 |
| `qwen_image_21_edit_multi_uncensored` | i2i | 越狱多参考编辑 | 与 `qwen_image_21_uncensored` 相同 | 同上 |
| `qwen_image_21_inpaint_uncensored` | i2i | 越狱蒙版重绘 | 与 `qwen_image_21_uncensored` 相同 | 同上 |
| `flux3_klein` | t2i | FLUX.3 Image Klein 蒸馏文生图。需要 ComfyUI ≥ 0.41，仓库需先同意许可 | [仓库 `black-forest-labs/flux-3-image-klein-comfy`](https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy)<br>UNET `flux3-image-klein-int8-convrot.safetensors`<br>TE `qwen3vl_4b_int8_convrot.safetensors`<br>扩展器 `qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors`<br>VAE `flux2-vae.safetensors` | UNET：`diffusion_models/`<br>TE 与扩展器：`text_encoders/`<br>VAE：`vae/` |
| `flux3_klein_edit` | i2i | Klein 单图编辑 | 与 `flux3_klein` 相同四件套 | 同上 |
| `flux3_klein_edit_multi` | i2i | Klein 多参考编辑，2 到 4 张图 | 与 `flux3_klein` 相同四件套 | 同上 |
| `qwen_edit_2511_color_grade` | i2i | 按参考图调色。还需要 [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)，以及 `pip install color-matcher` | [UNET `qwen_image_edit_2511_fp8mixed.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/blob/main/split_files/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors)<br>[TE `qwen_2.5_vl_7b_fp8_scaled.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/tree/main/split_files)<br>[VAE `qwen_image_vae.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/tree/main/split_files)<br>[LoRA 仓库](https://huggingface.co/ovi054/QIE-2511-Color-Grade-Transfer-LoRA)。下载 `Color-Grade-Transfer-LoRA.safetensors` 后改名为 `QIE-2511-Color-Grade-Transfer-LoRA.safetensors` | UNET：`diffusion_models/`<br>TE：`text_encoders/`<br>VAE：`vae/`<br>LoRA：`loras/` |
| `upscale_basic` | upscale | 约 4 倍放大，不用生图模型 | [RealESRGAN_x4plus.pth](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth)。放到目录后改名为 `RealESRGAN_x4.pth`，与包内默认文件名一致 | `upscale_models/` |
| `t2i_basic` | t2i | 传统单文件 Checkpoint，适用于 SD1.5、SDXL 或 Flux 整包。包本身不指定文件 | 示例：[SDXL Base](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/sd_xl_base_1.0.safetensors) | `checkpoints/` |
| `minimax_h3_t2v` | t2v | MiniMax H3 文生视频，官方文本编码器，可选 Turbo | 共用主模型与两个 VAE，见本表下方「H3 共用文件」<br>[官方 TE `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`](https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/text_encoders)<br>可选 [Turbo LoRA](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora)：`minimax_h3_turbo_v4_step600_ema.safetensors`。打开 Turbo 前安装 [ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo) | 主模型：`diffusion_models/`<br>TE：`text_encoders/`<br>VAE：`vae/`<br>LoRA：`loras/` |
| `minimax_h3_i2v` | i2v | 图生视频，官方文本编码器，可选 Turbo | 与 `minimax_h3_t2v` 相同 | 同上 |
| `minimax_h3_avatar` | avatar | 数字人口播，官方文本编码器，可选 Turbo | 与 `minimax_h3_t2v` 相同 | 同上 |
| `minimax_h3_motion` | motion | 动作迁移，官方文本编码器，可选 Turbo。单段最多 124 帧 | 与 `minimax_h3_t2v` 相同 | 同上 |
| `minimax_h3_t2v_uncensored` | t2v | 文生视频，越狱 NVFP4 文本编码器，无提示词增强 | H3 共用主模型与 VAE<br>[越狱 TE `qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors`](https://huggingface.co/sakamakismile/Qwen3-VL-32B-Heretic-MiniMax-H3-NVFP4/blob/main/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors)<br>可选同一份 Turbo LoRA | 主模型：`diffusion_models/`<br>TE：`text_encoders/`<br>VAE：`vae/`<br>LoRA：`loras/` |
| `minimax_h3_i2v_uncensored` | i2v | 图生视频，越狱 NVFP4，无增强 | 与 `minimax_h3_t2v_uncensored` 相同 | 同上 |
| `minimax_h3_avatar_uncensored` | avatar | 数字人口播，越狱 NVFP4 | 与 `minimax_h3_t2v_uncensored` 相同 | 同上 |
| `minimax_h3_motion_uncensored` | motion | 动作迁移，越狱 NVFP4。单段最多 124 帧 | 与 `minimax_h3_t2v_uncensored` 相同 | 同上 |
| `minimax_h3_t2v_enhancer` | t2v | 文生视频加提示词增强。需要 [Guide 节点包](https://github.com/ethanfel/ComfyUI-MiniMax-H3-Guide) | H3 共用主模型与 VAE<br>[越狱 TE 与生成尾](https://huggingface.co/ethanfel/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot)：`qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors`、`qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors`<br>可选同一份 Turbo LoRA | 主模型：`diffusion_models/`<br>TE 与生成尾：`text_encoders/`<br>VAE：`vae/`<br>LoRA：`loras/` |
| `minimax_h3_i2v_enhancer` | i2v | 图生视频加提示词增强 | 与 `minimax_h3_t2v_enhancer` 相同 | 同上 |
| `analysis_image_qwenvl` | analysis | 图片素材分析。需要 ComfyUI-AILab 节点 | 节点默认模型 [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)。由节点加载，不放进 `diffusion_models/` | 按该节点自己的模型目录 |
| `analysis_video_qwenvl` | analysis | 视频素材分析。还需要 [Video Helper Suite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) 抽帧 | 与图片分析相同的 Qwen3-VL-8B-Instruct | 按该节点自己的模型目录 |

### H3 共用文件

官方、越狱和增强包都用这一套画面与声音权重。文件在 [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3)。

| 文件 | 目录 |
| --- | --- |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `diffusion_models/` |
| `minimax_h3_video_vae_fp16.safetensors` | `vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | `vae/` |

主模型不要换成 `minimax_h3_ref2va_*`。图像用的 `qwen3vl_8b*` 和视频用的 `qwen3vl_32b*` 不能混用。

## 6. Speech 模型

语音服务本地没有对应权重时，第一次合成或转写会从 Hugging Face 自动下载。文件写进容器内的 `/models`，也就是宿主机环境变量 `LIBER_SPEECH_MODELS_DIR` 指向的目录；没设置时用 Docker 卷 `speech-models`。`HF_HUB_OFFLINE=1` 时不会自动下载，需要事先把权重放进下表的位置。

`multilingual` 是 `multilingual_v2` 的别名。单语言包还会从 [ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox) 取 `ve.pt`、`conds.pt`、`grapheme_mtl_merged_expanded_v1.json`、`Cangjie5_TC.json`，再和语言包里的 `t3_*.safetensors`、`s3gen_v3.pt` 一起组装。

| 模型名 | 描述 | 下载地址 | 放入位置 |
| --- | --- | --- | --- |
| `faster-whisper-large-v3` | 默认识别模型。名字由 `LIBER_SPEECH_ASR_MODEL` 决定，默认 `large-v3` | <https://huggingface.co/Systran/faster-whisper-large-v3> | `/models/models--Systran--faster-whisper-large-v3/`，或平铺目录 `/models/faster-whisper-large-v3/` |
| `faster-whisper-large-v3-turbo` | 更快的 large-v3。请求里的别名是 `large-v3-turbo`。Systran 没有这个仓库，faster-whisper 使用 Mobius Labs 的转换 | <https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo> | `/models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/`，或平铺目录 `/models/faster-whisper-large-v3-turbo/` |
| `Qwen3-ASR-1.7B` | 识别模型。请求别名 `qwen3-asr-1.7b`。需要下一行的对齐模型才能返回时间戳。不支持译成英语 | <https://huggingface.co/Qwen/Qwen3-ASR-1.7B> | `/models/models--Qwen--Qwen3-ASR-1.7B/`，或平铺目录 `/models/Qwen3-ASR-1.7B/` |
| `Qwen3-ForcedAligner-0.6B` | Qwen3-ASR 的字词时间戳模型。可用 `LIBER_SPEECH_QWEN_ALIGNER_MODEL` 改路径 | <https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B> | `/models/models--Qwen--Qwen3-ForcedAligner-0.6B/`，或平铺目录 `/models/Qwen3-ForcedAligner-0.6B/` |
| `multilingual_v3` | Chatterbox-Multilingual V3，23 种语言。权重文件 `t3_mtl23ls_v3.safetensors` | <https://huggingface.co/ResembleAI/chatterbox> | `/models/models--ResembleAI--chatterbox/` |
| `multilingual_v2` | Chatterbox-Multilingual V2，23 种语言。权重文件 `t3_mtl23ls_v2.safetensors` | <https://huggingface.co/ResembleAI/chatterbox> | `/models/models--ResembleAI--chatterbox/` |
| `turbo` | Chatterbox-Turbo，只读英文。参考音频需长于 5 秒 | <https://huggingface.co/ResembleAI/chatterbox-turbo> | `/models/models--ResembleAI--chatterbox-turbo/` |
| `nano` | Chatterbox-Nano，只读英文。参考音频需长于 5 秒 | <https://huggingface.co/ResembleAI/chatterbox-nano> | `/models/models--ResembleAI--chatterbox-nano/` |
| `standard` | Chatterbox 英文模型 | <https://huggingface.co/ResembleAI/chatterbox> | `/models/models--ResembleAI--chatterbox/` |
| `zh-cmn` | 中文单语言包 | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-zh-cmn> | 缓存 `/models/models--ResembleAI--Chatterbox-Multilingual-zh-cmn/`，组装目录 `/models/liber-speech-packs/zh-cmn/` |
| `es-mx` | 拉美西班牙语 | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-mx-latam> | 缓存 `/models/models--ResembleAI--Chatterbox-Multilingual-es-mx-latam/`，组装目录 `/models/liber-speech-packs/es-mx/` |
| `pt-br` | 巴西葡萄牙语 | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br> | 缓存 `/models/models--ResembleAI--Chatterbox-Multilingual-pt-br/`，组装目录 `/models/liber-speech-packs/pt-br/` |
| `es-es` | 西班牙西班牙语 | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-es> | 缓存 `/models/models--ResembleAI--Chatterbox-Multilingual-es-es/`，组装目录 `/models/liber-speech-packs/es-es/` |
| `pt-pt` | 葡萄牙葡萄牙语 | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-pt> | 缓存 `/models/models--ResembleAI--Chatterbox-Multilingual-pt-pt/`，组装目录 `/models/liber-speech-packs/pt-pt/` |
| `hi` | 印地语 | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-hi> | 缓存 `/models/models--ResembleAI--Chatterbox-Multilingual-hi/`，组装目录 `/models/liber-speech-packs/hi/` |
