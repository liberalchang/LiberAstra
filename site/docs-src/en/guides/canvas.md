---
title: Canvas & Director
---

# Canvas & Director

Canvas nodes, variable bindings, Director conversations, and run state.

Sidebar "Canvas". A canvas is a saved flow graph: inputs, workflow packs, speech, and concat execute in order along the connections. Image, audio, and video generation still go to your configured providers and workflow packs.

**Note:** The sidebar "Tools" entry is separate: media concat and image/video enhance have their own pages and do not go through the canvas. The Concat node inside a canvas only concatenates; its outputs remain canvas intermediate results.

## Open and save

Clicking "Canvas" in the sidebar again opens the canvas you last edited, as long as you have not clicked "Exit" in the top-left corner. "Exit" returns to the list and cancels that automatic reopen. Adding `?mode=list` to the URL also goes straight to the list.

In the list you can create, duplicate, and delete canvases. Deleting removes the canvas and its node run records. Finished outputs that were saved with "Save to Assets" remain in the asset library. The list page has two tabs, "Canvas" and "Menu Settings"; the latter maintains the functions available on the canvas, see "Canvas Menu" below.

Top right of the editor: canvas name, save (Ctrl+S; the button shows `Save *` when there are unsaved changes), groups (opens "Settings → Workflow Packs → Canvas Groups"), and run. If you click "Exit" in the top-left with unsaved changes, you are asked first.

Bottom row: undo (Ctrl+Z), redo (Ctrl+Shift+Z or Ctrl+Y), add node, hand, select, and tidy. Tidy arranges nodes from left to right by dependency.

- Double-click empty space, or click `+` at the bottom, to open the add-node menu. The menu has "Input", "Concat", and function categories; the function categories read the items from Menu Settings.
- Drag from the dot on the right side of a node to draw a connection. Releasing on empty space creates a downstream node at that point and connects it automatically. The `+` on a node card also creates a downstream node.
- Hand mode pans with the left mouse button. Select mode draws a selection box with the left button; the middle or right button still pans. The wheel zooms, roughly 0.25× to 1.8×. The minimap in the bottom-left pans and zooms.
- Connections cannot form cycles or enter input nodes. Video Concat accepts only video; Audio Concat accepts only audio. Delete or Backspace removes the selected node or connection.
- One canvas supports up to 200 nodes and 400 edges.

## Canvas Menu

Which functions a canvas can use is decided by "Menu Settings" on the canvas list page. From the sidebar "Canvas", enter the list and switch to the "Menu Settings" tab. It maintains function items in four categories: speech, image, video, and tools:

- **Function item**: a short name of 2–10 characters plus a one-line description; choose a sub-capability (for example text-to-image, single-image edit, outfit swap, image-to-video), then decide how it binds.
- **Auto match**: lists every enabled model and workflow that has that capability; new nodes use the default target.
- **Manual**: lists only the models or workflows you checked; useful for pinning a specific machine or pack.
- **Tool item**: only Image Concat, Video Concat, and Audio Concat. They run locally and need no model, provider, or workflow pack.

The Audio Extract tool takes one video or audio input, extracts either the full audio track or a fixed-length tail (0.5–15 seconds), and outputs audio that can feed a function node's reference-audio slot.

The canvas top bar "All functions" lists the function items from Menu Settings. In the bottom `+` menu, "Input" and "Concat" are fixed input/concat nodes; the "Speech", "Image", and "Video" groups read the menu items. Creating a node from a function item loads that item's default target and, based on the pack or model's required image, video, and audio slots, creates upstream input nodes on the left and connects them. If an upstream already provides the same media type, it is not created again. When you switch packs, model-file parameters return to the new pack's defaults so you do not carry the previous UNET, text encoder, or VAE into another family.

Click "Finish editing" to save; the enable switch and delete also save immediately. When the built-in menu structure is upgraded, image, video, and tools are rebuilt for the new version; speech keeps the model you specified; items you deleted in the current version are not restored.

## Workflow Groups

A Function node first chooses a "Group", then a workflow pack inside that group. When no groups exist yet, the add-node menu offers "Create default groups by capability": `t2i` / `i2i` / `upscale` go to "Image", `t2v` / `i2v` / `avatar` / `motion` go to "Video", `tts` / `asr` go to "Speech", and `analysis` goes to "Visual analysis".

The function categories in the add-node menu list image and video groups, followed by fixed Text-to-Speech and Speech-to-Text entries. Those two speech nodes use your configured speech service. A group that contains only speech workflow packs and whose packs have no image or video inputs does not appear in this menu; add any Function node first, then change its "Group" on the right.

