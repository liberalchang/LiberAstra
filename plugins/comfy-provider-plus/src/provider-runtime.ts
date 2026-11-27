import path from "node:path";
import { fileURLToPath } from "node:url";
import { ComfyClient } from "./comfy/client.js";
import { createComfyError } from "./comfy/errors.js";
import {
  DEFAULT_COMFY_PLUS_MODEL,
  MAX_INPUT_IMAGES,
  PROVIDER_ID,
} from "./config/defaults.js";
import { getComfyPlusPluginConfig, parseComfyPlusConfig } from "./config/schema.js";
import { normalizePromptSlots } from "./prompt/slot-normalizer.js";
import { routeOperation } from "./router/operation-router.js";
import {
  buildAppliedParamsMetadata,
  injectWorkflowParams,
} from "./workflow/injector.js";
import { assertBindingsExist, loadWorkflowTemplate } from "./workflow/loader.js";
import type {
  InputImage,
  PromptNormalizationAudit,
  ProviderOptionOverrides,
  SlotMapEntry,
} from "./types.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUNDLED_WORKFLOWS = path.resolve(HERE, "../workflows");

export type GenerateImageRequestLike = {
  prompt: string;
  model?: string;
  cfg?: unknown;
  timeoutMs?: number;
  size?: string;
  inputImages?: Array<{
    buffer?: Buffer;
    mimeType?: string;
    fileName?: string;
  }>;
  providerOptions?: Record<string, unknown>;
};

function parseSize(size?: string): { width?: number; height?: number } {
  if (!size) return {};
  const m = /^(\d+)\s*[x×]\s*(\d+)$/i.exec(size.trim());
  if (!m) return {};
  return { width: Number(m[1]), height: Number(m[2]) };
}

function readOverrides(req: GenerateImageRequestLike): ProviderOptionOverrides {
  const po = req.providerOptions ?? {};
  const fromSize = parseSize(req.size);
  const num = (v: unknown): number | undefined =>
    typeof v === "number" && Number.isFinite(v) ? v : undefined;
  const bool = (v: unknown): boolean | undefined =>
    typeof v === "boolean" ? v : undefined;
  const str = (v: unknown): string | undefined =>
    typeof v === "string" ? v : undefined;
  const roles = Array.isArray(po.imageRoles)
    ? po.imageRoles.filter((r): r is string => typeof r === "string")
    : undefined;

  return {
    operation: str(po.operation),
    steps: num(po.steps),
    cfg: num(po.cfg),
    negativePrompt: str(po.negativePrompt),
    seed: num(po.seed),
    loraEnabled: bool(po.loraEnabled),
    loraStrength: num(po.loraStrength),
    loraName: str(po.loraName),
    unetName: str(po.unetName),
    clipName: str(po.clipName),
    vaeName: str(po.vaeName),
    width: num(po.width) ?? fromSize.width,
    height: num(po.height) ?? fromSize.height,
    resolution: num(po.resolution),
    imageRoles: roles,
    imageCount: num(po.imageCount),
  };
}

