/** 把画布菜单项落到节点上，并只补建还缺的前置输入。已有输入不删除。
 * CanvasPage 与属性面板切换功能时调用。
 */

import type { CanvasMenuItem, ExecutionSpec, ProviderOut, WorkflowPackOut } from "@/api/client";
import type { MediaKind } from "@/canvas/types";
import { outputKindOfCapability } from "@/canvas/types";
import { defaultAccelState, hasAccel } from "@/components/AccelControl";
import { nextVarName, useCanvasStore } from "@/stores/canvas";

const MEDIA = new Set(["image", "video", "audio", "text"]);
/** 音色写在 voice 上，而不是 model。Edge、OpenAI TTS、豆包语音都是这样。 */
const VOICE_PROVIDER_TYPES = new Set(["edge_tts", "openai_tts", "volcengine_speech"]);

/** 自动匹配：该能力下已启用的模型和工作流。手动指定：只留勾选过的。 */
export function specsForMenu(item: CanvasMenuItem, specs: ExecutionSpec[]): ExecutionSpec[] {
  const pool = specs.filter((spec) => spec.sub_capability === item.sub_capability);
  if (item.bind_mode !== "manual") return pool;
  return pool.filter((spec) =>
    item.manual_targets.some(
      (target) =>
        target.target_id === spec.target_id &&
        target.target_type === spec.target_type &&
        (target.provider_id == null || target.provider_id === spec.provider_id),
    ),
  );
}

export function resolveSpec(
  item: CanvasMenuItem,
  specs: ExecutionSpec[],
): ExecutionSpec | undefined {
  const allowed = specsForMenu(item, specs);
  const preferred = item.default_target;
  if (preferred) {
    const hit = allowed.find(
      (spec) =>
        spec.target_id === preferred.target_id &&
        spec.target_type === preferred.target_type &&
        (preferred.provider_id == null || preferred.provider_id === spec.provider_id),
    );
    if (hit) return hit;
  }
  return allowed[0];
}

/** 供应商列表里的语音模型是「id · 名称 · 角色」。Liber Speech 请求只用前面的 id。 */
function liberModelId(targetId: string): string {
  const head = targetId.split(" · ")[0]?.trim();
  return head || targetId;
}

/** 节点上可能是短 id，菜单里是整行目录名。两边都算选中同一项。 */
export function speechSpecSelected(
  spec: ExecutionSpec,
  data: { model?: string; voice?: string; workflow?: string },
): boolean {
  if (spec.target_type === "workflow") return spec.target_id === (data.workflow || "");
  const current = data.voice || data.model || "";
  if (!current) return false;
  return spec.target_id === current || spec.target_id.startsWith(`${current} · `);
}

/** 语音节点把音色和服务模型分开放。返回值可直接交给 updateNodeData。 */
export function speechFieldsFromSpec(spec: ExecutionSpec | undefined, providers: ProviderOut[]) {
  const provider = spec ? providerForSpec(spec, providers) : undefined;
  const asVoice = Boolean(provider && VOICE_PROVIDER_TYPES.has(provider.type) && spec?.target_type === "model");
  const model =
    spec?.target_type === "model" && !asVoice
      ? provider?.type === "liber_speech"
        ? liberModelId(spec.target_id)
        : spec.target_id
      : "";
  return {
    providerId: provider?.id ?? null,
    model,
    voice: asVoice && spec ? spec.target_id : "",
    workflow: spec?.target_type === "workflow" ? spec.target_id : "",
  };
}

export function providerForSpec(
  spec: ExecutionSpec,
  providers: ProviderOut[],
): ProviderOut | undefined {
  if (spec.provider_id != null) {
    return providers.find((item) => item.id === spec.provider_id && item.enabled);
  }
  return providers.find((item) => item.enabled && item.type === spec.provider_type);
}

