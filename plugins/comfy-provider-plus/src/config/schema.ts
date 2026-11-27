import {
  DEFAULT_COMFY_PLUS_CONFIG,
  EDIT_NODE_BINDINGS,
  T2I_NODE_BINDINGS,
} from "./defaults.js";
import type { ComfyPlusConfig, WorkflowNodeBindings } from "../types.js";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function readPositiveInt(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : fallback;
}

function readNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function readBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function readBinding(
  value: unknown,
  fallback: { nodeId: string; inputName: string },
): { nodeId: string; inputName: string } {
  if (!isRecord(value)) return fallback;
  return {
    nodeId: readString(value.nodeId, fallback.nodeId),
    inputName: readString(value.inputName, fallback.inputName),
  };
}

function readWorkflowBindings(
  value: unknown,
  fallback: WorkflowNodeBindings,
): WorkflowNodeBindings {
  if (!isRecord(value)) return structuredClone(fallback);
  const loraRaw = isRecord(value.lora) ? value.lora : {};
  const imageEncoderRaw = isRecord(value.imageEncoder) ? value.imageEncoder : undefined;
  const outputRaw = isRecord(value.output) ? value.output : {};
  const emptyLatentRaw = isRecord(value.emptyLatent) ? value.emptyLatent : undefined;

  const result: WorkflowNodeBindings = {
    prompt: readBinding(value.prompt, fallback.prompt),
    negativePrompt: readBinding(value.negativePrompt, fallback.negativePrompt),
    seed: readBinding(value.seed, fallback.seed),
    steps: readBinding(value.steps, fallback.steps),
    cfg: readBinding(value.cfg, fallback.cfg),
    unetName: readBinding(value.unetName, fallback.unetName),
    clipName: readBinding(value.clipName, fallback.clipName),
    vaeName: readBinding(value.vaeName, fallback.vaeName),
    lora: {
      nodeId: readString(loraRaw.nodeId, fallback.lora.nodeId),
      nameInputName: readString(loraRaw.nameInputName, fallback.lora.nameInputName),
      strengthInputName: readString(
        loraRaw.strengthInputName,
        fallback.lora.strengthInputName,
      ),
      upstreamModelNodeId: readString(
        loraRaw.upstreamModelNodeId,
        fallback.lora.upstreamModelNodeId,
      ),
      downstreamModelBindings: Array.isArray(loraRaw.downstreamModelBindings)
        ? loraRaw.downstreamModelBindings
            .filter(isRecord)
            .map((b, i) =>
              readBinding(
                b,
                fallback.lora.downstreamModelBindings[i] ??
                  fallback.lora.downstreamModelBindings[0],
              ),
            )
        : structuredClone(fallback.lora.downstreamModelBindings),
    },
    output: {
      nodeId: readString(outputRaw.nodeId, fallback.output.nodeId),
      outputKey: readString(outputRaw.outputKey, fallback.output.outputKey),
    },
  };

  if (fallback.resolution || value.resolution) {
    result.resolution = readBinding(value.resolution, fallback.resolution ?? fallback.prompt);
  }
  if (fallback.imageEncoder || imageEncoderRaw) {
    result.imageEncoder = {
      nodeId: readString(
        imageEncoderRaw?.nodeId,
        fallback.imageEncoder?.nodeId ?? fallback.prompt.nodeId,
      ),
      inputPrefix: readString(
        imageEncoderRaw?.inputPrefix,
        fallback.imageEncoder?.inputPrefix ?? "images.image_",
      ),
    };
  }
  if (fallback.emptyLatent || emptyLatentRaw) {
    result.emptyLatent = {
      width: readBinding(
        emptyLatentRaw?.width,
        fallback.emptyLatent?.width ?? { nodeId: "6", inputName: "width" },
      ),
      height: readBinding(
        emptyLatentRaw?.height,
        fallback.emptyLatent?.height ?? { nodeId: "6", inputName: "height" },
      ),
    };
  }
  if (fallback.kSamplerLatent || value.kSamplerLatent) {
    result.kSamplerLatent = readBinding(
      value.kSamplerLatent,
      fallback.kSamplerLatent ?? { nodeId: "7", inputName: "latent_image" },
    );
  }
  return result;
}

