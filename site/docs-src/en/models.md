---
title: Model resources
---

# Model resources

LiberAstra does not run models itself. This page collects installers, Ollama and ComfyUI clients, and weight download links for the built-in workflows and speech services. Model directories are relative to the model root of each service; put files where the table says and keep filenames unchanged unless noted.

## All-in-one bundle

The cloud-drive bundle contains common runtimes and some models. Download only what you need:

- Link: <https://pan.baidu.com/s/1F8ZeMSUbPOfzgEcYUZzqHQ?pwd=g2v7>
- Code: `g2v7`

## LiberAstra and the Windows installer

- Project: <https://github.com/liberalchang/LiberAstra>
- Windows installer: <https://github.com/liberalchang/LiberAstra/releases/latest/download/LiberAstra-Setup.exe>
- Releases: <https://github.com/liberalchang/LiberAstra/releases>

The installer bundles a Python runtime and the built UI, so the target machine does not need Python or Node. Open `http://127.0.0.1:8000` after installation. Ollama, ComfyUI, and the speech plugin are not included.

The speech plugin has a separate [LiberSpeech-Setup.exe](https://github.com/liberalchang/LiberAstra/releases/latest/download/LiberSpeech-Setup.exe).

## Ollama

- Download page: <https://ollama.com/download>
- Windows installer: <https://ollama.com/download/OllamaSetup.exe>

The default address after installation is `http://<host>:11434`. Add a provider of type Ollama in LiberAstra. The two models below are what the current docs use for scripts and prompt refinement; pull them with `ollama pull`.

| Model | Description | Download |
| --- | --- | --- |
| `orcarouter/Qwen3.8-27B-Uncensored:q4_K_M` | 27B quantized weights for scripts and prompts | <https://ollama.com/orcarouter/Qwen3.8-27B-Uncensored> |
| `huihui_ai/gemma-4-abliterated:12b` | 12B weights for scripts and prompts | <https://ollama.com/huihui_ai/gemma-4-abliterated> |

```bash
ollama pull orcarouter/Qwen3.8-27B-Uncensored:q4_K_M
ollama pull huihui_ai/gemma-4-abliterated:12b
```

## ComfyUI desktop

- Download page: <https://www.comfy.org/download/>
- Windows installer: <https://download.comfy.org/windows/nsis/x64>

The default address is `http://<host>:8188`. See <https://docs.comfy.org/installation/comfyui_portable_windows> for the portable build and <https://github.com/Comfy-Org/ComfyUI/releases> for releases.

The FLUX.3 Klein workflows require ComfyUI 0.41 or newer.

## Workflows and ComfyUI models

All paths below are relative to ComfyUI's `models/` directory. Desktop and portable builds use the same subdirectories under `ComfyUI\models\`.

Several workflows share the same weights. The table lists the default files used by the built-in packs. The official and uncensored image packs share the text encoder and VAE; the difference is the UNET, and the uncensored pack can also load a LoRA.

| Workflow | Type | Description | Models and download links | ComfyUI directory |
| --- | --- | --- | --- | --- |
| `qwen_image_21` | t2i | Qwen-Image 2.1 text-to-image, official INT8 by default | [UNET](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/diffusion_models/qwen_image_2.1_int8_convrot.safetensors) `qwen_image_2.1_int8_convrot.safetensors` [TE](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/text_encoders/qwen3vl_8b_int8_convrot.safetensors) `qwen3vl_8b_int8_convrot.safetensors` [VAE](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/blob/main/vae/qwen_image_2.1_vae_bf16.safetensors) `qwen_image_2.1_vae_bf16.safetensors` | `diffusion_models/` `text_encoders/` `vae/` |
| `qwen_image_21_edit` | i2i | Whole-image edit from one source image | Same three files as `qwen_image_21` | Same as above |
| `qwen_image_21_edit_multi` | i2i | Multi-reference edit, 2 to 4 images | Same three files as `qwen_image_21` | Same as above |
| `qwen_image_21_inpaint` | i2i | Masked repaint | Same three files as `qwen_image_21` | Same as above |
| `qwen_image_21_uncensored` | t2i | Uncensored text-to-image. UC UNET by default; the Uncensored LoRA can be toggled | [UC UNET](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/blob/main/qwen-image-2.1-UC-int8_convrot.safetensors) `qwen-image-2.1-UC-int8_convrot.safetensors` TE and VAE are the same as the official pack [LoRA](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/blob/main/qwen-image-2.1-uncensored-lora.safetensors) `qwen-image-2.1-uncensored-lora.safetensors` | UNET: `diffusion_models/` TE: `text_encoders/` VAE: `vae/` LoRA: `loras/` |
| `qwen_image_21_edit_uncensored` | i2i | Uncensored whole-image edit | Same as `qwen_image_21_uncensored` | Same as above |
| `qwen_image_21_edit_multi_uncensored` | i2i | Uncensored multi-reference edit | Same as `qwen_image_21_uncensored` | Same as above |
| `qwen_image_21_inpaint_uncensored` | i2i | Uncensored masked repaint | Same as `qwen_image_21_uncensored` | Same as above |
| `flux3_klein` | t2i | FLUX.3 Image Klein distilled text-to-image. Requires ComfyUI ≥ 0.41 and accepting the repository license | [Repository](https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy) `black-forest-labs/flux-3-image-klein-comfy` UNET `flux3-image-klein-int8-convrot.safetensors` TE `qwen3vl_4b_int8_convrot.safetensors` upsampler `qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors` VAE `flux2-vae.safetensors` | UNET: `diffusion_models/` TE and upsampler: `text_encoders/` VAE: `vae/` |
| `flux3_klein_edit` | i2i | Klein single-image edit | Same four files as `flux3_klein` | Same as above |
| `flux3_klein_edit_multi` | i2i | Klein multi-reference edit, 2 to 4 images | Same four files as `flux3_klein` | Same as above |
| `qwen_image_21_union_depth` | i2i | Upload only a depth map and generate a person in that pose from the prompt. Requires the [T8 Fun ControlNet Union](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8) node and ComfyUI ≥ 0.37 | The default main model is the uncensored [UC UNET](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/blob/main/qwen-image-2.1-UC-int8_convrot.safetensors) `qwen-image-2.1-UC-int8_convrot.safetensors`. TE and VAE are the same as `qwen_image_21`. Additional [Union](https://huggingface.co/t8star/Qwen-Image-2.1-Fun-Controlnet-Union-Comfy) `Qwen-Image-2.1-Fun-Controlnet-Union-ComfyUI.safetensors` | UNET: `diffusion_models/` TE: `text_encoders/` VAE: `vae/` Union: `controlnet/` |
| `qwen_image_21_union_reference` | i2i | First image is the person, second is a depth map for the new pose. Node and weight requirements are the same as the row above | Same as `qwen_image_21_union_depth` | Same as above |
| `qwen_image_21_outfit_swap` | i2i | Outfit swap. First image is the person, second is the garment. ComfyUI ≥ 0.38. The main model is the official INT8; this LoRA has not been tested on the uncensored UNET | Same three files as `qwen_image_21`. Additional [Outfit Swap LoRA](https://huggingface.co/ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA) `qwen-image-2.1-outfit-swap.safetensors` | UNET: `diffusion_models/` TE: `text_encoders/` VAE: `vae/` LoRA: `loras/` |
| `qwen_edit_2511_color_grade` | i2i | Color-match to a reference image. Also requires [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) and `pip install color-matcher` | [UNET](https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/blob/main/split_files/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors) `qwen_image_edit_2511_fp8mixed.safetensors` [TE](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/tree/main/split_files) `qwen_2.5_vl_7b_fp8_scaled.safetensors` [VAE](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/tree/main/split_files) `qwen_image_vae.safetensors` [LoRA repository](https://huggingface.co/ovi054/QIE-2511-Color-Grade-Transfer-LoRA). Download `Color-Grade-Transfer-LoRA.safetensors` and rename it to `QIE-2511-Color-Grade-Transfer-LoRA.safetensors` | UNET: `diffusion_models/` TE: `text_encoders/` VAE: `vae/` LoRA: `loras/` |
| `upscale_basic` | upscale | About 4× upscale without a generative model | [RealESRGAN_x4plus.pth](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth). Rename it to `RealESRGAN_x4.pth` after downloading to match the pack's default filename | `upscale_models/` |
| `t2i_basic` | t2i | Traditional single-file checkpoint for SD1.5, SDXL, or a full Flux package. The pack does not specify a file | Example: [SDXL Base](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/sd_xl_base_1.0.safetensors) | `checkpoints/` |
| `minimax_h3_t2v` | t2v | MiniMax H3 text-to-video with the official text encoder and optional Turbo | Shares the main models and two VAEs; see "H3 shared files" below; [Official TE](https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/text_encoders) `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` Optional [Turbo LoRA](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora): `minimax_h3_turbo_v4_step600_ema.safetensors`. Install [ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo) before enabling Turbo | Main model: `diffusion_models/` TE: `text_encoders/` VAE: `vae/` LoRA: `loras/` |
| `minimax_h3_i2v` | i2v | Image-to-video with the official text encoder and optional Turbo | Same as `minimax_h3_t2v` | Same as above |
| `minimax_h3_orbit` | i2v | 360° orbit. With one image, the first and last frames are the same; adding an end frame allows an outfit change during the orbit. 768×768, 73 frames, 28 steps, LoRA strength 1 | Shares the H3 main models, official TE, and audio VAE. Use the [int8](https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/vae) video VAE `minimax_h3_video_vae_int8_convrot.safetensors`; if decoding comes out black, switch back to fp16. Additional [360° Orbit LoRA](https://huggingface.co/pablodawson/MiniMax-H3-360-Orbit-LoRA) `minimax_h3_flf2v_lora_v1.safetensors` | Main model: `diffusion_models/` TE: `text_encoders/` VAE: `vae/` LoRA: `loras/` |
| `minimax_h3_avatar` | avatar | Talking-head digital human with the official text encoder and optional Turbo | Same as `minimax_h3_t2v` | Same as above |
| `minimax_h3_motion` | motion | Motion transfer with the official text encoder and optional Turbo. Up to 124 frames per segment | Same as `minimax_h3_t2v` | Same as above |
| `minimax_h3_t2v_uncensored` | t2v | Text-to-video with the uncensored NVFP4 text encoder and no prompt enhancement | Shares the H3 main models and VAEs; [Uncensored TE](https://huggingface.co/sakamakismile/Qwen3-VL-32B-Heretic-MiniMax-H3-NVFP4/blob/main/qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors) `qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` Optional: the same Turbo LoRA | Main model: `diffusion_models/` TE: `text_encoders/` VAE: `vae/` LoRA: `loras/` |
| `minimax_h3_i2v_uncensored` | i2v | Image-to-video with the uncensored NVFP4 encoder and no enhancement | Same as `minimax_h3_t2v_uncensored` | Same as above |
| `minimax_h3_avatar_uncensored` | avatar | Talking-head digital human with the uncensored NVFP4 encoder | Same as `minimax_h3_t2v_uncensored` | Same as above |
| `minimax_h3_motion_uncensored` | motion | Motion transfer with the uncensored NVFP4 encoder. Up to 124 frames per segment | Same as `minimax_h3_t2v_uncensored` | Same as above |
| `minimax_h3_t2v_enhancer` | t2v | Text-to-video with prompt enhancement. Requires the [Guide node pack](https://github.com/ethanfel/ComfyUI-MiniMax-H3-Guide) | Shares the H3 main models and VAEs; [Uncensored TE and generation tail](https://huggingface.co/ethanfel/Qwen3-VL-32B-Ultra-Heretic-MiniMax-H3-ComfyUI-INT8-ConvRot): `qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors`, `qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors` Optional: the same Turbo LoRA | Main model: `diffusion_models/` TE and generation tail: `text_encoders/` VAE: `vae/` LoRA: `loras/` |
| `minimax_h3_i2v_enhancer` | i2v | Image-to-video with prompt enhancement | Same as `minimax_h3_t2v_enhancer` | Same as above |
| `analysis_image_qwenvl` | analysis | Image asset analysis. Requires the ComfyUI-AILab node | The node's default model is [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct). It is loaded by the node and does not go into `diffusion_models/` | The node's own model directory |
| `analysis_video_qwenvl` | analysis | Video asset analysis. Also requires [Video Helper Suite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) for frame extraction | Same Qwen3-VL-8B-Instruct as image analysis | The node's own model directory |

### H3 shared files

The official, uncensored, and enhancer packs all use this set of video and audio weights. Files are in [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3).

| File | Directory |
| --- | --- |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `diffusion_models/`. First frame / first-last frame, text-to-video, digital human |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `diffusion_models/`. Reference image / reference video, motion transfer, long video |
| `minimax_h3_video_vae_fp16.safetensors` | `vae/` |
| `minimax_h3_video_vae_int8_convrot.safetensors` | `vae/`. Used by default only by `minimax_h3_orbit`; other H3 packs still use the fp16 file above |
| `minimax_h3_audio_vae_fp32.safetensors` | `vae/` |

FL2VA and Ref2VA are two different weight sets; do not mix them in one workflow. The image-side `qwen3vl_8b*` and video-side `qwen3vl_32b*` cannot be mixed.

On RTX 3090 / Ampere, prefer Comfy-Org's `minimax_h3_ref2va_pruned_int8_convrot.safetensors`. Community NVFP4 weights target Blackwell; on non-Blackwell cards NVFP4 is emulated, so speed and compatibility are not guaranteed.

## Speech models

If the speech service does not have the weights locally, the first synthesis or transcription downloads them from Hugging Face. Files go into `/models` inside the container, which is the host directory pointed to by `LIBER_SPEECH_MODELS_DIR`; without it, the Docker volume `speech-models` is used. With `HF_HUB_OFFLINE=1` there is no automatic download, so place the weights in the locations below beforehand.

`multilingual` is an alias for `multilingual_v2`. Single-language packs also take `ve.pt`, `conds.pt`, `grapheme_mtl_merged_expanded_v1.json`, and `Cangjie5_TC.json` from [ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox), then assemble them with the pack's `t3_*.safetensors` and `s3gen_v3.pt`.

| Model | Description | Download | Location |
| --- | --- | --- | --- |
| `faster-whisper-large-v3` | Default ASR model. The name comes from `LIBER_SPEECH_ASR_MODEL`, default `large-v3` | <https://huggingface.co/Systran/faster-whisper-large-v3> | `/models/models--Systran--faster-whisper-large-v3/` or flat directory `/models/faster-whisper-large-v3/` |
| `faster-whisper-large-v3-turbo` | Faster large-v3. The request alias is `large-v3-turbo`. Systran does not host this repository; faster-whisper uses the Mobius Labs conversion | <https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo> | `/models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/` or flat directory `/models/faster-whisper-large-v3-turbo/` |
| `Qwen3-ASR-1.7B` | ASR model. Request alias `qwen3-asr-1.7b`. The aligner below is required for timestamps. It cannot translate into English | <https://huggingface.co/Qwen/Qwen3-ASR-1.7B> | `/models/models--Qwen--Qwen3-ASR-1.7B/` or flat directory `/models/Qwen3-ASR-1.7B/` |
| `Qwen3-ForcedAligner-0.6B` | Word-level timestamp model for Qwen3-ASR. Override the path with `LIBER_SPEECH_QWEN_ALIGNER_MODEL` | <https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B> | `/models/models--Qwen--Qwen3-ForcedAligner-0.6B/` or flat directory `/models/Qwen3-ForcedAligner-0.6B/` |
| `multilingual_v3` | Chatterbox-Multilingual V3, 23 languages. Weight file `t3_mtl23ls_v3.safetensors` | <https://huggingface.co/ResembleAI/chatterbox> | `/models/models--ResembleAI--chatterbox/` |
| `multilingual_v2` | Chatterbox-Multilingual V2, 23 languages. Weight file `t3_mtl23ls_v2.safetensors` | <https://huggingface.co/ResembleAI/chatterbox> | `/models/models--ResembleAI--chatterbox/` |
| `turbo` | Chatterbox-Turbo, English only. Reference audio must be longer than 5 seconds | <https://huggingface.co/ResembleAI/chatterbox-turbo> | `/models/models--ResembleAI--chatterbox-turbo/` |
| `nano` | Chatterbox-Nano, English only. Reference audio must be longer than 5 seconds | <https://huggingface.co/ResembleAI/chatterbox-nano> | `/models/models--ResembleAI--chatterbox-nano/` |
| `standard` | Chatterbox English model | <https://huggingface.co/ResembleAI/chatterbox> | `/models/models--ResembleAI--chatterbox/` |
| `zh-cmn` | Mandarin Chinese pack | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-zh-cmn> | Cache `/models/models--ResembleAI--Chatterbox-Multilingual-zh-cmn/`, assembled directory `/models/liber-speech-packs/zh-cmn/` |
| `es-mx` | Latin American Spanish | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-mx-latam> | Cache `/models/models--ResembleAI--Chatterbox-Multilingual-es-mx-latam/`, assembled directory `/models/liber-speech-packs/es-mx/` |
| `pt-br` | Brazilian Portuguese | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br> | Cache `/models/models--ResembleAI--Chatterbox-Multilingual-pt-br/`, assembled directory `/models/liber-speech-packs/pt-br/` |
| `es-es` | European Spanish | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-es> | Cache `/models/models--ResembleAI--Chatterbox-Multilingual-es-es/`, assembled directory `/models/liber-speech-packs/es-es/` |
| `pt-pt` | European Portuguese | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-pt> | Cache `/models/models--ResembleAI--Chatterbox-Multilingual-pt-pt/`, assembled directory `/models/liber-speech-packs/pt-pt/` |
| `hi` | Hindi | <https://huggingface.co/ResembleAI/Chatterbox-Multilingual-hi> | Cache `/models/models--ResembleAI--Chatterbox-Multilingual-hi/`, assembled directory `/models/liber-speech-packs/hi/` |

## VC voice conversion

Voice conversion needs the following weights in addition to TTS / ASR. `chatterbox` uses Chatterbox VC by default; `seed-vc` uses Seed-VC V1 (`seed-uvit-whisper-small-wavenet`). "Separate background audio" also requires Demucs. Example local bundle directory: `W-文字语音转换/VC(语音换音)/`.

| Model | Description | Download | Location |
| --- | --- | --- | --- |
| `s3gen.safetensors` | Chatterbox VC vocoder. Shares [ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox) with TTS; download only this file if it is the only one missing | <https://huggingface.co/ResembleAI/chatterbox/blob/main/s3gen.safetensors> | `/models/models--ResembleAI--chatterbox/` (same snapshot directory as the existing `s3gen.pt`, `ve.pt`, etc.) |
| `seed-vc` | Seed-VC V1 main weights and config: `DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth`, `config_dit_mel_seed_uvit_whisper_small_wavenet.yml` | <https://huggingface.co/Plachta/Seed-VC> | `/models/Seed-VC/` |
| `whisper-small` | Seed-VC content encoder from [openai/whisper-small](https://huggingface.co/openai/whisper-small). Inference needs at least `model.safetensors` plus the config and tokenizer files | <https://huggingface.co/openai/whisper-small> | `/models/whisper-small/` |
| `campplus` | Seed-VC speaker encoder. File `campplus_cn_common.bin` | <https://huggingface.co/funasr/campplus/blob/main/campplus_cn_common.bin> | `/models/campplus/` |
| `bigvgan_v2_22khz_80band_256x` | Seed-VC vocoder. Needs at least `bigvgan_generator.pt` and `config.json` | <https://huggingface.co/nvidia/bigvgan_v2_22khz_80band_256x> | `/models/bigvgan_v2_22khz_80band_256x/` |
| `htdemucs` | Demucs vocal/accompaniment separation. File `htdemucs-955717e8-8726e21a.th` | <https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th> | `/models/demucs/` |

Voice-conversion environment variables (the compose file already sets defaults): `LIBER_SPEECH_VC_MODEL=chatterbox`, `LIBER_SPEECH_SEEDVC_DIR=/models/Seed-VC`, `LIBER_SPEECH_WHISPER_SMALL_DIR=/models/whisper-small`, `LIBER_SPEECH_CAMPPLUS_DIR=/models/campplus`, `LIBER_SPEECH_BIGVGAN_DIR=/models/bigvgan_v2_22khz_80band_256x`, `LIBER_SPEECH_DEMUCS_DIR=/models/demucs`, `TORCH_HOME=/models`.
