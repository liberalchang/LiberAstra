---
title: Speech
---

# Speech

Text-to-speech, speech-to-text, Voice Conversion, Voice Library, and Music Library.

The Speech group in the sidebar has three pages: Text to Speech, Speech to Text, and Voice Conversion. Voice Library and Music Library live under Resources. Speech is a separate provider and does not run inside the LiberAstra process. Install and enable local Liber Speech from Settings → Plugins; if it already runs on another machine, enter its address under Service Providers. See [Works & Tasks → Plugins](/en/guides/works#plugins).

## Text to Speech

The controls depend on the service type:

| Voice service | How to choose a voice | Preview |
| --- | --- | --- |
| Local TTS (`edge_tts`) | The service's voice list, for example `zh-CN-XiaoxiaoNeural` | Yes |
| API TTS (OpenAI-compatible) | The service's voice list, for example `alloy` | Yes |
| Liber Speech | Voice Library or "Use default voice…", plus a language | No. Cloned voices play the reference audio from the Voice Library directly |
| ComfyUI speech workflow | Workflow pack parameters | No |

Preview appears in Text to Speech, Digital Human, Quick Create, and Custom Assets. The input defaults to "你好,这是一段试听语音!" and you can replace it with another short sentence (up to 200 characters). Click the speaker to synthesize and play with the current voice on the spot; it does not enter the job queue or get saved as an asset.

Liber Speech models are chosen in Settings → System Settings → Speech synthesis (Liber Speech). The default text-to-speech model is `multilingual_v3` (Chatterbox-Multilingual V3). Function pages can also select a specific model; leave it empty to use System Settings. The model list comes from enabled Liber Speech providers and is grouped by model family. The language dropdown follows the current text-to-speech model: multilingual models list 23 languages, and single-language packs keep only their own. When you pick a Voice Library entry, the reference audio is used to clone the voice, and the language only sets `language_id`. "Use default voice…" sends no reference audio. The reading language only affects pronunciation; it does not translate the text. Turbo and Nano are English-only, and clone reference audio must be longer than 5 seconds.

## Speech to Text

Upload audio or video (or click "Choose from library" to pick an existing file), then choose the recognition service, recognition model, and language. The language can be automatic, `zh`, `en`, and so on; for other languages choose Custom and enter the code. Leave the model empty to use the speech-to-text model in Settings → System Settings → Speech synthesis. For OpenAI-compatible services, an empty model uses the service's own default (for example `whisper-1`). Output uses the first available format among txt, json, srt, and vtt.

## Voice Conversion

Upload audio or video, choose a Voice Library voice that has reference audio, keep the speaking timeline unchanged, and replace only the timbre. Outputs audio (mp3 or wav) and srt / vtt subtitles; for video input you can also replace the audio track or burn in subtitles.

- Subtitles: automatic recognition by default; you can also upload an srt to skip recognition. Ranges not covered by subtitles keep the original audio, and the job result records the coverage.
- Separate background audio: split vocals and accompaniment, convert only the vocals, then mix them back. The toggle is disabled when the speech service does not have Demucs installed.
- Video input: you can burn in subtitles and adjust font size and color; size 0 means automatic based on video height.
- Limits: source material must be under 200 MB / 30 minutes; multiple speakers are all converted to the same target voice.
- Model: Chatterbox VC by default; change the default in System Settings, or choose Seed-VC on the page.

The "Voice Conversion" node in the canvas shares the same jobs as this page. The node accepts audio or video and recognizes subtitles automatically by default; the inspector lets you upload an srt, enable burn-in, and adjust font size and color. Audio input produces audio; video input produces video (with audio and subtitles as side outputs). The "Voice Conversion" entry in the quick menu is controlled by Canvas Menu Settings; you can rename it, disable it, or change its binding.

## Voice Library

Sidebar Resources → Voice Library. Local clone: upload reference audio + reference text and leave `voice_id` empty. Fill `voice_id` only when a cloud cloning service returns an ID.

## Music Library

Sidebar Resources → Music Library. Upload, preview, and delete BGM; duplicate names get an automatic suffix. Quick Create and Custom Assets pick background music here.

---

Related: speech models and default services are in [Settings → System Settings](/en/guides/settings#system-settings); canvas speech and Voice Conversion nodes are covered in [Canvas & Director](/en/guides/canvas#nodes).