/** 官方单图旧键：出现即拒绝，防止配置回退到模糊单图模式 */
const FORBIDDEN_LEGACY_KEYS = [
  "inputImageNodeId",
  "inputImageInputName",
  "promptNodeId",
  "promptInputName",
  "seedNodeId",
  "seedInputName",
  "outputNodeId",
  "workflowPath",
  "workflow",
] as const;

export function assertNoLegacyComfyKeys(raw: Record<string, unknown>): void {
  const offenders: string[] = [];
  for (const key of FORBIDDEN_LEGACY_KEYS) {
    if (key in raw) offenders.push(key);
  }
  const image = raw.image;
  if (isRecord(image)) {
    for (const key of FORBIDDEN_LEGACY_KEYS) {
      if (key in image) offenders.push(`image.${key}`);
    }
  }
  if (offenders.length > 0) {
    throw new Error(
      `comfy-plus 不兼容官方单图旧键，请迁移到 nodeBindings/workflows：${offenders.join(", ")}`,
    );
  }
}

export function parseComfyPlusConfig(raw: unknown): ComfyPlusConfig {
  const base = structuredClone(DEFAULT_COMFY_PLUS_CONFIG);
  if (!isRecord(raw)) return base;
  assertNoLegacyComfyKeys(raw);

  const workflows = isRecord(raw.workflows) ? raw.workflows : {};
  const defaults = isRecord(raw.defaults) ? raw.defaults : {};
  const operations = isRecord(raw.operations) ? raw.operations : {};
  const colorGrade = isRecord(operations.colorGrade) ? operations.colorGrade : {};
  const pose = isRecord(operations.pose) ? operations.pose : {};
  const nodeBindings = isRecord(raw.nodeBindings) ? raw.nodeBindings : {};

  return {
    mode: "local",
    baseUrl: readString(raw.baseUrl, base.baseUrl).replace(/\/$/, ""),
    timeoutMs: readPositiveInt(raw.timeoutMs, base.timeoutMs),
    pollIntervalMs: readPositiveInt(raw.pollIntervalMs, base.pollIntervalMs),
    maxUploadBytes: readPositiveInt(raw.maxUploadBytes, base.maxUploadBytes),
    allowPrivateNetwork: readBoolean(raw.allowPrivateNetwork, base.allowPrivateNetwork),
    workflows: {
      t2i: readString(workflows.t2i, base.workflows.t2i),
      edit: readString(workflows.edit, base.workflows.edit),
      colorGrade: readString(workflows.colorGrade, base.workflows.colorGrade),
      pose: readString(workflows.pose, base.workflows.pose),
    },
    defaults: {
      unetName: readString(defaults.unetName, base.defaults.unetName),
      clipName: readString(defaults.clipName, base.defaults.clipName),
      vaeName: readString(defaults.vaeName, base.defaults.vaeName),
      loraName: readString(defaults.loraName, base.defaults.loraName),
      loraStrength: readNumber(defaults.loraStrength, base.defaults.loraStrength),
      loraEnabled: readBoolean(defaults.loraEnabled, base.defaults.loraEnabled),
      steps: readPositiveInt(defaults.steps, base.defaults.steps),
      cfg: readNumber(defaults.cfg, base.defaults.cfg),
      width: readPositiveInt(defaults.width, base.defaults.width),
      height: readPositiveInt(defaults.height, base.defaults.height),
      resolution: readPositiveInt(defaults.resolution, base.defaults.resolution),
      negativePrompt: typeof defaults.negativePrompt === "string"
        ? defaults.negativePrompt
        : base.defaults.negativePrompt,
      samplerName: readString(defaults.samplerName, base.defaults.samplerName),
      scheduler: readString(defaults.scheduler, base.defaults.scheduler),
    },
    operations: {
      colorGrade: { enabled: readBoolean(colorGrade.enabled, false) },
      pose: { enabled: readBoolean(pose.enabled, false) },
    },
    nodeBindings: {
      t2i: readWorkflowBindings(nodeBindings.t2i, T2I_NODE_BINDINGS),
      edit: readWorkflowBindings(nodeBindings.edit, EDIT_NODE_BINDINGS),
    },
  };
}

export function getComfyPlusPluginConfig(cfg: unknown): unknown {
  if (!isRecord(cfg)) return undefined;
  const plugins = cfg.plugins;
  if (!isRecord(plugins)) return undefined;
  const entries = plugins.entries;
  if (!isRecord(entries)) return undefined;
  const entry = entries["comfy-plus"];
  if (!isRecord(entry)) return undefined;
  return entry.config;
}
