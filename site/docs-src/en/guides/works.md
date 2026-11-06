---
title: Works & Tasks
---

# Works & Tasks

Assets, Characters, Voice Library, Music Library, Plugins, and the Job Center: outputs, sources, and files all stay local.

The Resources group in the sidebar has four pages: Assets, Characters, Voice Library, and Music Library. Plugins live under Settings → Plugins. Jobs live under the Jobs item in the sidebar.

## Resources

### Assets

Successful outputs. You can switch pages while generation runs; the job keeps going. The same browser tab keeps showing progress; after you close the tab, the progress bar is no longer attached, but the job still runs.

Where assets come from:

- Generation results from each function page go straight into the Assets library.
- Image/video/audio concat, Image Enhance, and Video Enhance on the Tools pages put their outputs straight into Assets; no extra save step.
- Function, speech, and concat nodes on the canvas are not listed by default; click "Save to library" in the top-right corner of the node preview to make them appear here. Turn on "Include canvas intermediates" to see these unpublished files and masks.
- Files uploaded directly through input nodes, plus new images exported from markup or crop, become normal assets.

Depth map results carry a depth map marker, and the filename ends with `_depth.png`; for example, `photo.jpg` becomes `photo_depth.png`.

### Characters

Sidebar Resources → Characters. Stores a character's name, appearance description, and one 16:9 four-panel character sheet for image-to-video, Digital Human, and Motion Transfer. See [Video → Characters](/en/guides/video#characters) for generation from a description, uploading a character sheet, automatic splitting, and what each panel is used for.

### Voice Library

Sidebar Resources → Voice Library. Stores the reference audio and reference text for cloned voices; Text to Speech and Voice Conversion pick voices here. See [Speech → Voice Library](/en/guides/speech#voice-library).

### Music Library

Sidebar Resources → Music Library. Upload, preview, and delete BGM; duplicate names get an automatic suffix. Quick Create and Custom Assets pick background music here. See [Speech → Music Library](/en/guides/speech#music-library).

## Plugins

Settings → Plugins manages only local add-on services: Liber Speech (port 5555) and Liber Depth (port 5556). You can search. Cards show an icon, name, and description; open a card to see paths, start/stop, and installation.

When connecting to a speech or depth service that already runs on the LAN, do not install it here. Enter its address under Service Providers.

### Installation and progress

**Installation.** After you click "Install", the toggle becomes a blinking "Installing", and both the card and the details show a progress bar. The stages are: prepare the Python environment, install PyTorch, install the plugin's own dependencies; the depth plugin also downloads its default model. You cannot enable it before installation finishes. On failure, the details show the error and the progress bar disappears.

### Runtime and paths

Speech and depth share one Python environment with PyTorch. When that environment is already detected, a later plugin only adds the packages it is missing and does not install PyTorch again.

| Startup | Path |
| --- | --- |
| Start from `backend` in development | Environment at `%LOCALAPPDATA%\LiberAstra\plugin-runtime`. Models at `backend/data/plugins/<speech or depth>/models` |
| Windows installer | Data directory is `%LOCALAPPDATA%\LiberAstra\data`. Environment at `plugins\runtime` inside it. Models at `plugins\<speech or depth>\models` |

### Docker mode

If a released LiberSpeech installer includes `docker-compose.yml` and `install.ps1`, enabling it uses Docker and does not create the Python environment above. `services/speech` in this repository has no `install.ps1`, so it still uses Python.

### Enable, disable, and uninstall

**Enable and uninstall.** Enabling starts the local process and adds a matching entry under Service Providers (Liber Speech API or Liber Depth). Disabling stops the process and removes that local entry. Uninstalling also stops the process. Docker-based speech runs `docker compose stop` when disabled, not `down`.

### Model downloads

Speech weights are not downloaded during installation; they land in the speech model directory on first synthesis. Depth installation downloads only `dpt_swin2_large_384.pt`; see [Image → Depth Map Generation](/en/guides/image#depth-map-generation) for the other weights.

## Job center

### Progress and retry

Sidebar Jobs. Shows progress and status. "Retry" reuses the old parameters; after changing settings, submit a new job. Function nodes, speech nodes, and concat nodes on the canvas, plus concat (`media.concat`) and Video Enhance (`video.v2v`) jobs from the Tools pages, also appear here.

### Cancel and stop

Switching to another page while a job runs does not interrupt it; return to the Job Center to keep watching progress. To stop it, cancel the job. The canvas "Run" button turns into a red "Stop" while running; click it and confirm to cancel the current orchestration, stop downstream nodes, and send an interrupt request to ComfyUI.

## Related

- [Settings → Workflow Packs](/en/guides/settings#workflow-packs)
- [Settings → System Settings](/en/guides/settings#system-settings)