Manual adjustment is under "Settings → Workflow Packs", on the "Canvas Groups" tab:

1. **Add workflow pack**: assign each pack to a group. The group name is the "Group" shown on the canvas.
2. **Group management**: create, rename, and delete. After deleting a group, its packs return to the default groups named by capability: text-to-image, image-to-image, upscale/restore, text-to-video, image-to-video, avatar, motion transfer, and visual analysis.

When you add a Function node from a group in the menu, it loads the group's first pack and, according to the pack's required image, video, and audio parameters, creates upstream input nodes on the left and connects them. If an upstream already provides the same media type, it is not created again. When you switch packs, model-file parameters return to the new pack's defaults so you do not carry the previous UNET, text encoder, or VAE into another family.

## Nodes

| Node | Purpose | Set in the right panel |
|------|---------|------------------------|
| **Input** | Provides an image, video, audio, text, or a person from the character library | Media can be uploaded or picked from the asset library; an image input can also take a character sheet or a specific view directly from the character library and produce an independent image variable. Text is written directly. A character input selects a person and an on-camera view separately and does not appear in the image input's upload/asset library. Every node has an output variable name |
| **Function** | Runs a workflow pack or calls a cloud model | Menu item, group, workflow pack (or model), pack parameters, prompt, and input slots. When the pack declares Turbo / LoRA, an acceleration switch appears. Avatar and motion transfer do not ask for a duration: avatar follows the upstream audio, and motion transfer follows the reference video; when the single-segment limit is exceeded they split automatically and the next segment starts from the previous segment's last frame. Motion transfer can use "model-generated" or "original audio from the reference video". Both can mix background music from the music library. A visual-analysis pack outputs text and writes it to the node's variable |
| **Speech** | Text-to-speech, speech-to-text, or voice conversion | Service, voice or recognition language, and output format. Liber Speech also lets you choose a reading language. Speech-to-text and voice conversion accept audio or video; voice conversion can also upload an SRT, separate background audio, and burn in subtitles. When the service is left empty, the first enabled speech service with a matching capability is used |
| **Concat** | Combines multiple images into one, or joins multiple videos / audio clips in order; runs locally and does not go through a provider | Order follows the connections; you can move items up or down in the panel. Image Concat supports horizontal, vertical, and grid layouts, with column count, gap, and gap color |

An image input can "Edit image". Exporting creates a new version, and you can switch back to an older version at any time (including its mask):

- **Markup**: brush strokes are baked into the new image.
- **Mask**: white areas are repainted, black areas are kept, for inpainting packs. When preflight reports a missing mask, export it here.
- **Crop**: free ratio, or 1:1, 4:3, 3:2, 16:9, 9:16. Only the base image is cropped.
- **Depth conversion**: sends the current base image to an enabled Liber Depth service and produces a depth map. If the local depth plugin is not installed or not enabled, and there is no enabled Liber Depth provider, this button is disabled.

Switching to another image clears the version list; the new image becomes "Original".

### Character input image rules

The camera view selected on a character input node determines what downstream nodes actually receive:

- **16:9 character sheet** or **9:16 four-grid**: downstream receives the entire sheet as one image slot. It is not automatically replaced with the split front/side/back views. Reference it as `<Picture 1>` only.
- **Facial close-up / full-body front / side / back**: for image-to-video, the selected view goes first and the remaining full-body views fill the available image slots. For motion transfer with three image slots, it always sends **front, side, and back** full-body images, not just the selected one; they map to `<Picture 1>`, `<Picture 2>`, and `<Picture 3>`.
- Motion transfer needs the split front/side/back images. If a character only has a whole sheet and was uploaded without auto-split, choose the 16:9 sheet or 9:16 four-grid option; otherwise the default three-view mode has no single-view images.

## Director

The Director on the left side of the canvas is a conversational assistant. It reuses the canvas nodes and resources and can also modify the canvas directly. The backend handles conversations and model calls; canvas edits run in the browser, so every change can be undone with Ctrl+Z. Closing the page stops the current conversation, but the history remains in the session.

### Panel

- By default it sits on the left, below the "Exit" button. Drag the title bar to move it; the position is remembered locally.
- Click the collapse button in the top-right to turn it into a narrow bar at the bottom-left. Click the input box or the expand button to return to the expanded state.
- Click the session name at the top to open the session list: switch historical conversations, create a conversation, or delete a conversation. Double-click the session name to rename it directly; Enter saves, Esc cancels. Each canvas stores its conversations separately.