async function resolveExistingWorkflowPath(
  configured: string,
  bundledName: string,
): Promise<string> {
  const home = process.env.HOME || process.env.USERPROFILE || "";
  const candidates = [
    configured.replace(/^~\//, `${home}/`),
    configured,
    path.join(BUNDLED_WORKFLOWS, bundledName),
  ];
  const fs = await import("node:fs/promises");
  for (const c of candidates) {
    try {
      await fs.access(c);
      return c;
    } catch {
      /* try next */
    }
  }
  return path.join(BUNDLED_WORKFLOWS, bundledName);
}

export async function generateComfyPlusImage(req: GenerateImageRequestLike): Promise<{
  images: Array<{ buffer: Buffer; mimeType: string; fileName: string }>;
  model: string;
  metadata: Record<string, unknown>;
}> {
  const config = parseComfyPlusConfig(getComfyPlusPluginConfig(req.cfg));
  const overrides = readOverrides(req);
  const inputImages: InputImage[] = (req.inputImages ?? []).map((img, i) => {
    if (!img.buffer || !img.mimeType) {
      throw createComfyError("VALIDATION_FAILED", `第 ${i + 1} 张参考图缺少 buffer/mimeType`);
    }
    return {
      buffer: img.buffer,
      mimeType: img.mimeType,
      fileName: img.fileName,
      role: overrides.imageRoles?.[i],
    };
  });

  if (inputImages.length > MAX_INPUT_IMAGES) {
    throw createComfyError(
      "VALIDATION_FAILED",
      `参考图数量 ${inputImages.length} 超过上限 ${MAX_INPUT_IMAGES}，本地拒绝且不发起网络请求`,
    );
  }

  const route = routeOperation({
    config,
    imageCount: inputImages.length,
    requestedOperation: overrides.operation,
  });

  if (route.workflowKey === "colorGrade" || route.workflowKey === "pose") {
    // 门禁已在 router；此处防御
    throw createComfyError("VALIDATION_FAILED", "该操作工作流未验证");
  }

  const norm = normalizePromptSlots({
    prompt: req.prompt,
    actualImageCount: inputImages.length,
    imageRoles: overrides.imageRoles,
  });

  const bundledName =
    route.workflowKey === "t2i" ? "qwen-image-t2i.json" : "qwen-image-edit.json";
  const workflowPath = await resolveExistingWorkflowPath(
    config.workflows[route.workflowKey],
    bundledName,
  );

  const bindings =
    route.workflowKey === "t2i" ? config.nodeBindings.t2i : config.nodeBindings.edit;
  const template = await loadWorkflowTemplate(workflowPath);
  assertBindingsExist(template, bindings);

  const client = new ComfyClient({
    baseUrl: config.baseUrl,
    timeoutMs: req.timeoutMs ?? config.timeoutMs,
    pollIntervalMs: config.pollIntervalMs,
    maxUploadBytes: config.maxUploadBytes,
  });

  // 预检在上传前；T2I 无上传
  client.preflightImages(inputImages);

  let uploadedNames: string[] = [];
  if (route.operation === "edit") {
    const uploaded = await client.uploadImages(inputImages);
    uploadedNames = uploaded.map((u) => u.filename);
  }

  const loraEnabled = overrides.loraEnabled ?? config.defaults.loraEnabled;
  const promptGraph = injectWorkflowParams({
    workflow: template,
    bindings,
    defaults: config.defaults,
    overrides,
    prompt: norm.normalizedPrompt,
    uploadedFilenames: uploadedNames,
    loraEnabled,
    mode: route.operation === "t2i" ? "t2i" : "edit",
  });

  const slotMap: SlotMapEntry[] = uploadedNames.map((comfyFilename, i) => ({
    slot: `image_${i + 1}`,
    sourceName: inputImages[i]?.fileName || `input_${i + 1}`,
    comfyFilename,
    role: inputImages[i]?.role,
  }));

  const audit: PromptNormalizationAudit = {
    originalPrompt: norm.originalPrompt,
    normalizedPrompt: norm.normalizedPrompt,
    slotMap,
    warnings: norm.warnings,
  };

  const promptId = await client.submitPrompt(promptGraph);
  const history = await client.waitForHistory(promptId);
  const files = client.extractImages(history, bindings.output.nodeId);
  if (files.length === 0) {
    throw createComfyError("EXECUTION_FAILED", `工作流 ${promptId} 完成但无图片输出`);
  }

  const images = [];
  for (const file of files) {
    images.push(await client.downloadOutput(file));
  }

  return {
    images,
    model: req.model || DEFAULT_COMFY_PLUS_MODEL,
    metadata: {
      provider: PROVIDER_ID,
      promptId,
      operation: route.operation,
      timeoutMs: req.timeoutMs ?? config.timeoutMs,
      applied: buildAppliedParamsMetadata({
        defaults: config.defaults,
        overrides,
        loraEnabled,
        prompt: norm.normalizedPrompt,
      }),
      promptAudit: audit,
      outputNodeIds: [...new Set(files.map((f) => f.nodeId))],
    },
  };
}

export function isComfyPlusConfigured(cfg: unknown): boolean {
  try {
    const config = parseComfyPlusConfig(getComfyPlusPluginConfig(cfg));
    return Boolean(config.baseUrl && config.workflows.t2i && config.workflows.edit);
  } catch {
    return false;
  }
}
