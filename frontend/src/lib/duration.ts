/** 秒↔帧换算的唯一前端实现：与后端 media/timeline.py 保持 ceil + 对齐规则。 */

export interface FrameAlign {
  align_base?: number;
  align_offset?: number;
}

/** 把帧数向上吸附到 align_base * k + align_offset；无对齐规则时向上取整。 */
export function snapFramesCeil(frames: number, align?: FrameAlign | null): number {
  const base = align?.align_base ?? 0;
  if (!base) return Math.max(1, Math.ceil(frames));
  const offset = align?.align_offset ?? 0;
  const k = Math.max(0, Math.ceil((frames - offset) / base));
  return base * k + offset;
}

export function secondsToFrames(seconds: number, fps: number, align?: FrameAlign | null): number {
  return snapFramesCeil(Math.max(0, seconds) * fps, align);
}
