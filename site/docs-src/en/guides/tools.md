---
title: Tools
---

# Tools

The sidebar "Tools" group has two sections: **Media Concat** and **AI Enhance**. Concat runs locally and does not need ComfyUI or a provider; Image Enhance and Video Enhance still run through ComfyUI workflow packs.

## Image Concat

Sidebar "Tools → Image Concat". Uploaded images go into the asset library, or you can pick existing images directly.

1. Select at least 2 images; the order is the concat order, and you can move items up, move them down, or remove them on the right.
2. Choose horizontal, vertical, or grid. Grid lets you set the column count.
3. The gap defaults to 4px and white; the color can be changed.
4. Click "Start concat". The result goes directly into the asset library, and the job appears in Jobs.

Horizontal unifies height, vertical unifies width, and grid unifies height to the shortest image and packs tightly, centered. The grid is filled row by row.

## Video Concat

Sidebar "Tools → Video Concat". Pick existing videos or upload multiple clips, then join them in order into one video, at least 1 clip. The order can be adjusted up and down. The result goes directly into the asset library.

## Audio Concat

Sidebar "Tools → Audio Concat". Pick existing audio or upload multiple clips, then join them in order into one audio file, at least 1 clip. The result goes directly into the asset library.

**Note:** Outputs from the concat pages are formal assets; you do not need to click "Save to Assets" again. Concat nodes inside a canvas are still treated as canvas intermediate results and must be saved from the node preview. Video and audio concat require local ffmpeg; `astra doctor` checks whether ffmpeg is present.

## Image Enhance

Sidebar "Tools → Image Enhance". Upload one source image (you can also choose from the asset library), select an image service and an `upscale` workflow pack (default `upscale_basic`):

- `upscale_basic`: RealESRGAN faithful upscaling, about 4×, only adding detail and not repainting content. Weights go in ComfyUI's `upscale_models/`. The page has no prompt box; choose the upscale model in advanced parameters.
- `seedvr2_3b_image_restore`: SeedVR2 3B generative restoration. Suitable for low-resolution, noisy, compressed, and soft AI images; it repaints detail, so it is not suitable for product images or text images that require pixel-level fidelity. Models and VAE go in ComfyUI's `SEEDVR2/`, defaulting to `seedvr2_ema_3b_fp16.safetensors` + `ema_vae_fp16.safetensors`.

SeedVR2 image parameters:

- **Target short edge**: default 1080; output keeps the source aspect ratio.
- **Color correction**: default `lab`, closest to the source; `none` disables it.
- **Attention mode**: default `sdpa`; switch only if Flash Attention 2 or SageAttention 2 is installed.
- A single image is processed as 1 frame with batch=1 and does not use video temporal information.

Both packs process the whole image and do not apply local masks; for inpainting, use [Image → Image-to-Image and Edit → Inpaint](/guides/image#image-to-image-and-edit).

## Video Enhance

Sidebar "Tools → Video Enhance". Upload a video (you can also choose from the asset library), select an enabled video service (must be ComfyUI), then select a `v2v` workflow pack. The built-in pack is `seedvr2_3b_video_restore`:

- Keeps the source video's fps and audio, performing generative restoration and upscaling.
- **Target short edge**: default 1080; keeps the original aspect ratio.
- **Batch frames**: must be 4n+1 (1, 5, 9, 13…), default 5. Values greater than 1 provide temporal benefit; larger is more stable but uses more VRAM.
- **Temporal overlap**: number of overlapping frames between adjacent batches, default 0; for long videos set 1–4 for smoother transitions.
- **Color correction**: default `lab`.
- **Attention mode**: default `sdpa`.

Models go in ComfyUI's `SEEDVR2/`; install [ComfyUI-SeedVR2_VideoUpscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler); video reading and writing also need VideoHelperSuite. Test with a 2–5 second clip first, then process the full video; long videos take noticeably longer, and the job can be canceled or retried from Jobs.

**Note:** SeedVR2 is generative restoration and may rewrite details; it is not suitable for material that must remain pixel-identical.

---

Related: [Image → Image-to-Image and Edit](/guides/image#image-to-image-and-edit); [Canvas → Nodes](/guides/canvas#nodes) (the Concat node inside a canvas and the concat pages here are not the same kind of output).
