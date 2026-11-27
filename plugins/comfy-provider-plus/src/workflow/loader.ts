import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import type { ComfyPrompt, WorkflowNodeBindings } from "../types.js";

function expandUserPath(input: string): string {
  if (input.startsWith("~/") || input === "~") {
    return path.join(os.homedir(), input.slice(2));
  }
  return input;
}

/** 去掉 `_` 前缀文档键，仅保留节点 */
export function stripDocKeys(value: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value)) {
    if (k.startsWith("_")) continue;
    out[k] = v;
  }
  return out;
}

export function isComfyPrompt(value: unknown): value is ComfyPrompt {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const nodes = stripDocKeys(value as Record<string, unknown>);
  const entries = Object.values(nodes);
  if (entries.length === 0) return false;
  return entries.every((node) => {
    if (typeof node !== "object" || node === null) return false;
    const n = node as Record<string, unknown>;
    return typeof n.class_type === "string" && typeof n.inputs === "object" && n.inputs !== null;
  });
}

export async function loadWorkflowTemplate(workflowPath: string): Promise<ComfyPrompt> {
  const resolved = expandUserPath(workflowPath);
  const raw = await fs.readFile(resolved, "utf8");
  const parsed = JSON.parse(raw) as unknown;
  if (!isComfyPrompt(parsed)) {
    throw new Error(`工作流必须是 ComfyUI API Prompt JSON 对象: ${resolved}`);
  }
  return structuredClone(stripDocKeys(parsed as Record<string, unknown>)) as ComfyPrompt;
}

export function loadWorkflowFromObject(workflow: unknown): ComfyPrompt {
  if (!isComfyPrompt(workflow)) {
    throw new Error("工作流必须是 ComfyUI API Prompt JSON 对象");
  }
  return structuredClone(stripDocKeys(workflow as Record<string, unknown>)) as ComfyPrompt;
}

/** 校验配置中的 nodeId 均存在于模板（动态 LoadImage 除外） */
export function assertBindingsExist(
  workflow: ComfyPrompt,
  bindings: WorkflowNodeBindings,
  options?: { allowMissingImageLoads?: boolean },
): void {
  const requiredIds = new Set<string>();
  const collect = (nodeId: string) => requiredIds.add(nodeId);
  collect(bindings.prompt.nodeId);
  collect(bindings.negativePrompt.nodeId);
  collect(bindings.seed.nodeId);
  collect(bindings.steps.nodeId);
  collect(bindings.cfg.nodeId);
  collect(bindings.unetName.nodeId);
  collect(bindings.clipName.nodeId);
  collect(bindings.vaeName.nodeId);
  collect(bindings.lora.nodeId);
  collect(bindings.lora.upstreamModelNodeId);
  for (const d of bindings.lora.downstreamModelBindings) collect(d.nodeId);
  collect(bindings.output.nodeId);
  if (bindings.resolution) collect(bindings.resolution.nodeId);
  if (bindings.imageEncoder) collect(bindings.imageEncoder.nodeId);
  if (bindings.emptyLatent) {
    collect(bindings.emptyLatent.width.nodeId);
    collect(bindings.emptyLatent.height.nodeId);
  }
  if (bindings.kSamplerLatent) collect(bindings.kSamplerLatent.nodeId);

  const missing = [...requiredIds].filter((id) => !workflow[id]);
  if (missing.length > 0 && !options?.allowMissingImageLoads) {
    throw new Error(`工作流缺少配置声明的节点: ${missing.join(", ")}`);
  }
}
