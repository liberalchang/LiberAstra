---
title: Video
---

# Video

Quick Create, Digital Human, Image-to-Video, Motion Transfer, and Custom Assets. Character Library is under Resources; Storyboard Templates are under Settings.

Sidebar order: **Quick Create** → **Digital Human** → **Image-to-Video** → **Motion Transfer** → **Custom Assets**.

## Packs and models

### Which pack to pick on each page

| Sidebar feature | Dropdowns on the page | Pack capability | Built-in packs |
|-----------------|-----------------------|-----------------|----------------|
| Quick Create · Generate Images | Image provider + image workflow | `t2i` | `qwen_image_21` / `qwen_image_21_uncensored`, `flux3_klein`, `t2i_basic` |
| Quick Create · Generate Video | Video provider + video workflow | Defaults to `t2v`; `i2v` is also available after picking a character | `minimax_h3_t2v` (official), `minimax_h3_t2v_uncensored` (uncensored, no enhancement), `minimax_h3_t2v_enhancer` (uncensored + enhancement); after picking a character, the `i2v` family appears too (first frame, multi-reference, orbit; the long-video Extender is mainly for the Director) |
| Digital Human | Video provider + pack; pick a voice separately | `avatar`, etc. | `minimax_h3_avatar` / `minimax_h3_avatar_uncensored` |
| Image-to-Video | Video provider + workflow pack | `i2v` | `minimax_h3_i2v` (first frame; the pack also has an optional last-frame slot) / `minimax_h3_i2v_uncensored` / `minimax_h3_i2v_enhancer`; also `minimax_h3_i2v_ref` (multi-reference), `minimax_h3_orbit` (360° orbit), and `minimax_h3_extender` (long video, mainly used by the Director) |
| Motion Transfer | Video provider + workflow pack | `motion`, etc. | `minimax_h3_motion` / `minimax_h3_motion_uncensored` |
| Custom Assets · Asset Animation | Animation provider + animation workflow | `i2v` | `minimax_h3_i2v` / `minimax_h3_i2v_uncensored` / `minimax_h3_i2v_enhancer` and other `i2v` packs |
| Custom Assets · Write Copy from Assets | Analysis provider + analysis workflow | `analysis` | `analysis_image_qwenvl` / `analysis_video_qwenvl` |
| Character Library · Generate from Description | Not selected on this page. Uses Settings → System Settings → Default Character Generation | `t2i` / `i2i` | Pick three packs: text-to-image, single-reference, and multi-reference; defaults are `qwen_image_21`, `qwen_image_21_edit`, `qwen_image_21_edit_multi` |

The sidebar's Tools → Video Enhance is a separate page. It uses a video provider and a `v2v` workflow pack (built in: `seedvr2_3b_video_restore`) and does not depend on the video generation pages above.

### How to choose on the page (general)

1. **Video / image / animation provider**: an enabled provider with a matching capability. After choosing ComfyUI, the model list is fetched from that machine's `/models/...`.
2. **Workflow pack**: filtered by the capability in the table above. The dropdown first shows the capability name and a one-line description; uncensored packs are marked "Uncensored". The bulb on the right opens the full description. After selecting a pack:
   - Models declared by the pack but missing on disk → yellow warning (submission is not blocked).
   - Expand the parameters: main model, text encoder, VAE, LoRA, and so on.
   - If the pack has `accel` → a **Turbo acceleration** or **Uncensored LoRA** toggle. MiniMax H3 Turbo carries sampling presets: turning it on sets steps and sampler to 8 steps and `euler`; turning it off restores the pack's own defaults. Values you already filled in for those two fields are overwritten too. The image uncensored LoRA has no step preset; the toggle only attaches or removes the LoRA. Currently MiniMax H3 video, Digital Human, Motion Transfer, and Qwen image-edit packs enable acceleration by default; turn it off in the parameters when you want to compare quality.
3. **Width/height and duration**: Image-to-Video uses an aspect ratio snapped to the pack's `multiple` (usually 32 for H3). Packs with `fps` take a duration in seconds; on submit it is converted to frames and snapped with `align_base` / `align_offset` (H3 uses 17k+5). Digital Human does not show a duration; the picture follows the voice.
4. H3 / long jobs: set **ComfyUI timeout** in Settings → System Settings → Run Parameters to at least 3600 seconds.

### MiniMax H3: Version = Complete Set of Files (Do Not Mix)

