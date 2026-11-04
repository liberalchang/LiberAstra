/** 导演台 @ 引用：从画布节点生成可引用的选项和结构化 ref。 */
import type { AgentRef } from "@/api/client";
import {
  nodeOutputKind,
  type CanvasFlowNode,
  type FunctionNodeData,
  type InputNodeData,
  type MediaKind,
  type SpeechNodeData,
} from "@/canvas/types";

export type RefStatus = "output" | "config";

export interface RefOption {
  nodeId: string;
  handle: string;
  title: string;
  kind: MediaKind;
  status: RefStatus;
  preview: string;
}

function nodeTitle(node: CanvasFlowNode): string {
  const data = node.data;
  if (data.kind === "function") {
    const f = data as FunctionNodeData;
    return f.presetTitle || f.pack || "功能节点";
  }
  if (data.kind === "concat") {
    return data.mediaKind === "image"
      ? "图片拼接"
      : data.mediaKind === "audio"
        ? "音频拼接"
        : "视频拼接";
  }
  if (data.kind === "speech") {
    if (data.mode === "tts") return "文字转语音";
    if (data.mode === "vc") return "音色替换";
    return "语音转文字";
  }
  const input = data as InputNodeData;
  const titles: Record<string, string> = {
    image: "图片输入",
    video: "视频输入",
    audio: "音频输入",
    text: "文本输入",
    character: "角色输入",
  };
  return titles[input.mediaKind] ?? "输入";
}

export function nodeHandle(node: CanvasFlowNode): string {
  const name = (node.data as { varName?: string }).varName;
  return name?.trim() ? name : `节点#${node.id.slice(-4)}`;
}

export function nodeHasOutput(node: CanvasFlowNode): boolean {
  if (node.data.run.assetIds.length > 0) return true;
  if (node.data.kind === "input" && node.data.mediaKind === "text") {
    return Boolean(node.data.text?.trim());
  }
  return false;
}

export function collectRefOptions(nodes: CanvasFlowNode[]): RefOption[] {
  return nodes.map((node) => {
    const kind = nodeOutputKind(node) ?? "text";
    const status: RefStatus = nodeHasOutput(node) ? "output" : "config";
    const data = node.data as { text?: string; prompt?: string; characterName?: string };
    const preview =
      status === "output"
        ? `已有产出 · ${data.text?.slice(0, 40) || (data.prompt ?? "").slice(0, 40) || "媒体"}`
        : "仅引用配置（还没有产出）";
    return {
      nodeId: node.id,
      handle: nodeHandle(node),
      title: nodeTitle(node),
      kind,
      status,
      preview,
    };
  });
}

export function refForNode(node: CanvasFlowNode): AgentRef {
  const data = node.data;
  const kind = nodeOutputKind(node) ?? "text";
  const assetIds = data.run.assetIds;
  const text =
    data.kind === "input" && data.mediaKind === "text"
      ? (data.text ?? "").slice(0, 20_000)
      : undefined;
  return {
    node_id: node.id,
    var_name: nodeHandle(node),
    title: nodeTitle(node),
    kind,
    config: summarize(node),
    assets: assetIds.map((assetId) => ({ asset_id: assetId, kind })),
    asset_ids: assetIds,
    text,
  };
}

function summarize(node: CanvasFlowNode): Record<string, unknown> {
  const data = node.data;
  if (data.kind === "function") {
    return {
      pack: data.pack,
      subCapability: data.subCapability,
      prompt: data.prompt.slice(0, 500),
      values: data.values,
      bindings: data.bindings,
    };
  }
  if (data.kind === "input") {
    if (data.mediaKind === "character") {
      return { characterId: data.characterId, characterName: data.characterName };
    }
    if (data.mediaKind === "text") return { text: (data.text ?? "").slice(0, 500) };
    return { assetId: data.assetId, mediaKind: data.mediaKind };
  }
  if (data.kind === "concat") {
    return {
      mediaKind: data.mediaKind,
      order: data.order,
      layout: data.layout,
      columns: data.columns,
      gap: data.gap,
    };
  }
  const speech = data as SpeechNodeData;
  return {
    mode: speech.mode,
    text: speech.text?.slice(0, 500),
    voice: speech.voice,
    model: speech.model,
  };
}

/** 把输入框里的 @handle 换成后端引用，显式选过的也合并进来。 */
export function resolveRefs(
  text: string,
  options: RefOption[],
  nodes: CanvasFlowNode[],
  explicit: AgentRef[],
): AgentRef[] {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const refs: AgentRef[] = [...explicit];
  const seen = new Set(explicit.map((ref) => ref.node_id));
  for (const option of options) {
    if (!text.includes(`@${option.handle}`)) continue;
    if (seen.has(option.nodeId)) continue;
    const node = byId.get(option.nodeId);
    if (!node) continue;
    refs.push(refForNode(node));
    seen.add(option.nodeId);
  }
  return refs;
}

export function refHasMedia(ref: AgentRef): boolean {
  return (ref.assets ?? []).some(
    (asset) => asset.kind === "image" || asset.kind === "video",
  );
}
