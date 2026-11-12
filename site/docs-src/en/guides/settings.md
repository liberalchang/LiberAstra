---
title: Settings
---

# Settings

Service Providers, Workflow Packs, Prompt Templates, and System Settings.

## Service Providers

Settings → Service Providers: name, type, address, capabilities, key, and enabled. Use `http://` for the address (writing `https://` locally causes a protocol error). The API key for ComfyUI can be left empty. If speech sets `LIBER_SPEECH_API_KEY`, enter the same key in the provider.

The search box on the left filters only provider names and descriptions; it is not a login box. Open an entry to fill in the API address and key. The type name for Liber Depth is "Liber Depth Depth Map", the default address is `http://127.0.0.1:5556`, and its capability is depth map. Enabling the local plugin creates this entry automatically; to connect to another depth service on the LAN, change the address here instead of starting a remote process from the Plugins page.

The image / video / speech / recognition service dropdowns on each page list only enabled entries with matching capabilities (such as `image`, `video`, `tts`, `asr`). The Depth Map page lists only enabled Liber Depth providers.

## Workflow Packs

Settings → Workflow Packs can import:

1. **Full LiberAstra pack** (with `workflow` + `inputs` and other fields)
2. **ComfyUI API Format** (`Save (API Format)`)
3. **ComfyUI canvas JSON** (with `nodes` / `links`, optionally with subgraphs): after importing a file or pasting it, click "Convert canvas JSON" to convert it to API Format and **heuristically generate** capabilities, parameter mappings, output nodes, and optional `accel` / `fps` drafts — **verify the node / field mappings before importing**.

| Location | Description |
| --- | --- |
| `backend/workflows/` | Built-in (shipped with the release) |
| `backend/data/workflows/` | User packs; same-name packs override built-ins |

Capability vocabulary: `t2i` text-to-image, `i2i` image-to-image, `upscale` image enhance, `v2v` video enhance, `t2v` text-to-video (Quick Create · Generate Video), `i2v` image-to-video / asset animation, `avatar` digital human, `motion` motion transfer, `tts` speech, `analysis` analyze media and write the script. The three concat tools under Tools are local native tools, not workflow packs, and do not appear here.

Optional top-level `accel`: the frontend shows a Turbo toggle and submits `__accel`. The pack dropdown first shows the capability name and a one-line description; uncensored packs are marked "Uncensored". The lightbulb on the right shows the full description from the manifest.