/** 返回新补建的输入节点数量。 */
export function applyMenuToNode(
  nodeId: string,
  item: CanvasMenuItem,
  spec: ExecutionSpec | undefined,
  providers: ProviderOut[],
  packs: WorkflowPackOut[] = [],
): number {
  const store = useCanvasStore.getState();
  const provider = spec ? providerForSpec(spec, providers) : undefined;
  const outputKind =
    spec?.category === "video"
      ? "video"
      : spec?.category === "image"
        ? "image"
        : spec?.sub_capability === "asr" || spec?.sub_capability === "analysis"
          ? "text"
          : outputKindOfCapability(spec?.sub_capability);
  let created = 0;
  store.batch(() => {
    if (item.category === "speech") {
      store.updateNodeData(nodeId, {
        mode: item.sub_capability === "asr" ? "asr" : "tts",
        presetId: item.id,
        presetTitle: item.title,
        ...speechFieldsFromSpec(spec, providers),
      });
      created = ensureSlots(nodeId, slotsFor(spec, item));
      return;
    }
    const node0 = store.nodes.find((node) => node.id === nodeId);
    const existingVar = (node0?.data as { varName?: string } | undefined)?.varName ?? "";
    const varName =
      outputKind && (!existingVar || /^output_(image|video|audio|text|media)_\d+$/.test(existingVar))
        ? nextVarName(
            store.nodes.filter((node) => node.id !== nodeId),
            `output_${outputKind}`,
          )
        : existingVar;
    const values = Object.fromEntries(
      Object.entries(spec?.inputs ?? {}).map(([key, field]) => [
        key,
        field.default != null ? String(field.default) : "",
      ]),
    );
    store.updateNodeData(nodeId, {
      presetId: item.id,
      presetTitle: item.title,
      subCapability: item.sub_capability,
      targetType: spec?.target_type ?? "",
      targetId: spec?.target_id ?? "",
      targetLabel: spec?.display_name ?? "",
      providerId: provider?.id ?? null,
      pack: spec?.target_type === "workflow" ? spec.target_id : "",
      group: item.title,
      outputKind: outputKind ?? null,
      values,
      ...(varName ? { varName } : {}),
      // 有工作流列表时写入加速默认值；没列表时不覆盖，避免把已有开关清掉。
      ...(packs.length ? { accel: accelOf(spec, packs) } : {}),
    });
    created = ensureSlots(nodeId, slotsFor(spec, item));
  });
  return created;
}

function accelOf(spec: ExecutionSpec | undefined, packs: WorkflowPackOut[]) {
  if (spec?.target_type !== "workflow") return null;
  const pack = packs.find((item) => item.name === spec.target_id);
  return hasAccel(pack?.accel) ? defaultAccelState(pack?.accel) : null;
}

function slotsFor(spec: ExecutionSpec | undefined, item: CanvasMenuItem) {
  // 绑定到工作流或模型时用它自己的槽；还没绑定时用能力表上的默认槽。
  if (spec) return spec.media_slots;
  return item.media_slots ?? [];
}

function ensureSlots(nodeId: string, mediaSlots: { required: boolean; type: string; input_kind?: string; multiple?: boolean }[]): number {
  const required = mediaSlots.filter((slot) => slot.required && (MEDIA.has(slot.type) || slot.input_kind === "character"));
  const needed = new Map<string, number>();
  for (const slot of required) {
    const kind = slot.input_kind || slot.type;
    if (slot.multiple) {
      needed.set(kind, Math.max(needed.get(kind) ?? 0, 1));
    } else {
      needed.set(kind, (needed.get(kind) ?? 0) + 1);
    }
  }
  let created = 0;
  const node = useCanvasStore.getState().nodes.find((item) => item.id === nodeId);
  if (!node) return 0;
  for (const [mediaType, count] of needed) {
    const have = incomingCount(nodeId, mediaType as MediaKind);
    for (let index = have; index < count; index += 1) {
      const inputNode = useCanvasStore.getState().addNode("input", mediaType as MediaKind, {
        x: node.position.x - 320,
        y: node.position.y + (have + created) * 180,
      });
      useCanvasStore.getState().onConnect({
        source: inputNode.id,
        target: nodeId,
        sourceHandle: `out-${inputNode.id}`,
        targetHandle: `in-${nodeId}`,
      });
      if (mediaType === "text") {
        const createdNode = useCanvasStore.getState().nodes.find((item) => item.id === inputNode.id);
        const varName = createdNode?.data.varName ?? "";
        const target = useCanvasStore.getState().nodes.find((item) => item.id === nodeId);
        const prompt =
          target?.data.kind === "function"
            ? target.data.prompt
            : target?.data.kind === "speech"
              ? (target.data.text ?? "")
              : "";
        if (varName && !prompt.trim()) {
          useCanvasStore.getState().updateNodeData(
            nodeId,
            target?.data.kind === "speech" ? { text: `{{${varName}}}` } : { prompt: `{{${varName}}}` },
          );
        }
      }
      created += 1;
    }
  }
  return created;
}

function incomingCount(nodeId: string, mediaType: MediaKind): number {
  const accept = mediaType === "character" ? "image" : mediaType;
  const current = useCanvasStore.getState();
  return current.edges.filter((edge) => {
    if (edge.target !== nodeId) return false;
    const source = current.nodes.find((node) => node.id === edge.source);
    if (!source) return false;
    if (source.data.kind === "input") {
      if (accept === "image") return source.data.mediaKind === "image" || source.data.mediaKind === "character";
      return source.data.mediaKind === accept;
    }
    if (source.data.kind === "function") return source.data.outputKind === accept;
    if (source.data.kind === "speech") {
      if (accept === "audio") return source.data.mode !== "asr";
      if (accept === "text") return source.data.mode === "asr";
    }
    return false;
  }).length;
}