### Model

The "Model" button below the input box lists conversation-enabled models from enabled providers. The default is "Follow system default", which reads the default LLM from "System Settings"; open it to choose another model, and the current conversation remembers the choice. Models marked "Vision" can view images directly; models marked "Tools" use native tool calls; without "Tools", the assistant falls back to a text protocol and can still edit the canvas, with the format constrained by the system prompt.

### Attachments and resources

The `+` below the input box opens the attachment menu:

- Upload images, videos, scripts/text, and audio separately. Files are archived as hidden assets and do not appear in the asset library list.
- "Choose from asset library" lets you pick existing files.
- Attachments are sent to the model with the message by default; images/videos can be switched to "Node only", which passes only the `asset_id` to the assistant for canvas nodes and does not send the media content. Attachments sent to the model also keep their `asset_id`, so nodes can reuse them.
- Images are resized to a long edge of 1568px, videos are sampled evenly, and audio is represented by a single hint that asks the assistant to transcribe it first.
- If you explicitly upload an image or video while the current model has no vision capability, only attachments marked "Send to model" are blocked; you are prompted to switch models, set the attachment to "Node only", or remove the media.

### Referencing canvas nodes

Type `/` or `@` in the input box to list the canvas nodes:

- A node with the green "Config only" marker has no output yet; the assistant sees only its configuration.
- For a node with outputs, the assistant receives a configuration summary, variable name, asset id, and text output.
- Selecting a node inserts a reference in the form `@variable_name`; when sent, it is replaced by a structured node summary.
- References exist first so the Director can **operate on that node**: connect, disconnect, change properties, change inputs, tidy the layout, run, or delete. Only when the model has vision does it also attach the node's images/videos; without vision it skips the media and keeps only the configuration and id, so it can still disconnect or change properties without being blocked by referencing an image.
- If the user wants to discuss the image content itself, switch to a model with vision; explicitly uploaded images/videos still go through visual validation.

### Node context menu

Right-click a canvas node to open a menu at the mouse position:

- "Add to Director" inserts the node into the Director input box as `@variable_name`, the same as typing `@` manually; if the Director is collapsed, it expands automatically.
- "Delete node" is the same as selecting the node and pressing Del; it removes the node together with its connections and goes into the undo stack.

### Function nodes and execution

- When the Director creates a Function node, it first creates a blank node, then reads the actual menu items, available workflows, and default workflow from "Canvas Menu Settings"; only when no suitable menu exists does it look for a specific workflow pack. It never hardcodes a workflow name.
- When applying a menu and upstream nodes already exist, it binds input slots and adds upstream connections automatically; it does not create empty input nodes. `bindings` only decides slot assignment; media dependencies must have direct connections. Text prompts are written directly on the Function node; no empty text input is generated. When a video node references group text, it uses `{{variable_name}}` and does not copy the text.
- Before changing node properties, it can read the node's current data and parameter specification: target, input slots, defaults, ranges, and current `values`. When changing `values`, the entire object is written back so parameters are not lost.
- Execution submits only the current node; upstream nodes are reused by fingerprint by default, so concatenating or generating one node does not rerun the whole chain.
- The execution confirmation card offers "Run current node", "Force run including upstream", "Allow for this session", and "Cancel". Only "Force run including upstream" ignores the upstream cache.

### Skills

There are five built-in skills:

| Skill | Purpose |
|-------|---------|
| `director` | Produces a short video step by step: topic, character, script, storyboard, creative route, keyframes/reference images, video. Asks before each step |
| `canvas-auto` | Builds a canvas automatically: node types, variable names, bindings, prompt style, and execution conventions |
| `skill-creator` | Guides you in turning your own process into a skill |
| `liberastra` | Does not touch the canvas; uses server tools directly for images, video, speech, and transcription |
| `project-info` | Read-only project resources: assets, characters, voices, music, menu items, available/default workflows, and current node parameters |

The skill menu lets you switch the current skill, upload a `SKILL.md` or zip, and manage enable/disable and deletion. Uploaded packs follow the Agent Skills standard: one `SKILL.md` plus optional `references/`, `assets/`, `scripts/`, and arbitrary resource files; file extensions are no longer restricted and scripts are not forbidden. The server only protects against path traversal and limits archive size and file count (8MB per file, 32MB per archive, at most 1000 files). A pack with the same name as a built-in skill is rejected.

Built-in skills are already split into `SKILL.md` + `references/` or `assets/`: the main file keeps only the core flow, and detailed templates and parameters are read on demand to reduce context usage.

