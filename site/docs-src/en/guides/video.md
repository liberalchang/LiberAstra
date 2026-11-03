---
title: Video
---

# Video

Video has four generation modes plus a shared video library.

## Quick Create

Video -> Quick. Pick AI, fixed script, or batch. AI writes the script and storyboard; fixed script uses your copy; batch reuses the same settings across inputs. Storyboard count controls how many shots are planned. You can pause after the storyboard for manual review before rendering.

Quick Create can generate narration, subtitles, and stitch shots. Background music comes from the music library; image assets can be animated through i2v first.

## Digital presenter

Video -> Avatar. Upload or select a portrait, then write the narration.

The chain is: portrait + narration -> TTS -> avatar workflow. Long narration is split into sentences and joined at the tail frame. Choose a TTS provider and voice; the avatar pack must match the page capability.

## Image to video

Video -> I2V. Upload a first-frame image and write a prompt.

The still becomes the first frame. Long clips are split and joined with frame continuity. The available workflow packs are filtered to `i2v`; model families must match the pack.

## Motion transfer

Video -> Motion. Upload a reference clip (keep it under 30 seconds) and a target image, then write a prompt.

The clip drives motion; the target image supplies appearance. Length follows the reference clip. Longer clips split automatically and join. Template, character, and reference-image controls are on the same page.

## Assets, templates, characters

- Video Assets: uploaded and generated clips.
- Templates: HTML storyboard templates with placeholders. The filename prefix (`static_`, `image_`, `video_`) sets the type; the aspect must match 9:16, 1:1, or 16:9.
- Characters: name, appearance, optional reference images, and a five-view sheet (face, front, side, back, contact sheet). Video tasks use a single view per shot.

## Troubleshooting

If a workflow pack reports missing model files, choose an installed pack or place the required `.safetensors` in ComfyUI's `models/` tree. Use the exact filenames from the pack page. Do not mix MiniMax H3 with Qwen-Image weights.
