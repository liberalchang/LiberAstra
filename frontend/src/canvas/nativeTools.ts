import type { CanvasMenuItem } from "@/api/client";

export type NativeToolId = "image_concat" | "video_concat" | "audio_concat";

export interface NativeTool {
  id: NativeToolId;
  title: string;
  mediaKind: "image" | "video" | "audio";
  subCapability: string;
  page: string;
  description: string;
}

export const NATIVE_TOOLS: NativeTool[] = [
  {
    id: "image_concat",
    title: "图片拼接",
    mediaKind: "image",
    subCapability: "tool_image_concat",
    page: "/tools/image-concat",
    description: "多张图片横排、竖排或网格拼接",
  },
  {
    id: "video_concat",
    title: "视频拼接",
    mediaKind: "video",
    subCapability: "tool_video_concat",
    page: "/tools/video-concat",
    description: "按顺序拼接多段视频",
  },
  {
    id: "audio_concat",
    title: "音频拼接",
    mediaKind: "audio",
    subCapability: "tool_audio_concat",
    page: "/tools/audio-concat",
    description: "按顺序拼接多段音频",
  },
];

export function toolForMenu(item: CanvasMenuItem): NativeTool | undefined {
  const target = item.default_target?.target_id;
  return (
    NATIVE_TOOLS.find((tool) => tool.id === target) ??
    NATIVE_TOOLS.find((tool) => tool.subCapability === item.sub_capability)
  );
}

export function toolById(id: string): NativeTool | undefined {
  return NATIVE_TOOLS.find((tool) => tool.id === id);
}