### The Director skill's video routes and audio continuity

Choose a creative route before generating storyboard images:

- **A. Storyboard video**: generate keyframes for each shot, then generate video. After choosing A, choose a mode:
  - **A1. Per-shot concatenation (default)**: one `i2v_ref` video node per shot, merged at the end; individual shots can be retried and hard cuts are allowed.
  - **A2. Continuous timeline**: put several shots into one Extender timeline; suited to continuous shots in the same scene, and the whole timeline is rerun rather than one shot.
- **B. Whole-reference video**: generate one storyboard reference image per shot and split internally according to the single-segment limit; each segment is concatenated into one 1×N reference image. Up to 15 seconds uses "Reference Image to Video (Single Segment)"; over 15 seconds uses "Continuous Generation (Long)". The focus is continuity of motion, light, and audio.

A1 audio continuity:

- **Model native**: no extra processing, the default.
- **Previous shot tail**: from shot 2 onward, add an Audio Extract node (`audio_extract`, `tail`, 2–15 seconds), connect the previous shot video to it, and connect its audio output to the current shot's `ref_audio`. The first shot has no reference. The whole chain is visible, editable, and can be rerun on its own.
- **Whole-film ambience bed**: add an audio input node and connect it to every shot's `ref_audio`. H3 treats it as a reference, not a time-aligned slice; align it manually if per-shot precision matters.
- The video concat node's `audioFadeMs` controls a short fade at each segment's audio boundaries (0–200ms, default 60).

A2/B Extender audio: `audio_context_length` defaults to 0; higher values carry more audio from the previous segment. P1 adds optional `ref_audio`. A2/B do not expose A1's per-shot three-way choice.

The route decides the node type; the user no longer chooses "image-to-video / reference video". Workflows and models are resolved from the current canvas menu configuration; to change the target, use the dropdown in the node property panel. The Director does not create or modify workflow packs.

- A1 uses `i2v_ref` multi-reference images: the current keyframe, character three-view, face, and scene can be passed at the same time; `<Picture N>` is numbered in the order of the slots actually filled. Audio references come from the canvas audio nodes described above.
- A single video node's `length` follows `duration_limits`: `ceil(seconds × fps)`, then snap up to `align_base × k + align_offset`. For H3, 10 seconds is 243 frames, not 240 or 241.
- A2 creates only one Extender node, with no per-shot video or concat node; if reference slots run out, reduce keyframes first and then use per-segment 1×N composite images.
- When B is no longer than 15 seconds, one "Reference Image to Video (Single Segment)" node is used; when it is longer than 15 seconds, use the Extender path under "Continuous Generation (Long)". A 60-second video defaults to 4 segments of no more than 15 seconds each, keeping motion context between segments instead of splitting into multiple independent videos and concatenating them.
- Menu mapping: `minimax_h3_i2v` keeps strict first-frame/optional last-frame; `minimax_h3_i2v_ref` serves both "Reference Image to Video (Single Segment)" and A1; `minimax_h3_extender` serves "Continuous Generation (Long)", A2, and B long video.
- Each step still presents a plan first and waits for confirmation; after the nodes are created, the canvas can be tidied automatically, and the order of storyboard video and concat nodes is checked afterwards.

### Permissions and confirmation

- Adding nodes, changing nodes, connecting, disconnecting, and tidying the layout: executed directly and added to the undo stack.
- High-risk operations are intercepted by the safety router: deleting nodes, submitting generation jobs, writing skill files, and running skill scripts. The confirmation card lists the operation and risk and offers "Confirm", "Allow for this session", and "Cancel".
- "Allow for this session" remembers the tool only for the current session; subsequent operations of the same kind no longer prompt. Refreshing or switching sessions restores the default.
- Execution confirmation cards state whether it is a "normal run (prefer cache reuse)" or a "forced run (ignore cache)" and list the node ids.
- Skill scripts run with the permissions of the LiberAstra backend process, with no OS-level sandbox; only scripts inside the skill pack's `scripts/` directory can run, and output is truncated and time-limited. The first run and later runs that have not been auto-allowed require confirmation.
- Each step of the Director skill: the assistant presents a plan first and proceeds only after your confirmation.
- A single turn has at most 25 steps; beyond that it stops and waits for you to check.

### Image Concat node

The "Concat" section of the add-node menu includes "Image Concat". Connect two or more images and choose horizontal, vertical, or grid on the right:

