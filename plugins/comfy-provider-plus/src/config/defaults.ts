import type { ComfyPlusConfig, WorkflowNodeBindings } from "../types.js";

/** T2I 显式节点绑定（禁止模糊搜索） */
export const T2I_NODE_BINDINGS: WorkflowNodeBindings = {
  unetName: { nodeId: "1", inputName: "unet_name" },
  clipName: { nodeId: "2", inputName: "clip_name" },
  vaeName: { nodeId: "3", inputName: "vae_name" },
  lora: {
    nodeId: "200",
    nameInputName: "lora_name",
    strengthInputName: "strength_model",
    upstreamModelNodeId: "4",
    downstreamModelBindings: [{ nodeId: "7", inputName: "model" }],
  },
  prompt: { nodeId: "5", inputName: "prompt" },
  negativePrompt: { nodeId: "5", inputName: "negative_prompt" },
  resolution: { nodeId: "5", inputName: "resolution" },
  emptyLatent: {
    width: { nodeId: "6", inputName: "width" },
    height: { nodeId: "6", inputName: "height" },
  },
  seed: { nodeId: "7", inputName: "seed" },
  steps: { nodeId: "7", inputName: "steps" },
  cfg: { nodeId: "7", inputName: "cfg" },
  kSamplerLatent: { nodeId: "7", inputName: "latent_image" },
  output: { nodeId: "9", outputKey: "images" },
};

/** Edit 显式节点绑定；LoadImage 由 injector 动态创建 101..116 */
export const EDIT_NODE_BINDINGS: WorkflowNodeBindings = {
  unetName: { nodeId: "1", inputName: "unet_name" },
  clipName: { nodeId: "2", inputName: "clip_name" },
  vaeName: { nodeId: "3", inputName: "vae_name" },
  lora: {
    nodeId: "200",
    nameInputName: "lora_name",
    strengthInputName: "strength_model",
    upstreamModelNodeId: "4",
    downstreamModelBindings: [{ nodeId: "6", inputName: "model" }],
  },
  prompt: { nodeId: "5", inputName: "prompt" },
  negativePrompt: { nodeId: "5", inputName: "negative_prompt" },
  resolution: { nodeId: "5", inputName: "resolution" },
  imageEncoder: { nodeId: "5", inputPrefix: "images.image_" },
  seed: { nodeId: "6", inputName: "seed" },
  steps: { nodeId: "6", inputName: "steps" },
  cfg: { nodeId: "6", inputName: "cfg" },
  kSamplerLatent: { nodeId: "6", inputName: "latent_image" },
  output: { nodeId: "8", outputKey: "images" },
};

export const DEFAULT_COMFY_PLUS_CONFIG: ComfyPlusConfig = {
  mode: "local",
  baseUrl: "http://10.10.12.140:8188",
  timeoutMs: 600_000,
  pollIntervalMs: 1_500,
  maxUploadBytes: 25 * 1024 * 1024,
  allowPrivateNetwork: true,
  workflows: {
    t2i: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-t2i.json",
    edit: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-edit.json",
    colorGrade: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-color-grade.json",
    pose: "~/.openclaw/workspace/workflows/comfy-plus/qwen-image-pose.json",
  },
  defaults: {
    unetName: "qwen-image-2.1-UC-int8_convrot.safetensors",
    clipName: "qwen3vl_8b_int8_convrot.safetensors",
    vaeName: "qwen_image_2.1_vae_bf16.safetensors",
    loraName: "qwen-image-2.1-uncensored-lora.safetensors",
    loraStrength: 1.0,
    loraEnabled: true,
    steps: 25,
    cfg: 1,
    width: 1024,
    height: 1024,
    resolution: 1024,
    negativePrompt: "",
    samplerName: "euler",
    scheduler: "simple",
  },
  operations: {
    colorGrade: { enabled: false },
    pose: { enabled: false },
  },
  nodeBindings: {
    t2i: T2I_NODE_BINDINGS,
    edit: EDIT_NODE_BINDINGS,
  },
};

export const PROVIDER_ID = "comfy-plus";
export const PLUGIN_ID = "comfy-plus";
export const DEFAULT_COMFY_PLUS_MODEL = "workflow";
export const MAX_INPUT_IMAGES = 16;
