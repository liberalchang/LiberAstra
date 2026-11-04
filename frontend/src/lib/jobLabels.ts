/** 任务类型到 i18n key 的公共映射。 */

export const JOB_KIND_LABEL: Record<string, string> = {
  "image.generate": "nav.imageGen",
  "image.edit": "nav.imageEdit",
  "video.quick": "nav.videoQuick",
  "video.i2v": "nav.i2v",
  "video.avatar": "nav.avatar",
  "video.motion": "nav.motion",
  "video.assets": "nav.videoAssets",
  "video.assets.script": "jobs.script",
  "canvas.node": "jobs.node",
  "media.concat": "jobs.concat",
  "tts.synthesize": "nav.tts",
  "asr.transcribe": "nav.asr",
  "vc.convert": "nav.vc",
  "character.generate": "nav.characters",
  "prompt.optimize": "nav.prompts",
  "llm.chat": "jobs.chat",
};

export function jobKindLabel(kind: string, t: (key: string) => string): string {
  const key = JOB_KIND_LABEL[kind];
  return key ? t(key) : kind;
}