- Horizontal unifies height; vertical unifies width; grid unifies height to the shortest image and packs rows tightly, centered.
- The default gap is 4px, white; you can change the gap and color. The grid unifies height to the shortest image among all inputs and packs tightly, avoiding large empty areas when aspect ratios differ.
- The grid is filled row by row. In the Director's reference-image mode, when only first frames are generated it is one row of N images; in first/last-frame mode it first connects all first frames in the group, then all last frames, producing 2 rows × N columns, where each column is one shot's first and last frames.
- The output is PNG. Like video and audio concat, it first becomes a canvas intermediate result and enters the asset list only after "Save to Assets".

## Variables and prompts

Every node has an output variable name, defaulting to the type plus a number (for example `output_image_1`), and it can be changed. If it collides with another node, the input box turns red.

- Text variables: write `{{variable_name}}` in a Function node prompt or Speech node text, or type `/` to insert from a connected node. At execution it is replaced by text input, speech-to-text, or visual-analysis text. A downstream node must be connected to the node that produces the text so the text is written into the variable first. Referencing a variable that does not exist fails.
- Media tags: `/` inserts tags such as `<Picture 1>`, `<Video 1>`, and `<Audio 1>`, which are passed to the workflow as-is. The motion-transfer pack uses `<Picture 1>` for the person image and `<Video 1>` for the reference video.
- Input slots: a Function node lists one row per media parameter in the pack, and the dropdown binds the variable of a connected node. `bindings` only decides how multiple upstream nodes fill slots; the variable source must be an upstream node directly connected to this node, and binding without a connection is rejected by preflight. Without a binding, slots are matched automatically by media type and connection order. A mask enters only slots whose name or description contains "mask"; the next image in multi-image editing is still matched as a normal image.

Function nodes with a prompt slot use the same **PromptField** as the feature pages: original / optimized, scene preset, ✨, and "Use optimized prompt". When checked, execution uses the optimized draft and then replaces `{{variable_name}}`. ✨ uses the default LLM from "System Settings". The canvas chooses the function template based on the current workflow pack's capability: text-to-image packs use `t2i`, image-to-image packs use `i2i`, image-enhance packs use `upscale`, image-to-video packs use `i2v`, and text-to-video packs use `t2v`. Packs without a prompt slot (such as SeedVR2 image/video enhance) do not show a prompt box. The template text is edited under "Settings → Prompt Templates".

## Execution and results

Before execution it checks: no menu item or workflow pack selected, required media not connected, inpainting missing a mask, an empty prompt or text, or no media file selected. Nodes with problems flash with a red border, the notification shows the first reason, and nothing is submitted.

| Action | Result |
|--------|--------|
| "Run selected" in the top-right | Select one or more nodes first. Selected nodes run again; if upstream parameters and media are unchanged, the last successful result is reused |
| "Run" in the top-right | No node is selected. After confirmation the whole canvas reruns and nothing is reused |
| "Rerun this node" on the right | Reruns only the current node; if upstream parameters and media are unchanged, the last successful result is reused |
| "Force run including upstream" on the right | Reruns the current node and all its upstream nodes, ignoring the cache |
| "Retry" on a failed card | Reruns only that node; if upstream is unchanged, it reuses |

Reuse is based on a fingerprint: workflow pack, resolved parameters and prompt, and upstream assets. Avatar and motion transfer also include the audio source, background music, and volume; durations the user previously entered do not participate. On a hit with a previous success, the preview badge shows "Reused".

When one branch fails, its downstream nodes are skipped because the upstream did not succeed, while other branches continue. After refreshing the page, nodes still queued or running keep showing progress. These jobs also appear in "Jobs" and can be canceled or retried. While running, "Run" in the top-right of the canvas turns into a red "Stop"; clicking it and confirming cancels the current orchestration, stops subsequent nodes, and sends an interrupt request to ComfyUI. Clicking the main button again while a feature page is generating also opens an interrupt confirmation; the backend job and the ComfyUI job stop together.

Images, videos, and audio produced by Function, Speech, and Concat nodes first become canvas intermediate results and are not listed in the asset library by default. Click the save icon in the top-right of the preview, "Save to Assets", and they become visible in Assets; the node is marked "Saved". Opening "Include canvas intermediates" in the asset library shows these unpublished files and inpainting masks. Files uploaded directly through input nodes, and new images exported from markup or crop, become normal assets. Deleting a canvas does not affect outputs already saved to Assets.

---

Related: [Settings → Workflow Packs](/guides/settings#workflow-packs); [Image](/guides/image) / [Video](/guides/video) / [Speech](/guides/speech); [Tools](/guides/tools).
