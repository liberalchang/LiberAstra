---
title: Image
---

# Image

The Image group has four pages: generate, edit, upscale, and depth. Every ComfyUI task starts with a provider and a workflow pack; the pack decides which models and parameters appear.

## Text to image

Open Image -> Generate, choose an image provider and a `t2i` workflow pack.

- Prompt optimization can rewrite the input with your configured LLM.
- Aspect ratio, steps, seed, batch size, and workflow parameters are kept with the job.
- A seed of `-1` is random; batches increment from that seed.
- History stays on the right; click a result to reuse or preview.

Built-in examples include `qwen_image_21`, `flux3_klein`, and `t2i_basic`. Pair official packs with official weights; do not mix UNET, text encoder, VAE, or quantization from different families.

## Edit and inpaint

Open Image -> Edit. One source image is required; the prompt says what to change and what to preserve.

- Whole-image edit: one source image.
- Multi-reference edit: 2-4 images; the first is the main image and sets the canvas.
- Inpaint: source image plus a mask; white is repainted, black is kept.
- Reference color grading: first image is the original, second supplies color; leave the prompt empty.
- Depth controls and outfit swap are available as separate packs; follow the pack's slot order.

The page shows only packs matching the capability, and disables generation when the number of uploads exceeds the pack's image slots.

## Upscale

Open Image -> Upscale, choose `upscale_basic`, and upload an image. RealESRGAN upscales about 4x. Weights go in ComfyUI's `upscale_models/`.

## Depth map

Open Image -> Depth. This page calls Liber Depth rather than a ComfyUI workflow.

1. Enable the local depth plugin under Resources -> Plugins, or enable a Liber Depth provider (default `http://127.0.0.1:5556`).
2. Pick the depth service, model, and hardware.
3. Add one or more images; duplicate files are ignored.
4. Start conversion. Outputs are named `<original>_depth.png`, and history is kept.

Brighter pixels are closer to the camera. Depth maps can be reused in the Union workspace packs.

## Practical notes

- Use `.safetensors`; avoid mixing GGUF with other formats.
- Qwen-Image text encoders should be `qwen3vl_8b*`; video H3 encoders (`32b`, `h3`, `minimax`) are a different family.
- If a pack reports missing weights, choose an installed pack or place the files in the ComfyUI model directory first.
