# 资源字段

## 资产（list_assets / get_asset）

```json
{
  "id": 12,
  "kind": "image",
  "name": "角色定妆照.png",
  "path": "uploads/abc.png",
  "mime": "image/png",
  "size": 1048576,
  "hidden": false,
  "job_id": "job-uuid",
  "meta": {"source_name": "角色定妆照.png", "size": "1024x1536"},
  "created_at": "2026-11-01T10:00:00+00:00",
  "media": {"width": 1024, "height": 1536}
}
```

- `kind`：`image` / `video` / `audio` / `subtitle` / `text`。
- 默认不返回画布中间结果；需要时 `include_hidden=true`。
- `get_asset(probe_media=true)` 才读取 `media`，列表接口不探测，避免慢。
- `meta.duration_s` 可能是任务处理耗时；媒体时长看 `media.duration_s`。

## 角色（list_characters）

```json
{
  "id": 3,
  "name": "林夏",
  "description": "黑色短发，米色风衣",
  "tags": ["主角"],
  "views": {
    "portrait": "characters/3/portrait.png",
    "turnaround": "characters/3/turnaround.png",
    "front": "characters/3/front.png",
    "side": "characters/3/side.png",
    "back": "characters/3/back.png"
  },
  "voice_record_id": 5,
  "voice_name": "林夏声音",
  "created_at": "2026-11-01T10:00:00+00:00"
}
```

- 角色输入节点用 `characterId` / `characterSlot`；不要把角色图片路径直接塞进图片输入节点，除非用户明确要固定某一视角。

## 音色（list_voices）

```json
{
  "id": 5,
  "name": "林夏声音",
  "provider_id": 3,
  "provider_name": "Liber Speech",
  "voice_id": null,
  "ref_text": "参考音频对应文本",
  "tags": ["女声"],
  "is_default": true,
  "has_ref_audio": true,
  "created_at": "2026-11-01T10:00:00+00:00"
}
```

- 语音节点优先用 `voiceRecordId`；服务商原生音色用 `voice` 或 `model`。
- 数字人、快速创作里的音色也来自这里。

## 音乐（list_music）

```json
{"name": "雨夜.mp3", "size": 3145728, "path": "bgm/雨夜.mp3"}
```

- 功能节点背景音乐写 `bgmPath`，值用 `bgm/<文件名>`；音量写 `bgmVolume`，0–1，默认约 0.2。
- `probe=true` 时返回 `duration_s`。
