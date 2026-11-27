import { loadImageNodeId } from "./presets.js";
import type {
  ComfyPrompt,
  ComfyPlusDefaults,
  ProviderOptionOverrides,
  WorkflowNodeBindings,
} from "../types.js";

function setInput(
  workflow: ComfyPrompt,
  nodeId: string,
  inputName: string,
  value: unknown,
): void {
  const node = workflow[nodeId];
  if (!node) throw new Error(`工作流缺少节点 "${nodeId}"（显式绑定写入失败）`);
  if (!node.inputs || typeof node.inputs !== "object") {
    throw new Error(`节点 "${nodeId}" 缺少 inputs 对象`);
  }
  node.inputs[inputName] = value;
}

export type InjectParams = {
  workflow: ComfyPrompt;
  bindings: WorkflowNodeBindings;
  defaults: ComfyPlusDefaults;
  overrides: ProviderOptionOverrides;
  prompt: string;
  /** 已上传的 Comfy 文件名，按 image_1..N 顺序；T2I 为空 */
  uploadedFilenames: string[];
  /** 是否旁路 LoRA */
  loraEnabled: boolean;
  mode: "t2i" | "edit";
};

/**
 * 仅通过 nodeId + inputName 写入参数；Edit 按 N 动态创建 LoadImage 并接线。
 */
export function injectWorkflowParams(params: InjectParams): ComfyPrompt {
  const wf = structuredClone(params.workflow);
  const b = params.bindings;
  const d = params.defaults;
  const o = params.overrides;

  setInput(wf, b.unetName.nodeId, b.unetName.inputName, o.unetName ?? d.unetName);
  setInput(wf, b.clipName.nodeId, b.clipName.inputName, o.clipName ?? d.clipName);
  setInput(wf, b.vaeName.nodeId, b.vaeName.inputName, o.vaeName ?? d.vaeName);

  setInput(wf, b.prompt.nodeId, b.prompt.inputName, params.prompt);
  setInput(
    wf,
    b.negativePrompt.nodeId,
    b.negativePrompt.inputName,
    o.negativePrompt ?? d.negativePrompt,
  );

  if (b.resolution) {
    setInput(wf, b.resolution.nodeId, b.resolution.inputName, o.resolution ?? d.resolution);
  }

  const seed =
    typeof o.seed === "number" && Number.isFinite(o.seed)
      ? Math.trunc(o.seed)
      : Math.floor(Math.random() * (2 ** 48 - 1));
  setInput(wf, b.seed.nodeId, b.seed.inputName, seed);
  setInput(wf, b.steps.nodeId, b.steps.inputName, o.steps ?? d.steps);
  setInput(wf, b.cfg.nodeId, b.cfg.inputName, o.cfg ?? d.cfg);

  // LoRA
  const loraName = o.loraName ?? d.loraName;
  const loraStrength = o.loraStrength ?? d.loraStrength;
  if (params.loraEnabled) {
    setInput(wf, b.lora.nodeId, b.lora.nameInputName, loraName);
    setInput(wf, b.lora.nodeId, b.lora.strengthInputName, loraStrength);
    for (const down of b.lora.downstreamModelBindings) {
      setInput(wf, down.nodeId, down.inputName, [b.lora.nodeId, 0]);
    }
  } else {
    // 旁路：下游 model 重连到上游 Cache，并移除 LoRA 节点
    for (const down of b.lora.downstreamModelBindings) {
      setInput(wf, down.nodeId, down.inputName, [b.lora.upstreamModelNodeId, 0]);
    }
    delete wf[b.lora.nodeId];
  }

  if (params.mode === "t2i") {
    if (b.emptyLatent) {
      setInput(wf, b.emptyLatent.width.nodeId, b.emptyLatent.width.inputName, o.width ?? d.width);
      setInput(
        wf,
        b.emptyLatent.height.nodeId,
        b.emptyLatent.height.inputName,
        o.height ?? d.height,
      );
    }
    // 断言无 LoadImage / images.*
    for (const [id, node] of Object.entries(wf)) {
      if (node.class_type === "LoadImage" || node.class_type === "VHS_LoadImagePath") {
        throw new Error(`T2I 工作流不应包含图片加载节点: ${id}`);
      }
      for (const key of Object.keys(node.inputs ?? {})) {
        if (key.startsWith("images.")) {
          throw new Error(`T2I 工作流不应包含 images.* 输入: 节点 ${id}.${key}`);
        }
      }
    }
    return wf;
  }

  // Edit：动态 LoadImage + images.image_N
  const n = params.uploadedFilenames.length;
  if (n < 1 || n > 16) {
    throw new Error(`Edit 需要 1..16 张已上传图片，收到 ${n}`);
  }
  if (typeof o.imageCount === "number" && o.imageCount !== n) {
    throw new Error(`imageCount=${o.imageCount} 与实际上传数 ${n} 不一致`);
  }
  if (!b.imageEncoder) {
    throw new Error("Edit 模式缺少 nodeBindings.imageEncoder");
  }

  // 清除模板中可能残留的 images.*（模板不应预置，但防御性清理）
  const encoder = wf[b.imageEncoder.nodeId];
  if (!encoder) throw new Error(`缺少编码器节点 ${b.imageEncoder.nodeId}`);
  for (const key of Object.keys(encoder.inputs)) {
    if (key.startsWith("images.")) delete encoder.inputs[key];
  }

  for (let i = 1; i <= n; i += 1) {
    const filename = params.uploadedFilenames[i - 1];
    if (!filename) throw new Error(`第 ${i} 张上传文件名为空`);
    const loadId = loadImageNodeId(i);
    wf[loadId] = {
      class_type: "LoadImage",
      inputs: { image: filename },
    };
    const inputName = `${b.imageEncoder.inputPrefix}${i}`;
    setInput(wf, b.imageEncoder.nodeId, inputName, [loadId, 0]);
  }

  // 跟随首图比例：KSampler.latent_image → [textEncode, 2]
  if (b.kSamplerLatent) {
    setInput(wf, b.kSamplerLatent.nodeId, b.kSamplerLatent.inputName, [
      b.imageEncoder.nodeId,
      2,
    ]);
  }

  return wf;
}

/** 供元数据回显的已应用参数快照 */
export function buildAppliedParamsMetadata(params: {
  defaults: ComfyPlusDefaults;
  overrides: ProviderOptionOverrides;
  loraEnabled: boolean;
  prompt: string;
  seed?: number;
}): Record<string, unknown> {
  const d = params.defaults;
  const o = params.overrides;
  return {
    prompt: params.prompt,
    negativePrompt: o.negativePrompt ?? d.negativePrompt,
    steps: o.steps ?? d.steps,
    cfg: o.cfg ?? d.cfg,
    width: o.width ?? d.width,
    height: o.height ?? d.height,
    resolution: o.resolution ?? d.resolution,
    unetName: o.unetName ?? d.unetName,
    clipName: o.clipName ?? d.clipName,
    vaeName: o.vaeName ?? d.vaeName,
    loraEnabled: params.loraEnabled,
    loraName: o.loraName ?? d.loraName,
    loraStrength: o.loraStrength ?? d.loraStrength,
    seed: params.seed,
  };
}
