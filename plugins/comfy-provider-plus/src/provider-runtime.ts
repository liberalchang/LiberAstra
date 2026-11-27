import path from "node:path";
import { fileURLToPath } from "node:url";
import { ComfyClient } from "./comfy/client.js";
import { createComfyError, redactSensitive } from "./comfy/errors.js";
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
  signal?: AbortSignal;
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
    // 保留原始 operation（含非字符串），交给 routeOperation 严格校验
    operation: po.operation,
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
  const expanded = configured.replace(/^~\//, `${home}/`);
  const candidates = [expanded, configured, path.join(BUNDLED_WORKFLOWS, bundledName)];
  const fs = await import("node:fs/promises");
  const tried: string[] = [];
  for (const c of candidates) {
    tried.push(c);
    try {
      await fs.access(c);
      return c;
    } catch {
      /* try next */
    }
  }
  throw createComfyError(
    "VALIDATION_FAILED",
    `工作流文件不存在（已尝试 ${tried.length} 个候选路径）`,
    { bundledName },
  );
}

/** 规范化返回 model，避免 comfy-plus/comfy-plus/workflow */
export function normalizeProviderModel(model: string | undefined): string {
  const raw = (model || DEFAULT_COMFY_PLUS_MODEL).trim();
  const prefix = `${PROVIDER_ID}/`;
  if (raw.startsWith(prefix)) return raw;
  if (raw === DEFAULT_COMFY_PLUS_MODEL || !raw.includes("/")) {
    return `${prefix}${raw || DEFAULT_COMFY_PLUS_MODEL}`;
  }
  return raw;
}

export async function generateComfyPlusImage(req: GenerateImageRequestLike): Promise<{
  images: Array<{ buffer: Buffer; mimeType: string; fileName: string }>;
  model: string;
  metadata: Record<string, unknown>;
}> {
  try {
    return await generateComfyPlusImageInner(req);
  } catch (err) {
    if (err && typeof err === "object" && "code" in err) throw err;
    throw createComfyError(
      "EXECUTION_FAILED",
      redactSensitive(err instanceof Error ? err.message : String(err)),
    );
  }
}

async function generateComfyPlusImageInner(req: GenerateImageRequestLike): Promise<{
  images: Array<{ buffer: Buffer; mimeType: string; fileName: string }>;
  model: string;
  metadata: Record<string, unknown>;
}> {
  const pluginRaw = getComfyPlusPluginConfig(req.cfg);
  const config = parseComfyPlusConfig(pluginRaw);
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

  const mode = route.operation === "t2i" ? "t2i" : "edit";
  const client = new ComfyClient({
    baseUrl: config.baseUrl,
    timeoutMs: req.timeoutMs ?? config.timeoutMs,
    pollIntervalMs: config.pollIntervalMs,
    maxUploadBytes: config.maxUploadBytes,
    signal: req.signal,
  });

  client.preflightImages(inputImages);

  let uploadedNames: string[] = [];
  if (route.operation === "edit") {
    const uploaded = await client.uploadImages(inputImages);
    uploadedNames = uploaded.map((u) => u.filename);
  }

  const loraEnabled = overrides.loraEnabled ?? config.defaults.loraEnabled;
  const { workflow: promptGraph, resolvedSeed } = injectWorkflowParams({
    workflow: template,
    bindings,
    defaults: config.defaults,
    overrides,
    prompt: norm.normalizedPrompt,
    uploadedFilenames: uploadedNames,
    loraEnabled,
    mode,
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
  const files = client.extractImages(history, bindings.output.nodeId, bindings.output.outputKey);
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
        seed: resolvedSeed,
        mode,
      }),
      promptAudit: audit,
      outputNodeIds: [...new Set(files.map((f) => f.nodeId))],
    },
  };
}

export function isComfyPlusConfigured(cfg: unknown): boolean {
  try {
    if (!isRecord(cfg)) return false;
    const plugins = cfg.plugins;
    if (!isRecord(plugins)) return false;
    const entries = plugins.entries;
    if (!isRecord(entries)) return false;
    const entry = entries["comfy-plus"];
    if (!isRecord(entry)) return false;
    if (entry.enabled === false) return false;
    const config = entry.config;
    if (!isRecord(config)) return false;
    if (typeof config.baseUrl !== "string" || !config.baseUrl.trim()) return false;
    if (!isRecord(config.workflows)) return false;
    parseComfyPlusConfig(config);
    return true;
  } catch {
    return false;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
