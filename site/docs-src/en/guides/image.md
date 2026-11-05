---
title: Image
---

# Image

From text-to-image and editing to depth maps; choose a service and workflow pack first, then write the prompt. Image Enhance lives under Tools → Image Enhance in the sidebar.

The repository primarily ships the **Qwen-Image 2.1** series (not the same models as MiniMax H3 for video). There are also three distilled **FLUX.3 Image Klein** packs and a traditional SD checkpoint pack as a fallback. When changing file names in the dropdowns, choose by "set" as described below; do not mix series, quantization, or GGUF.

## Image Generation Series at a Glance

| Series | Capability | Workflow pack | How to choose models |
|------|------|----------|------------|
| **Official** | `t2i` | `qwen_image_21` | UNET + TE + VAE; official INT8 by default |
| **Uncensored** | `t2i` | `qwen_image_21_uncensored` | UC UNET by default; also has an **Uncensored LoRA** switch (same control as video Turbo) |
| **Official** | `i2i` full image | `qwen_image_21_edit` | Three-piece set + 1 original image |
| **Uncensored** | `i2i` full image | `qwen_image_21_edit_uncensored` | UC + LoRA switch |
| **Official** | `i2i` multi-reference | `qwen_image_21_edit_multi` | Three-piece set; 2–4 reference images |
| **Uncensored** | `i2i` multi-reference | `qwen_image_21_edit_multi_uncensored` | UC + LoRA switch |
| **Official** | `i2i` inpaint | `qwen_image_21_inpaint` | Three-piece set; original image + mask |
| **Uncensored** | `i2i` inpaint | `qwen_image_21_inpaint_uncensored` | UC + LoRA switch |
| **FLUX.3 Klein** | `t2i` | `flux3_klein` | Distilled INT8 + Qwen3-VL-4B + w4a8 upsampler + flux2-vae |
| **FLUX.3 Klein** | `i2i` single image | `flux3_klein_edit` | Same four-piece set; 1 original image |
| **FLUX.3 Klein** | `i2i` multi-reference | `flux3_klein_edit_multi` | Same as above; 2–4 reference images |
| **Traditional SD** | `t2i` | `t2i_basic` | Only one package from `checkpoints/`; no UNET/TE/VAE |
| **Color grading reference** | `i2i` | `qwen_edit_2511_color_grade` | Edit-2511 + color grading LoRA; original + reference. See below |
| **PoseStudio pose transfer** | `i2i` | `qwen_image_21_posestudio` | Qwen 2.1 + PoseStudio V1.1 LoRA; person photo + line art/depth, identity preserved |
| **PoseStudio pose generation** | `i2i` | `qwen_image_21_posestudio_gen` | Same as above; upload only line art/depth, identity comes from the prompt |
| **Union depth-to-image** | `i2i` | `qwen_image_21_union_depth` | 2.1 three-piece set + Fun ControlNet Union; upload only a depth map |
| **Union reference pose change** | `i2i` | `qwen_image_21_union_reference` | Same as above; image 1 is the person photo, image 2 is the depth map |
| **Outfit swap** | `i2i` | `qwen_image_21_outfit_swap` | Official three-piece set + Outfit Swap LoRA; image 1 is the person, image 2 is the garment |
| **Image Enhance (Tools)** | `upscale` | `upscale_basic` / `seedvr2_3b_image_restore` | RealESRGAN faithful upscaling, or SeedVR2 generative restoration; see [Tools → Image Enhance](/en/guides/tools#image-enhance) |

The four official packs and four uncensored packs have **matching graph structures**; the difference is the default UNET and whether `accel` (LoRA) is declared. Do not change only the UNET in an official pack and expect a LoRA switch to appear—choose a `*_uncensored` pack if you want LoRA.

## FLUX.3 Image Klein

All three packs are distilled and already include a prompt upsampler in the graph. ComfyUI requires **≥ 0.41**. Sampling is fixed at CFG 1, euler, simple, 16 steps. On 24GB use the set below; do not switch to bf16 or NVFP4:

| Slot | Directory | File |
|------|------|------|
| UNET | `diffusion_models/` | `flux3-image-klein-int8-convrot.safetensors` |
| Text encoder | `text_encoders/` | `qwen3vl_4b_int8_convrot.safetensors` |
| Upsampler | `text_encoders/` | `qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors` |
| VAE | `vae/` | `flux2-vae.safetensors` |

Keep CLIPLoader type `flux3`. This set has no public uncensored base image model; do not swap in Qwen's UC UNET or LoRA.

### Text-to-Image: `flux3_klein`

Sidebar "Image → Text-to-Image". Choose ComfyUI as the image service and `flux3_klein` as the workflow pack.

1. Keep the four models from the table above. The upsampler expands short prompts into long English descriptions; do not replace it with Qwen-Image's 8B or the video 32B.
2. Write the visual content in the prompt, e.g. "a ceramic cup by the window, soft side light".
3. Width and height default to 1024; the long edge must not exceed 1536. The page's steps override the pack default; set the distilled pack back to **16**. CFG is fixed at 1 and is not shown on the page.
4. On 24GB keep the image count at 1. The upsampler itself uses VRAM.

### Single-Image Edit: `flux3_klein_edit`

Sidebar "Image → Image-to-Image & Edit". Upload **only 1** original image.

1. Prompt what to change and what to keep, e.g. "change the background to a beach; keep the face and pose unchanged".
2. There are no width/height controls. Output size follows the original; the reference is resized to about 1MP before encoding.
3. 16 steps, same weights as text-to-image.
4. This pack has no mask. For brush inpainting, use `qwen_image_21_inpaint`.

### Multi-Image Edit: `flux3_klein_edit_multi`

On the same page, switch the workflow pack to `flux3_klein_edit_multi`.

1. At least 2, at most 4. The first image is the main image and determines the output size (resized to about 2MP first, then encoded at about 1MP). Images 3 and 4 are optional; unused slots are disconnected rather than filled with a placeholder.
2. In the prompt, refer to "the first image" and "the second image" in upload order, e.g. "the person in the first image stands in front of the autumn forest lookout in the second image". Do not use the Qwen multi-image pack syntax `` `<image1>` `` / `` `<image2>` `` here.
3. 16 steps, CFG fixed at 1.

## Color Grading Reference

Pack name `qwen_edit_2511_color_grade`, capability `i2i`. Sidebar "Image → Image-to-Image & Edit".

It only changes color: Qwen-Image-Edit-2511 plus the Color Grade Transfer LoRA generates a color-graded result at about 1MP, then KJNodes' ColorMatch transfers the color back onto the full-size original without repainting pixels.

The Comfy environment requires:

- Node pack [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) (provides `ColorMatch`)
- Run `pip install color-matcher` in Comfy's Python environment

| Slot | Directory | File |
|------|------|------|
| UNET | `diffusion_models/` | `qwen_image_edit_2511_fp8mixed.safetensors` |
| Text encoder | `text_encoders/` | `qwen_2.5_vl_7b_fp8_scaled.safetensors` |
| VAE | `vae/` | `qwen_image_vae.safetensors` |
| Color grading LoRA | `loras/` | `QIE-2511-Color-Grade-Transfer-LoRA.safetensors` |

On the page:

1. Select workflow pack `qwen_edit_2511_color_grade`.
2. Image 1 is the photographic original whose content and resolution should be preserved; image 2 is the reference that only lends its color. Do not reverse the order.
3. **Leave the prompt empty**. Empty uses the pack's trigger sentence `Transfer ONLY the color grading from Image 2 onto Image 1`. Writing a normal editing instruction (e.g. change background, change clothes) leaves this color-grading path.
4. Steps **20**, CFG **4**. This is the official template without Lightning. LoRA strength defaults to 1.
5. The color transfer algorithm defaults to `hm-mvgd-hm`; `mkl`, `hm`, `reinhard`, `mvgd`, and `hm-mkl-hm` are also accepted. Strength 1 fully applies the reference color, 0.7 is lighter, and 0 equals the original.

These four weights are not the same set as Qwen-Image 2.1. If the dropdown shows `qwen_image_2.1*`, `qwen3vl_8b*`, or `qwen_image_2.1_vae*`, do not select them. Keep CLIPLoader type `qwen_image`. On 24GB use fp8mixed; with enough VRAM you can switch to the same-generation bf16, but keep the text encoder `qwen_2.5_vl_7b` and the VAE `qwen_image_vae`.

## Qwen-Image 2.1: Choose Models as a Set (Do Not Mix)

After selecting a pack, the parameter area has UNET / TE / VAE dropdowns. The UI allows changing them individually, but **you must select them as a complete set**.

### Set Table (Recommended)

| Set | Main model UNET (`diffusion_models/`) | Text encoder TE (`text_encoders/`) | VAE (`vae/`) | LoRA (`loras/`, uncensored packs only) |
|------|-------------------------------------|-----------------------------------|---------------|---------------------------|
| **Official INT8** | `qwen_image_2.1_int8_convrot.safetensors` | `qwen3vl_8b_int8_convrot.safetensors` | `qwen_image_2.1_vae_bf16.safetensors` | None (official packs have no accel) |
| **Uncensored UC INT8** | `qwen-image-2.1-UC-int8_convrot.safetensors` | **Same as above** `qwen3vl_8b_*` | **Same as above** | Recommended `qwen-image-2.1-uncensored-lora.safetensors` (can be turned off) |
| **Official higher precision** | `qwen_image_2.1_bf16.safetensors` and similar | Same family `qwen3vl_8b_*` | Same VAE as above | None |

### How to Use Uncensored LoRA

1. Choose workflow pack **`qwen_image_21_uncensored`** (or the corresponding `*_edit*_uncensored` / `*_inpaint_uncensored`); do not choose the official pack without the `_uncensored` suffix.
2. The page shows the **same** control as video Turbo: **Uncensored LoRA** on/off → when on, choose the LoRA file and strength (on by default, recommended `qwen-image-2.1-uncensored-lora.safetensors`, strength 1.0).
3. **Off**: the graph removes `LoraLoaderModelOnly` and uses only the UC UNET (which may still be looser than official).
4. **On**: the LoRA is attached after Cache and before sampling; too high a strength can overfit, so try 0.7–1.0.
5. Put the file in Comfy's `models/loras/`; the dropdown filters by file names containing `uncensored`. Put the UC UNET in `diffusion_models/`.
6. When choosing an uncensored pack for Quick Create → Generate Illustration, the LoRA switch also appears.

Even if you manually change the UNET to UC in an official pack, it will **not** automatically load that LoRA.

### Pairing Rules (Read This)

1. **TE** must be `qwen3vl_8b*`; **do not** choose the video H3 `qwen3vl_32b*` / `*_minimax_h3_*`.
2. **Main model** must be `qwen_image_2.1*` / `qwen-image-2.1*`; **do not** choose `minimax_h3_*` or `wan_*`.
3. **VAE** must be `qwen_image_2.1_vae*`; **do not** choose a video VAE.
4. **Choose `.safetensors` only**; do not choose GGUF.
5. Uncensored set: use UC for UNET, keep TE/VAE on the two official rows; use a file containing `uncensored` for LoRA.
6. Keep **CLIPLoader type** `qwen_image`.

In the dropdowns, look for **`qwen_image` / `qwen-image` / `qwen3vl_8b` / `uncensored`** and avoid **`minimax` / `32b` / `h3` / `.gguf`**.

## Text-to-Image

Sidebar "Image → Text-to-Image". Choose an image Provider and a `t2i` workflow pack.

- **`qwen_image_21`**: official three-piece set.
- **`qwen_image_21_uncensored`**: UC + Uncensored LoRA switch.
- **`flux3_klein`**: FLUX.3 Klein distilled text-to-image. Four-piece set, 16 steps, do not replace the upsampler. See "FLUX.3 Image Klein" above.
- **`t2i_basic`**: a full package from `checkpoints/`.

The prompt can be rewritten by the configured LLM using the button on the right. Width, height, steps, seed, and image count can stay at each pack's defaults; set `flux3_klein` steps back to 16. Seed `-1` means random; for multiple images, add 1 per image starting from that seed.

## Image-to-Image & Edit

Sidebar "Image → Image-to-Image & Edit". Pack capability is usually `i2i`. Official and uncensored packs come in pairs; uncensored packs have a LoRA switch.

- **Full-image edit**: `qwen_image_21_edit` / `qwen_image_21_edit_uncensored`. Uses **only 1** original image, connected to `image_1` of `TextEncodeQwenImage21`. The upload box can select multiple images, but when the count exceeds this pack's image slots (1 here), "Start" is disabled. If the API still receives multiple images, only the first is used and the rest do not enter the workflow. Write what to change and what to keep, e.g. "change the background to a beach; keep the face and pose unchanged".
- **Multi-reference edit (put multiple people into one scene)**: `qwen_image_21_edit_multi` / `…_uncensored`. At least 2, at most 4, mapped to `` `<image1>` `` … `` `<image4>` `` in upload order. The first image is the main image and determines the canvas ratio. Use this pack to put people from several images into one scene, e.g. "place the person from `<image1>` next to the person from `<image2>` in the same room, with unified lighting". The tag must be written exactly as `` `<image1>` `` with no space; "image 1" or "图一" will not bind to the corresponding reference. When both images are person photos, the model will paint both people into the scene. To keep only one person, use a scene without a person for the other image, or switch back to full-image edit and describe the background in the prompt.
- **Inpainting**: `qwen_image_21_inpaint` / `…_uncensored`. Original image first, then mask; white = repaint, black = keep. `grow` expands the white area.
- **FLUX.3 single-image edit**: `flux3_klein_edit`. 1 original image; prompt the edit instruction; 16 steps. See above.
- **FLUX.3 multi-image edit**: `flux3_klein_edit_multi`. 2–4 images; can also put people from multiple images into one scene. Use "the first image" and "the second image" in the prompt, not Qwen's `` `<image1>` ``. 16 steps. See above.
- **Color grading reference**: `qwen_edit_2511_color_grade`. Image 1 is the original, image 2 is the color reference; leave the prompt empty; 20 steps, CFG 4. See "Color Grading Reference" above for model and node requirements.

### PoseStudio Pose Packs

The two packs require the ComfyUI nodes `TextEncodeQwenImage21`, `QwenImage21Cache`, and `GetImageSize` (installed with the Qwen-Image 2.1 node pack). The LoRA is `loras/VNCCS_QI2_PoseStudioV1.1.safetensors`; the default main model is `qwen_image_2.1_int8_convrot.safetensors`, the text encoder is `qwen3vl_8b_int8_convrot.safetensors`, and the VAE is `qwen_image_2.1_vae_bf16.safetensors`. A line-art pose image can come directly from Depth Map Generation or be imported externally.

- **Pose transfer**: `qwen_image_21_posestudio`. Image 1 is the person photo whose identity should be preserved; image 2 is a line-art or depth pose image. The default prompt is `Draw character from image2` and usually does not need changing; if you change it, describe only clothing, scene, and lighting, and do not repeat the limb motion. The output aspect ratio follows the pose reference; the resolution takes the larger of the two images, with a 2048 long-edge cap; line art is no longer cropped at white borders. 25 steps, CFG fixed at 1, LoRA strength 1.0. If the face drifts, lower the LoRA strength slightly.
- **Pose generation**: `qwen_image_21_posestudio_gen`. Upload only 1 line-art or depth pose image; describe the person's appearance, clothing, and scene entirely in the prompt. The default prompt is a full-body studio shot; change the prompt to change the person or outfit. The output size follows the pose reference; line art is not cropped at white borders.

### Union Depth and Reference Packs

The two Union packs require ComfyUI ≥ 0.37 and the node pack [Qwen Image 2.1 Fun ControlNet Union (T8)](https://github.com/T8mars/Comfyui-Qwen-Image-2.1-Fun-Controlnet-Union-T8). The default main model is the uncensored `qwen-image-2.1-UC-int8_convrot.safetensors`; the text encoder and VAE are still the same as `qwen_image_21`. Also place `Qwen-Image-2.1-Fun-Controlnet-Union-ComfyUI.safetensors` in `controlnet/`; the file name must start with `Qwen-Image-2.1-Fun-Controlnet-Union`. Weights: [t8star/Qwen-Image-2.1-Fun-Controlnet-Union-Comfy](https://huggingface.co/t8star/Qwen-Image-2.1-Fun-Controlnet-Union-Comfy).

- **Depth-to-person**: `qwen_image_21_union_depth`. Upload only 1 depth map; describe the person's appearance and scene in the prompt; motion follows the depth map. 40 steps, CFG fixed at 1.
- **Change a person's pose using a depth map**: `qwen_image_21_union_reference`. Image 1 is the person photo, image 2 is the depth map. Control type defaults to Depth; if image 2 is an OpenPose skeleton, change it to Pose. If the face drifts, lower the control strength to 0.7–0.8. Keep the aspect ratios of the two images as close as possible.

### Outfit Swap

`qwen_image_21_outfit_swap`. Image 1 is the person photo, image 2 is the garment (flat-lay or worn by someone else; crop to the garment itself when possible). Leaving the prompt empty uses the default sentence: replace the clothes of the person in image 1 with those in image 2, keeping face, hair, hands, pose, and background unchanged. To keep their shoes, change the ending to `Keep their own shoes and legwear.` For group photos, replace `the person` with a position or hairstyle; do not use clothing to identify the person. Resolution defaults to 0, which outputs at the person image's original size. Steps 25, CFG fixed at 1, LoRA strength 1.0. The main model defaults to official INT8 (this LoRA was tested on official 2.1). Put `qwen-image-2.1-outfit-swap.safetensors` in `loras/`; source: [ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA](https://huggingface.co/ausboss/Qwen-Image-2.1-Outfit-Swap-Consistency-LoRA). ComfyUI ≥ 0.38.

### Uploads and Slots

Uploads can be added in multiple batches, and individual images can be removed; you can also click "Choose from library" to pick existing images. The number of images you can submit equals the current pack's image slot count: full-image edit 1, multi-reference 2–4, inpaint original plus mask. Multi-reference and inpaint thumbnails have badges.

## Image Enhance (Moved to Tools)

The former "Fix & Upscale" has moved to sidebar "Tools → Image Enhance": `upscale_basic` does RealESRGAN faithful upscaling, and `seedvr2_3b_image_restore` does SeedVR2 generative restoration. See [Tools → Image Enhance](/en/guides/tools#image-enhance).

## Depth Map Generation

Sidebar "Image → Depth Map Generation". This page does not run a Comfy workflow; it sends images to an enabled **Liber Depth** (local plugin or a LAN depth service). Brighter means closer to the camera. You can convert multiple images at once; result file names append `_depth.png`, e.g. `photo.jpg` becomes `photo_depth.png`.

1. First install and enable the local depth plugin in "Settings → Plugins", or enable a Liber Depth entry under "Providers" and fill in the address (local default `http://127.0.0.1:5556`).
2. On the page, choose the depth service, depth model, and hardware (`cuda` or `cpu`). The dropdown only shows models enabled for that provider. The first open loads the default provider and model saved in "System Settings → Depth Map Generation"; if those are empty, it uses the first enabled depth service and `dpt_swin2_large_384`.
3. The upload box accepts multiple files and multiple batches, drag and drop, or "Choose from library" for existing images. Thumbnails can be removed individually. The same image (same file name, size, and modification time) is not added twice.
4. Click "Start conversion". Results for the batch appear on the right; you can also reopen or download them from depth map history.

Installing the plugin downloads only `dpt_swin2_large_384.pt` (SwinV2 Large, 384 px). One model is used per conversion. To use other MiDaS weights, place them in the model directory yourself and enable the corresponding switch under Providers; then they appear here:

| Model id | Purpose |
|---------|------|
| `dpt_swin2_large_384` | Default. Downloaded automatically during installation |
| `dpt_beit_large_512` | BEiT Large, 512 px, finer edges, slower |
| `dpt_swin2_tiny_256` | SwinV2 Tiny, 256 px, faster, less detail |
| `dpt_large_384` | Previous-generation DPT Large |
| `dpt_hybrid_384` | DPT Hybrid, smaller |
| `midas_v21_small_256` | MiDaS v2.1 Small, lightest |

If the directory lacks the corresponding `.pt` / `.pth`, selecting that item will not run inference with those weights. Generated depth maps can be used in the Union packs under Image-to-Image & Edit for depth-to-person or pose changes, or as PoseStudio pose references.

---

Related: [Tools → Image Enhance](/en/guides/tools#image-enhance); [Settings → Workflow Packs](/en/guides/settings#workflow-packs); [Video](/en/guides/video).
