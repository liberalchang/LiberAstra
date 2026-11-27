/** ComfyUI API Prompt：节点 id → 节点定义 */
export type ComfyPrompt = Record<string, ComfyNode>;

export type ComfyNode = {
  class_type: string;
  inputs: Record<string, unknown>;
  _meta?: Record<string, unknown>;
};

export type ImageRole = string;

export type InputImage = {
  buffer: Buffer;
  mimeType: string;
  fileName?: string;
  role?: ImageRole;
};

export type SlotMapEntry = {
  slot: string;
  sourceName: string;
  comfyFilename: string;
  role?: ImageRole;
};

export type PromptNormalizationAudit = {
  originalPrompt: string;
  normalizedPrompt: string;
  slotMap: SlotMapEntry[];
  warnings: string[];
};

export type NodeBinding = {
  nodeId: string;
  inputName: string;
};

export type LoraBinding = {
  nodeId: string;
  nameInputName: string;
  strengthInputName: string;
  /** 旁路时 model 输入所连上游节点 id（通常为 QwenImage21Cache） */
  upstreamModelNodeId: string;
  /** KSampler 等下游读取 model 的节点绑定 */
  downstreamModelBindings: NodeBinding[];
};

export type ImageEncoderBinding = {
  nodeId: string;
  inputPrefix: string;
};

export type WorkflowNodeBindings = {
  prompt: NodeBinding;
  negativePrompt: NodeBinding;
  seed: NodeBinding;
  steps: NodeBinding;
  cfg: NodeBinding;
  width?: NodeBinding;
  height?: NodeBinding;
  resolution?: NodeBinding;
  unetName: NodeBinding;
  clipName: NodeBinding;
  vaeName: NodeBinding;
  lora: LoraBinding;
  imageEncoder?: ImageEncoderBinding;
  output: { nodeId: string; outputKey: string };
  emptyLatent?: { width: NodeBinding; height: NodeBinding };
  kSamplerLatent?: NodeBinding;
};

export type OperationKind = "t2i" | "edit" | "color-grade" | "pose-transfer";

export type ComfyPlusDefaults = {
  unetName: string;
  clipName: string;
  vaeName: string;
  loraName: string;
  loraStrength: number;
  loraEnabled: boolean;
  steps: number;
  cfg: number;
  width: number;
  height: number;
  resolution: number;
  negativePrompt: string;
  samplerName: string;
  scheduler: string;
};

export type ComfyPlusConfig = {
  mode: "local";
  baseUrl: string;
  timeoutMs: number;
  pollIntervalMs: number;
  maxUploadBytes: number;
  allowPrivateNetwork: boolean;
  workflows: {
    t2i: string;
    edit: string;
    colorGrade: string;
    pose: string;
  };
  defaults: ComfyPlusDefaults;
  operations: {
    colorGrade: { enabled: boolean };
    pose: { enabled: boolean };
  };
  nodeBindings: {
    t2i: WorkflowNodeBindings;
    edit: WorkflowNodeBindings;
    colorGrade?: WorkflowNodeBindings;
    pose?: WorkflowNodeBindings;
  };
};

export type ProviderOptionOverrides = {
  /** 原始 operation（可为非法类型，由 router 校验） */
  operation?: unknown;
  steps?: number;
  cfg?: number;
  negativePrompt?: string;
  seed?: number;
  loraEnabled?: boolean;
  loraStrength?: number;
  loraName?: string;
  unetName?: string;
  clipName?: string;
  vaeName?: string;
  width?: number;
  height?: number;
  resolution?: number;
  imageRoles?: ImageRole[];
  imageCount?: number;
};

export type ComfyErrorCode =
  | "COMFY_UNREACHABLE"
  | "UPLOAD_FAILED"
  | "EXECUTION_FAILED"
  | "EXECUTION_TIMEOUT"
  | "VALIDATION_FAILED";

export type ComfyPlusError = Error & {
  code: ComfyErrorCode;
  details?: Record<string, unknown>;
};