Function nodes on the canvas choose packs by their "Group". Groups are maintained on this page under the "Canvas Groups" tab: assign packs to groups, rename them, or delete them. See [Canvas → Workflow Groups](/en/guides/canvas#workflow-groups).

## Prompt Templates

Settings → Prompt Templates. When you click ✨ to optimize, the system prompt sent to the default LLM is assembled from two parts: the **function template** explains what this task is doing, and the **scene preset** adds a layer of style after it. Built-in entries ship with the release; user files store only overrides and custom entries. If the saved content matches the built-in content, it stays "default" and does not show "Customized"; only actual edits show that. Click "Reset to default" to remove the override and return to the text shipped with the release. The next optimization uses the new content immediately after saving.

Tabs and buttons:

- **Function Templates** / **Scene Presets**: select an entry on the left and edit its content on the right; the save button is disabled when nothing has changed.
- **New**: enter an ID. The ID cannot be changed after saving. Saving with the same ID as a built-in entry only creates a custom override when the content differs.
- **Import**: paste JSON. The structure is `{ "tasks": { "some-id": { "name", "system", "capabilities" } } }` or `{ "scenes": { "some-id": { "name", "append" } } }`. A same-name entry only becomes custom when its content differs from the built-in.
- **Delete**: user-created "My Templates / My Presets" can be deleted; built-in entries cannot be deleted, only reset to default.
- **Export**: download the current merged result as `prompts-catalog.json`.

You can also edit `data/prompts/tasks.yaml` and `scenes.yaml` directly. Built-in templates ship with the app package: the source is in `backend/prompts/`, and in the installer it is under `liberastra/prompts/`. `data/prompts/` holds only user overrides and custom entries; full copies left over from older versions are compared with the built-ins, and content identical to the old defaults is cleaned up automatically and not mistakenly marked as custom. Container deployments do not need to copy built-in files manually. After an upgrade, if an old copy differs from the new built-in content, it is kept and marked "Customized"; click "Reset to default" to adopt the new built-in content.

### Function Templates

Each page and the canvas pass a fixed template ID to the optimization endpoint. The table below lists the built-in IDs. The "Applies to" field on a function template is a comma-separated list of capabilities, used to show which capability it corresponds to on this page; when empty, this page does not list that capability.

| ID | Name | Used by |
| --- | --- | --- |
| `t2i` | Text to Image | Text to Image page; canvas function nodes with capability `t2i` |
| `i2i` | Image to Image / Inpainting | Image to Image & Edit |
| `upscale` | Image Enhance | Tools → Image Enhance; canvas `upscale` packs |
| `i2v` | Image to Video | Image to Video, Custom Assets animation prompts; canvas `i2v` packs |
| `t2v` | Text to Video | Canvas `t2v` packs |
| `quick_visual` | Quick Create · Visual Prompt | Quick Create visual prompts |
| `motion` | Motion Transfer | Motion Transfer page |
| `quick_topic` | Quick Create · Topic Expansion | Quick Create topics |
| `assets_topic` | Custom Assets · Topic Expansion | Custom Assets topics |
| `character_sheet` | Characters · Character Appearance (legacy) | Kept for legacy callers; the character page now uses the two templates below |
| `character_appearance` | Characters · Appearance Description | ✨ on the Characters appearance description |
| `character_edit` | Characters · Single-View Edit | ✨ on the Characters edit prompt |

Canvas function nodes use the template with the same name as the selected pack's capability. When there is no matching template, they fall back to `t2i`. Visual analysis does not use this prompt field; the analysis angle is written in the pack parameters. Characters use `character_appearance` for the appearance description and `character_edit` for the edit prompt, and do not share `t2i` with the Text to Image page. The `upscale` template only applies to custom upscale packs that declare a prompt slot; the built-in `upscale_basic` and SeedVR2 image enhance have no prompt field.

### Scene Presets

A scene only appends style; it does not replace the function template above. The PromptField scene dropdown comes from here. There are nine built-in entries:

| ID | Name | Tendency |
| --- | --- | --- |
| `auto` | Auto / General | Does not force poster, portrait, or other fixed scenes; still follows the function template |
| `photo` | Photography & Portraits | Camera body and film texture, focal length, candid framing |
| `poster` | Posters & Layout | Main title, info bar, limited palette; in-image text given word by word |
| `illustration` | Illustration & Art | Line work, coloring, material |
| `product` | Product & E-commerce | Hero image, material close-up, selling-point copy |
| `character` | Character & Persona | Standing art, outfit, expression |
| `infographic` | Infographic & Visualization | Numbered sections and short labels |
| `architecture` | Architecture & Space | Material, light and shadow, perspective |
| `cinematic_video` | Cinematic Storyboard Video | Shot size, camera movement, temporal action |

Choosing "Auto" still includes the `auto` overlay text, which explicitly says not to force any particular visual type.

### PromptField on Each Page

Text to Image, Image to Image, Image to Video, Motion Transfer, Quick Create, Custom Assets, Characters, and canvas function nodes with prompt slots all use the same prompt entry: switch between the original input and the optimized draft, scene presets, ✨, and "Use optimized prompt". The original draft, optimized draft, and toggle are stored in the local browser and survive a refresh.

On Image Edit, Image-to-Video/Motion Transfer/Digital Human, and the character edit prompt, typing `/` inserts images already filled on the current page. The inserted text is the workflow pack's registered mention (such as `image 1` or `原图`); a hand-written `<Picture 1>` is also converted for the current pack on submit. The resource menu is grouped by image/video/audio/text variable and only shows what the page already has.

SeedVR2 image/video enhance and regular upscale packs have no prompt slot and do not show this field.

✨ submits the `prompt.optimize` job: `POST /api/v1/prompts/optimize` returns a job ID and the frontend polls progress. The server streams from the default LLM in System Settings. After a refresh, the job ID is enough to keep showing completion. If a workflow pack name is included during optimization, the pack's capability, description, and model family are passed to the LLM as well. `?wait=true` waits synchronously. The legacy path `/api/v1/images/optimize-prompt` still returns synchronously.

API: `GET /api/v1/prompts` lists the merged templates; `PUT /api/v1/prompts/tasks/{id}` and `PUT /api/v1/prompts/scenes/{id}` save overrides; the corresponding `DELETE` resets to default; `POST /api/v1/prompts/import` imports.

## System Settings

Change account password.

**Default LLM (scripts and prompt optimization)**: choose the provider and model used by Quick Create, Custom Assets, each function page, and ✨ on canvas function nodes. Edit the template text in the previous section, "Prompt Templates".

**Depth Map Generation**: choose the default depth provider and model for the Depth Map page and canvas depth generation. When empty, the first enabled Liber Depth and `dpt_swin2_large_384` are used.

**Speech synthesis (Liber Speech)**: choose the text-to-speech model, speech-to-text model, and voice conversion model separately. Text-to-speech defaults to `multilingual_v3` (Chatterbox-Multilingual V3); speech-to-text and voice conversion follow the speech service configuration (`.env`) by default, and you can also specify them here. Text to Speech, Speech to Text, Voice Conversion, Quick Create, Custom Assets, and Digital Human all use these defaults; function pages can still override them.

**Default Character Generation**: shared by Character Library four-view generation, filling, and single-view edits. The image provider list keeps every `image` service and defaults to the first enabled one. Validation depends on the provider type:

- **ComfyUI**: all three workflows are required. The character sheet workflow lists only `t2i` packs and is used for a single view without references; the single-reference workflow is used when there is one anchor image; the multi-reference workflow is used for two or more anchors and for the 16:9 sheet. Defaults are blank, so choose them manually; the frontend no longer fills in `qwen_image_21`.
- **Non-ComfyUI**: choose the provider's character image model. With at least one reference image it uses `edit`; without one it uses `generate`. References beyond the provider's capability are truncated automatically and noted in the job result.
- **Exemption**: four full slots with no edit prompt and compose-only saves do not require configuration; downloads and compose-only saves are also exempt.

When configuration is missing, the character page shows a banner with a **Go to System Settings** link. Change official or uncensored image models here instead of going back to the Characters page.

Runtime settings: ComfyUI wait timeout, synchronous API wait, and LLM timeout; "Serialize services on the same host" is off by default (parallel). When enabled, multiple services on the same host run only one job at a time. Changes take effect on the next job after saving.

**Notifications**: completion, failure, and progress pushes plus the delivery log are covered in [Notifications](/en/guides/notifications).

---

Related: [Canvas → Workflow Groups](/en/guides/canvas#workflow-groups); [Works & Tasks → Plugins](/en/guides/works#plugins); [Image](/en/guides/image) / [Video](/en/guides/video) / [Speech](/en/guides/speech).