One "feature" on Comfy often maps to **multiple files**. The dropdowns let you change file names individually, but **the official / uncensored / quantization spec must be chosen as a complete set**; otherwise loading may fail or the result may be wrong.

#### Shared Files (Required by Official and Uncensored)

| Role | Directory | Current recommended files (common remotely) |
|------|-----------|---------------------------------------------|
| Main model FL2VA (first frame / first-last frame, text-to-video) | `diffusion_models/` | `minimax_h3_fl2va_pruned_int8_convrot.safetensors` |
| Main model Ref2VA (reference image / reference video, long video) | `diffusion_models/` | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` |
| Video VAE | `vae/` | `minimax_h3_video_vae_fp16.safetensors` |
| Audio VAE | `vae/` | `minimax_h3_audio_vae_fp32.safetensors` |
| Turbo LoRA (optional) | `loras/` | `minimax_h3_turbo_v4_step600_ema.safetensors`. The node is `MiniMaxH3TurboLoRA` (requires [Larryvrh/ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo)); keep the scheduler at `simple`. The dropdown only lists weights whose filename contains `_ema` |

FL2VA and Ref2VA are two separate sets of weights. Do not mix them in one workflow: `minimax_h3_i2v`, `minimax_h3_orbit`, `minimax_h3_t2v`, and Digital Human use FL2VA; `minimax_h3_i2v_ref`, `minimax_h3_motion`, and `minimax_h3_extender` use Ref2VA. `minimax_h3_orbit` uses `minimax_h3_video_vae_int8_convrot.safetensors` as its default video VAE, while other H3 packs default to fp16; it also uses `loras/minimax_h3_flf2v_lora_v1.safetensors` (a first-last-frame orbit LoRA), not Turbo. When you change the main model, the whole chain still uses the same VAE. Other quantization variants (unpruned INT8, FP8, W6A8, etc.) have different sizes; do not mix them.

> RTX 3090 / Ampere: use Comfy-Org's `minimax_h3_ref2va_pruned_int8_convrot.safetensors` (about 21GB). Community NVFP4 weights target Blackwell; on non-Blackwell cards NVFP4 is emulated, so speed and compatibility are not guaranteed.

#### Text Side: Official Set vs Uncensored Set

| Set | Text encoder (TE, `text_encoders/`) | Generation tail (tail, only needed for prompt enhancement) | Matching built-in packs |
|-----|-------------------------------------|-----------------------------------------------------------|--------------------------|
| **Official** | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | Usually not needed; official enhancement needs a matching `…instruct_generation_tail…` | `minimax_h3_i2v` / `minimax_h3_t2v` |
| **Uncensored NVFP4 (no enhancement)** | `qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` | Not needed | `minimax_h3_t2v_uncensored` / `minimax_h3_i2v_uncensored` |
| **Uncensored INT8 + enhancement** | `qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors` | `qwen3vl_32b_h3_generation_tail_50_63_int8_convrot.safetensors` | `minimax_h3_i2v_enhancer` / `minimax_h3_t2v_enhancer` |

Pairing rules:

- **TE and tail must be from the same family** (official pairs with the instruct tail; uncensored pairs with the matching heretic tail).
- `CLIPLoader` type is `minimax` for all of them; changing files does not change the node type.
- In `minimax_h3_i2v`, swapping only the TE dropdown to an uncensored file gives you **uncensored output without prompt enhancement** (Guide is still optional). To "rewrite the prompt from an image", you must use an enhancer pack and install the [Guide node pack](https://github.com/ethanfel/ComfyUI-MiniMax-H3-Guide).

#### Understanding Quantization

The same role often has several quantization files (for example TE in nvfp4 / int8_convrot / bf16). **Pick one spec and use it throughout.** Do not use pruned-int8 for the main model and then mix in an unverified TE combination. On a 3090 the official nvfp4 runs but is not the fastest; the uncensored TE (about 25G) uses more memory, so on a remote 62G machine watch separately for OOM.

A more detailed file list and download links are in [Model resources](/en/models).

## Other generation modes

### Custom Assets

You already have images or videos; add voiceover and subtitles and join them into one short video in upload order. The picture stays as-is by default.

From top to bottom the page is: Assets → Copy and Title → Asset Animation → Voice → Aspect Ratio, Subtitles, and Background Music. When Asset Animation is on or a video is uploaded, the voice can be switched to **model audio**, keeping the animation or video's own audio track. After clicking **Start Compositing**, the order is: copy is finalized → if there is a title, make a 2-second title card first (no subtitles burned in) → with custom voice, synthesize each segment and write subtitles; with model audio, write subtitles using each clip's own duration → keep images still or animate them according to the toggle → join into one video → mix in background music if selected.

#### Assets

The order is the shot order. You can add multiple times, or click **Choose from Library** to pick existing images or videos. Each video segment is looped or trimmed to the duration of that voiceover line.

#### Copy and Title

The title is optional. If filled in, the video opens with a 2-second title card.

There are three copy modes; they do not affect each other:

| Option | How the voiceover is produced | Looks at the picture? |
|--------|-------------------------------|-----------------------|
| Your own copy (one line per asset) | You write it. One line per asset, matching asset order; if there are fewer lines, they repeat | No |
| Generate copy from topic | Fill in only the topic and target duration. Copy is written from filenames and video durations. Requires the default LLM in System Settings | No |
| Write copy from assets | Upload assets, then click **Generate Copy**. A vision model looks at each image and video, then writes the voiceover. You can edit the result; the edited text is what gets used | Only when you click **Generate Copy** |

Writing copy from assets also requires:

- **Analysis provider**: the ComfyUI that runs the analysis.
- **Image analysis workflow**: required when there are images. Built in: `analysis_image_qwenvl`, which needs ComfyUI-AILab and Qwen-VL (default Qwen3-VL-8B-Instruct).
- **Video analysis workflow**: required when there are videos. Built in: `analysis_video_qwenvl`, which also needs Video Helper Suite to extract frames.
- **Extra requirements**, **target duration**: optional. Use them to specify tone, selling points, and sentence length. Leave blank to write only from the picture.

**Generate Copy** is unavailable when no assets are uploaded. You cannot start compositing if this voiceover is empty.

#### Asset Animation

The toggle is off by default. When on, it takes effect only inside **Start Compositing**, after that segment's voice is ready: each still image goes through `i2v` once to generate a short motion clip, which is then looped or trimmed to the voiceover duration and given subtitles.

Uploaded videos and the title card stay as-is. The toggle is unavailable when the current assets contain no images.

If the animation prompt is empty, the default is a slight, natural camera push-in. If filled in, your motion description is used. Pick an `i2v` pack as the workflow, for example `minimax_h3_i2v`, `minimax_h3_i2v_uncensored`, or `minimax_h3_i2v_enhancer`; multi-reference and orbit packs can also be used, with images sent to their own image slots. If the pack has `accel`, Turbo can be enabled. Each image runs one image-to-video job; more images take longer.

#### Voice, Aspect Ratio, and Background Music

The voice is synthesized segment by segment following the assets, and subtitle timing follows that voice line. You can turn off burning in, and change subtitle font size and color: font size 0 means automatic, and the color defaults to white. The title card does not get subtitles. If the voice provider is ComfyUI, choose a speech workflow separately; the voiceover text is injected automatically. Local TTS or API TTS can be previewed under the voice, see [Text-to-Speech](/en/guides/speech#text-to-speech). Aspect ratio is 9:16, 1:1, or 16:9. Background music is chosen from the Music Library and mixed in after the whole video is joined.

When **Model native** is selected and the animation workflow supports reference audio, the voice section shows **Audio continuity (experimental)**:

- **Model native**: no extra processing; current behavior.
- **Previous shot tail**: take the last 2–15 seconds of the previous animated clip as the next shot's reference; the first shot has no reference.
- **Whole-film ambience bed**: choose or upload an audio track and slice it by each shot's actual duration for H3; loop it or pad silence when the bed is shorter. Final mixing can be **bed-first with model ambience at low volume** or **bed only**.
- Seam fade applies only to music/ambience and defaults to 60 ms. It is a separate layer from the final background music; prefer only one of them.
- Custom voice, or a workflow without a reference-audio input, does not show this control.

### Digital Human

Character image + voiceover copy → TTS voice → `avatar` workflow pack. Two built-in lip-sync workflows are based on the MiniMax H3 joint audio-video model (no extra lip-sync plugin or audio encoder needed):

| Pack | Default text side | How it works and what it is good for |
|------|-------------------|--------------------------------------|
| `minimax_h3_avatar` | Official TE | `MiniMaxH3ImageToVideo` locks the first-frame character; `MiniMaxH3AddGuide` anchors the TTS voice latent at frame 0 to drive lip movement and expression, and the finished video carries the clean TTS audio directly; Turbo can be enabled |
| `minimax_h3_avatar_uncensored` | Uncensored **NVFP4** TE | Same as above, but uses the uncensored text encoder by default; Turbo can be enabled |

Pick a voice provider and voice separately. The picture duration is determined by this voice; you no longer enter seconds on the page. Frame count is rounded up to `17k+5` and then trimmed back to the voice length, leaving only about one extra frame. If the estimate exceeds about 12 seconds, or the result still exceeds the per-segment limit (362 frames, about 15 seconds), it is split by sentence; the next segment uses the previous segment's last frame as its first frame, and the segments are joined into one video. Later segments no longer return to the character sheet, so with many segments the character may still drift. After compositing, you can add background music from the Music Library. Local TTS or API TTS can be previewed under the voice, see [Text-to-Speech](/en/guides/speech#text-to-speech).

The character image can be uploaded, chosen with **Choose from Library**, or picked from Character Library. When a character is selected, **only the first segment** uses the character's **facial half-body close-up** (the 9:16 single view split from the four-grid) as its first frame; it does not use the full-body image or the entire sheet. Uploaded images take precedence over Character Library. If the character has a bound voice, it is used when no other voice is selected.

### Image-to-Video

First frame + prompt → `i2v`. The page renders every image slot declared by the pack: the first frame is required, while the optional last frame, side/back references, and extra reference images appear under "More images". The finished video keeps the model-generated audio track; you can also add background music from the Music Library.

| Pack | Default text side | Characteristics |
|------|-------------------|-----------------|
| `minimax_h3_i2v` | Official TE | First frame is required; upload the optional last-frame slot `last_frame` under "More images"; the prompt goes into generation as-is; Turbo can be enabled |
| `minimax_h3_i2v_uncensored` | Uncensored **NVFP4** TE | **Uncensored, no enhancement**; first frame required, optional last frame; LightX2V 8-step by default; Turbo can be enabled |
| `minimax_h3_i2v_enhancer` | Uncensored INT8 TE + tail | First frame required, optional last frame; Guide enhancement runs before rendering; the enhanced text is visible in the result area; Turbo can be enabled; Guide is required |
| `minimax_h3_i2v_ref` | Official TE | Up to 9 reference images, all shown on the page; images only provide appearance and are not used as the first video frame; refer to them with `<Picture N>` in the prompt; Turbo can be enabled |
| `minimax_h3_orbit` | Official TE | 360° orbit shot; with one image, the same image is used for both start and end, and a second image uploaded on the page becomes the ending frame; leaving the prompt empty uses the built-in orbit sentence; with two different images and the original prompt unchanged, an outfit-change sentence is added automatically; default 73 frames (about 3 seconds), 28 steps, no Turbo needed |
| `minimax_h3_extender` | Official TE | Long-video Extender: `clips_json` describes each segment's duration and prompt, reference images are passed through `ref_1` to `ref_9`, and each segment is at most 15 seconds; mainly generated by the Director |

The enhancer is slower and uses more memory; it is suitable when the prompt is very short or when you want it rewritten into an H3-style long prompt first. `i2v_ref` reference images are not the first frame; they are for giving character, clothing, and scene references and letting the model choose the starting camera position. `orbit` is good for orbiting a character or product in place; it is most stable when the camera and subject stay still, and it drifts easily when the scene contains a lot of motion.

After selecting a character from Character Library, choose the camera view for this shot: facial half-body close-up, full-body front, full-body side, or full-body back. The page fills empty reference slots with character images; uploaded images take precedence. Multi-reference slots unlock in order: `image_2` must be filled before `image_3`, and clearing an earlier slot clears later slots so `<Picture N>` numbering stays aligned. The ending frame for `orbit` and the last frame for `i2v` are uploaded in the same "More images" block. Use close-ups for near shots and the matching full-body image for full-body motion. Quick Create can rotate views across shots, which uses multiple character sheet images. Images can be uploaded or chosen from the library; uploaded images take precedence over Character Library. The Motion page also shows the pack's side and back reference slots, mapped to `<Picture 2>` and `<Picture 3>`.

#### Audio reference for image-to-video (H3)

`minimax_h3_i2v_ref` and `minimax_h3_extender` provide reference audio in the **Audio** block:

- `minimax_h3_i2v_ref`: optional **reference audio** gives the model ambient sound/music as a guide for a consistent atmosphere. It is a reference, not audio locking; a single-pack run does not offer "previous shot tail" or "whole-film ambience bed".
- `minimax_h3_extender`: **Audio continuity** offers off, audio context, reference audio, or both. Context length 22 is common; 44/96 is stronger but slower and uses more VRAM. Reference audio can come from the Music Library or an upload. Enabling both is an advanced experiment.
- These references do not replace the final background music; background music is still set separately under **Advanced → Background music**. Enabling both layers can duplicate the music.

### Motion Transfer

Reference video + target image + prompt → `motion` workflow pack. The reference video can be uploaded or chosen from the library. Picture duration follows the reference video; you no longer enter seconds on the page. The reference video is split at the motion pack's `length.max` (the current two H3 motion packs use 124 frames, about 5.2 seconds, and satisfy `17k+5`); every segment keeps the same target images so the previous tail frame cannot pull the identity off course, and the segments are joined into one video. Audio can keep the model-generated track or be replaced with the reference video's entire original audio. Either way, you can add background music from the Music Library. Two built-in motion-transfer workflows are based on MiniMax H3 multimodal reference (`MiniMaxH3ReferenceToVideo`). After selecting a character from Character Library, the target-image option determines what is sent: the default **front, side, and back three full-body images** sends **full-body front, full-body side, and full-body back** as `<Picture 1>`, `<Picture 2>`, and `<Picture 3>`; choosing **16:9 character sheet** or **9:16 four-grid** sends only that entire sheet as `<Picture 1>` and does not split it into front/side/back. The right-side facial close-up is not used for motion transfer, to avoid losing lower-body clothing. The target image can be uploaded or chosen from the library; uploaded images take precedence over Character Library. Two optional extra reference slots are also available, mapped in order to `<Picture 4>` and `<Picture 5>`; unconnected slots are detached automatically.

| Pack | Default text side | How it works and what it is good for |
|------|-------------------|--------------------------------------|
| `minimax_h3_motion` | Official TE | `VHS_LoadVideo` extracts frames at 24fps as the `<Video 1>` motion reference, and the target image is the `<Picture 1>` identity reference; body motion and camera movement transfer without skeleton preprocessing; Turbo can be enabled |
| `minimax_h3_motion_uncensored` | Uncensored **NVFP4** TE | Same as above, but uses the uncensored text encoder by default; Turbo can be enabled |

In the prompt, `<Picture 1>` refers to the target image and `<Video 1>` to the reference video. If no tags are written or the prompt is empty, the pipeline adds the standard motion-transfer instruction automatically and states that images own the person's identity while the video only supplies motion, so the video person's face, hair, and clothing must not be copied. You can also import your own `WanAnimate2ToVideo` or `WanSCAILToVideo` workflow pack.

#### Motion-transfer prompt example

When the node prompt is empty, the default instruction is enough. If the reference video contains a real person and you are worried the model will copy that person, paste the following to pin the identity to the images:

```text
Use <Picture 1> (front), <Picture 2> (side), and <Picture 3> (back) as identity references for the same person. Always keep this person's face, facial features, hairstyle, skin tone, body shape, and clothing. <Video 1> only supplies body motion, pose changes, and camera movement. Do not copy the face, hairstyle, or clothing of the person in the video, and do not change the face or outfit mid-video. Keep the motion natural and follow the camera movement of <Video 1>.
```

If you enabled the extra reference slots, append:

```text
<Picture 4> and <Picture 5> are also supplementary references for the same person; identity still follows <Picture 1>.
```

## Quick Create

Quick Create turns voiceover into a short video. The voiceover is the line spoken in each shot; the voice reads that line and the subtitle shows it. It is not a finished video file.

A finished video can have multiple shots. Each shot is made separately as a short segment: the line goes to the voice, and the picture follows that shot's visual prompt. All segments are joined in order, and background music is added if needed, to produce the mp4 you download. A shot count of 4 means 4 short segments joined into 1 video, not 4 separate videos.

The **AI Create**, **Fixed Script**, and **Batch Create** tabs at the top only decide where the voiceover lines come from. The storyboard template, voice, subtitles, character, and background music below are shared by all three modes.

### What Is in a Finished Video

Each shot has two pieces of text:

- **Voiceover**: the line that is spoken, and also the subtitle for that shot.
- **Visual prompt**: the description handed to the image or video workflow. Static templates do not use it to generate images; the text is laid directly into the layout.

The title is one line shared by the whole video. It is displayed on the picture and is not read as one of the voiceover lines.

You can enable **Pause after storyboard generation; composite after manual confirmation**. When enabled, the script and storyboard JSON are produced first, and compositing starts after you edit each shot's visual prompt. Batch Create does not have this option.

### AI Create

Use this when you have not written a script yet and only know what to talk about. Enter a topic, then set the shot count (1 to 12, default 4).

The original topic becomes the video title and is displayed on the picture. The default large language model (LLM) in System Settings writes the voiceover according to the shot count. With a shot count of 4, it writes 4 lines of about 20 to 40 Chinese characters each, in a conversational tone. Those 4 lines map to 4 shots: line 1 goes with picture segment 1, line 2 with segment 2, and the four segments are joined into one video. A title invented by the LLM is not used; the title is always the topic you wrote.

The ✨ on the topic field only expands your topic into something more specific, to make the later voiceover easier to write. The voiceover itself is written by the LLM only after you click **Start Creating**.

If the template is **Generate Images** or **Generate Video**, there is also **Use the LLM to write visual prompts during generation**, on by default. When on, after the 4 voiceover lines are written, the LLM rewrites each line into a visual description for image or video generation. When off, the visual description uses the voiceover text as-is. Workflow packs with Guide (names containing `enhancer`) also rewrite the prompt once inside the pack; packs without it (for example `uncensored`) do not. That in-pack enhancement and the page toggle are two separate things; turning one off does not turn off the other.

Static style templates do not write visual prompts. The voiceover text is laid directly into the layout and read aloud.

An LLM must already be configured. If it is not, the page prompts you to go to System Settings or Providers.

### Fixed Script

Use this when the script is already written and you want the exact sentences spoken. The voiceover is exactly the text you paste in; the system does not rewrite it into other sentences. The topic field next to it is only the title, displayed as-is and not passed through AI.

This page has no shot count. How many shots there are is determined by the **split mode**:

| Split mode | What counts as one shot |
|------------|--------------------------|
| By paragraph | A blank line starts a new paragraph. One paragraph per shot |
| By line | Each non-empty line is one shot |
| By sentence | Split at periods, question marks, and exclamation marks. One sentence per shot |

For example, with sentence splitting, a script with 6 sentences produces 6 short segments joined into 1 video. Empty segments are dropped.

Static templates read and lay out the text according to the split result. With image or video templates, the left side of the input area is the voiceover; click ✨ to generate a visual prompt per shot. If the toggle is on and the right side already has a visual prompt, compositing uses that text directly and the backend does not ask the LLM to rewrite it. If the toggle is on but the right side is still empty, the LLM fills in a visual prompt from the voiceover. If the toggle is off, the visual description uses the voiceover text as-is.

Fixed Script does not require an LLM when using a static template or when the visual prompts are already written.

### Batch Create

Use this when you want many videos with different topics using the same template and voice. One topic per line in the text box, up to 100 lines. Blank lines do not count.

One topic line corresponds to one complete video and is also that video's title. It is not one shot. The shot count still applies: it is the number of shots inside each video, shared by all topics.

For example, with 3 lines and a shot count of 4, 3 jobs are queued. Each job is a complete AI Create run: write 4 voiceover lines for that topic, produce 4 picture segments, and join them into 1 video. Template, voice, character, subtitles, and background music are all shared. A failed job does not affect the others; view or cancel progress in the Job Center. Batch Create requires an LLM and does not have **Pause after storyboard generation**.

### Picture, Sound, and Subtitles

First choose the aspect ratio (portrait 9:16, square 1:1, or landscape 16:9), then the template mode, then the specific template:

- **Static style**: laid out locally; does not call image or video generation and does not ask the LLM for visual prompts. The voiceover text appears on the picture and is read aloud.
- **Generate images**: each shot uses a text-to-image (`t2i`) workflow to produce one image, which is then joined with that line's voice into a short segment.
- **Generate video**: each shot uses a video workflow to produce a short segment. By default only text-to-video (`t2v`) packs are listed. After picking a character, image-to-video (`i2v`) packs are added: a normal `i2v` pack sends one camera-view image, an `i2v_ref` pack can take multiple reference images (Quick Create still sends only the current camera view per shot; use the Image-to-Video page or canvas for multi-reference), `orbit` does a 360° orbit, and `extender` is a long-video segmentation pack mainly used by the Director and not recommended for manual selection in Quick Create. If the pack declares acceleration, Turbo can be enabled. Packs whose names contain `enhancer` enhance the prompt inside the pack.

Voice, subtitles, and background music are below the template and shared by all three script modes:

- Static and image templates only support custom voice: synthesize each voiceover line and replace the audio track of that short segment.
- Generate Video can also use **model audio**: keep the audio produced by the text-to-video model instead of replacing it with a voice. Subtitles are still written from the voiceover text and that segment's duration.
- When the voice is local TTS (text-to-speech) or API TTS, you can preview it under the voice, see [Text-to-Speech](/en/guides/speech#text-to-speech). If the voice provider is ComfyUI, choose a speech workflow separately; the voiceover text is filled in automatically.
- Subtitles can be turned off, and their font size and color can be changed. The title and the on-screen voiceover text can also be hidden or scaled separately.
- Background music is chosen from the Music Library and mixed in after the whole video is joined. A volume of 0.1 to 0.3 is recommended.
- When Generate Video uses **model audio** and the selected video pack supports reference audio (for example `minimax_h3_i2v_ref`), **Audio continuity (experimental)** appears: model native / previous shot tail / whole-film ambience bed. Previous shot tail runs in order; the ambience bed is sliced by each shot's actual duration and is not the final background music. Final mixing can be **bed-first with model ambience at low volume** or **bed only**. Custom voice or a pack without reference audio does not show this control.

### Characters and Camera View

The character is optional. All three script modes can pick one, and Batch Create shares the same character across all topics.

After selecting one, two different things happen.

The first always happens: the character's appearance description is prepended to each shot's visual prompt, so the shots are textually the same person. Layout sentences such as "16:9 landscape, 9:16 four-grid, four views" in the character sheet description are removed first, to avoid the picture being drawn as a collage. The style prefix you enter on the page is placed after this appearance text.

The second happens only when the video pack actually has an image input slot. Pure text-to-video packs have no image slot, so the character image is not uploaded. In that case the **camera view** is only a text hint to the LLM, for example that the current reference view is front, so it can write the visual description from that angle.

After selecting a character, you can switch the video workflow to an image-to-video pack. Such packs send one character image per shot according to the view, to lock the same person:

- By default the view you selected is used: facial half-body close-up, full-body front, full-body side, or full-body back.
- When the LLM writes the storyboard, it can switch a particular shot to another view, which uses multiple character sheet images.
- Choosing **16:9 character sheet** or **9:16 four-grid** sends that entire sheet for every shot instead of splitting it into individual views.
- If that view has no image yet while the workflow requires a reference image, the job fails directly.

Image templates only write the appearance into the prompt and do not send the character image into the text-to-image pack.

### Which Text-to-Video (`t2v`) Pack?

| Pack | Text side | Notes |
|------|-----------|-------|
| `minimax_h3_t2v` | Official TE | Pure prompt-to-video; Turbo can be enabled |
| `minimax_h3_t2v_uncensored` | Uncensored **NVFP4** TE | **Uncensored, no enhancement** (corresponds to the local canvas Text-to-Video); LightX2V 8-step Turbo by default; Turbo can be enabled |
| `minimax_h3_t2v_enhancer` | Uncensored INT8 TE + tail | **Uncensored + prompt enhancement**; requires Guide; the enhanced text is visible in the result; Turbo can be enabled |

None of the three accepts a first frame. To give each shot a character image, switch to `minimax_h3_i2v` / `minimax_h3_i2v_uncensored` / `minimax_h3_i2v_enhancer`.

## Characters and templates

### Character Library

The sidebar's Resources → Character Library stores a character's name, appearance description, two sheet layouts, and four individual views:

- **9:16 four-grid (primary)**: `1152×2048`, a 2×2 grid where each `576×1024` cell is still 9:16. Top-left face half-body close-up, top-right full-body front, bottom-left full-body side, bottom-right full-body back. The app splits fixed quadrants into four 9:16 views used as the facial close-up, full-body front, full-body side, and full-body back. Portrait video, motion transfer, and digital human prefer these four.
- **16:9 character sheet**: `1536×864`, four landscape columns from left to right: full-body front, full-body side, full-body back, and a right-side face half-body close-up. It is generated after the four 9:16 views: the app composes them into a 16:9 reference, then uses a multi-image edit workflow to redraw a native landscape sheet. It is used for preview, whole-sheet reference, and 16:9 image-to-video.

The whole sheet is only for preview and whole-sheet reference; it is never used directly as a video frame. Video uses one 9:16 view per shot by default. If a 16:9 video must lock its first frame, use a reference-only pack such as `i2v_ref`, or generate a separate 16:9 first-frame still; the four 9:16 views are not 16:9 first frames.

Choose one add method on the page; the other method's button does not appear at the same time.

#### Generate from Description

Use this when you have no image and only an appearance. Enter a name, plus age, face shape, hairstyle, and clothing. You can also upload 1 to 3 reference images (or choose them from the library); when reference images are present, the appearance description can be left empty. One image uses the **single-reference workflow** in System Settings; 2 to 3 images use the **multi-reference workflow**. References are first pasted onto a 9:16 light-gray canvas to keep the four-grid portrait.

You can click ✨ to use the default LLM in **System Settings** with the prompt template **Character Library · Character Appearance** (`character_sheet`). Optimization only completes the face, headwear, bottoms, shoes, and quality; it no longer hard-codes the layout. Generation appends the four-grid and landscape compositions separately.

**Generate Character Sheet** runs these steps:

1. Generate the 9:16 four-grid and split it into four 9:16 views, saving them immediately.
2. Use those four views as references for a second image-to-image pass that generates the native 16:9 four-column sheet. By default it composes a 16:9 reference image, then uses the **multi-reference workflow**; if unavailable it falls back to single-image editing.
3. If the 16:9 pass fails, the four 9:16 views are kept; the app composes a 16:9 overview from them and notes the failure in the job result.

The image provider, four-grid workflow pack, single-reference workflow, and multi-reference workflow are all in **System Settings → Default Character Generation**, not on the character page. With no reference images the default pack is `qwen_image_21`, targeting `1152×2048`; if the selected pack's width/height limit is smaller, it shrinks proportionally while keeping 9:16.

#### Upload a Character Sheet

Use this when you already have a finished sheet. Choose the layout first:

- **16:9 four-column**: from left to right, full-body front, full-body side, full-body back, and right-side facial close-up. It detects vertical gaps and splits dynamically.
- **9:16 four-grid**: top-left face close-up, top-right full-body front, bottom-left full-body side, bottom-right full-body back. Equal cells with light-gray gutters. It splits fixed quadrants, and each output stays 9:16.

You can also choose an image from the library next to the upload box. The appearance description can be left empty; if filled in, Quick Create prepends that text to every picture. Click **Save and Auto-Split** to split and create the record immediately without calling the image provider.

Do not upload a single portrait, a three-panel turnaround, or a layout that does not match the selected type; cuts may land on the person or bring neighboring cells along.

Split rules:

- 16:9 landscape: find gaps between the three figures from column brightness changes and cut at each gap midpoint; if there are fewer than three gaps, fall back to roughly `23% / 22% / 23% / 32%`. If the right close-up still has a gray edge, move the cut right along the top color-block boundary.
- 9:16 four-grid: do not analyze gaps; split at the exact width/height midlines. Generation and uploads must therefore keep figures from crossing the center lines.

Click a card thumbnail to open the large view and switch left/right among the facial close-up, full-body front, full-body side, full-body back, 16:9 sheet, and 9:16 four-grid sheet.

Image files are under `backend/data/characters/`.

### Storyboard Templates

Settings → Storyboard Templates. Upload/delete storyboard templates. Filename prefixes: `static_` / `image_` / `video_`. Canvas size must match the aspect-ratio directory. Built-in entries cannot be deleted; user files with the same name override built-in entries.

## Quick reference

### ComfyUI model directory

| Purpose | Directory (relative to `models/`) | Common files |
|---------|-----------------------------------|--------------|
| Image/video main model (UNET) | `diffusion_models/` | `qwen_image_2.1*` / `qwen-image-2.1*` (**do not** mix `minimax_h3_*`) |
| Text encoder / generation tail | `text_encoders/` | Images use `qwen3vl_8b*`; video H3 uses `qwen3vl_32b*` (**do not mix**) |
| VAE | `vae/` | Images use `qwen_image_2.1_vae*`; video uses `minimax_h3_*_vae*` |
| Turbo / UC / style LoRA | `loras/` | Video Turbo, image uncensored, PoseStudio, outfit swap, color grading, and their respective LoRAs |
| Legacy SD checkpoint | `checkpoints/` | Only `t2i_basic` |
| Upscale model | `upscale_models/` | RealESRGAN used by `upscale_basic` |
| SeedVR2 | `SEEDVR2/` | `seedvr2_ema_3b_fp16.safetensors` + `ema_vae_fp16.safetensors` (numz nodes) |
| ControlNet | `controlnet/` | Qwen-Image 2.1 Fun ControlNet Union |

---

Related: [Image](/en/guides/image) / [Speech](/en/guides/speech) / [Tools](/en/guides/tools); [Settings → System Settings](/en/guides/settings#system-settings).
