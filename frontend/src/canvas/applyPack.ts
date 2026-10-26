/** 功能节点选包后的统一动作：写入包配置 + 自动补建必填媒体输入节点并连线。
 * 快速建点菜单与右侧属性面板共用。
 */
import type { WorkflowPackOut } from "@/api/client";
import { outputKindOfCapability, type MediaKind } from "@/canvas/types";
import { defaultAccelState, hasAccel } from "@/components/AccelControl";
import { nextVarName, useCanvasStore } from "@/stores/canvas";

const MEDIA_TYPES = ["image", "video", "audio"] as const;

/** 返回自动补建的输入节点数。 */
export function applyPackToNode(
  nodeId: string,
  pack: WorkflowPackOut,
  currentValues: Record<string, string>,
): number {
  const store = useCanvasStore.getState();
  const outKind = outputKindOfCapability(pack.capability);
  const node0 = store.nodes.find((n) => n.id === nodeId);
  const existingVar = (node0?.data as { varName?: string } | undefined)?.varName ?? "";
  // 变量名缺省或仍是旧默认(output_*)时,按产物类型重新分配;用户改过的名字不动
  const varName =
    outKind && (!existingVar || /^output_(image|video|audio|media)_\d+$/.test(existingVar))
      ? nextVarName(
          store.nodes.filter((n) => n.id !== nodeId),
          `output_${outKind}`,
        )
      : existingVar;
  // 选包 = 一步撤销:写配置 + 补建输入节点 + 连线合并为一个历史条目
  let created = 0;
  store.batch(() => {
    store.updateNodeData(nodeId, {
      pack: pack.name,
      outputKind: outKind,
      ...(varName ? { varName } : {}),
      // 换包后参数值保留同名键,其余回落 manifest 默认。
      // 例外:模型文件/枚举类参数(options_from / options,如 unet/clip/vae)一律回落新包默认——
      // 跨包保留会把上一套模型组合注入新工作流(如 flux3 三件套打进 qwen 包 → KSampler 维度不匹配)。
      values: Object.fromEntries(
        Object.entries(pack.inputs)
          .filter(([, spec]) => !MEDIA_TYPES.includes(spec.type as (typeof MEDIA_TYPES)[number]))
          .map(([key, spec]) => {
            const fallback = spec.default != null ? String(spec.default) : "";
            const carried = spec.options_from || spec.options ? undefined : currentValues[key];
            return [key, carried ?? fallback];
          }),
      ),
      accel: hasAccel(pack.accel) ? defaultAccelState(pack.accel) : null,
    });

    const node = useCanvasStore.getState().nodes.find((n) => n.id === nodeId);
    if (!node) return;
    Object.entries(pack.inputs).forEach(([, spec], index) => {
      if (!MEDIA_TYPES.includes(spec.type as (typeof MEDIA_TYPES)[number]) || !spec.required) return;
      const mediaKind = spec.type as MediaKind;
      const current = useCanvasStore.getState();
      const hasIncoming = current.edges.some((e) => {
        if (e.target !== nodeId) return false;
        const source = current.nodes.find((n) => n.id === e.source);
        return source?.data.kind === "input" && source.data.mediaKind === mediaKind;
      });
      if (hasIncoming) return;
      const inputNode = useCanvasStore.getState().addNode("input", mediaKind, {
        x: node.position.x - 320,
        y: node.position.y + created * 180 + index * 40,
      });
      useCanvasStore.getState().onConnect({
        source: inputNode.id,
        target: nodeId,
        sourceHandle: `out-${inputNode.id}`,
        targetHandle: `in-${nodeId}`,
      });
      created += 1;
    });
  });
  return created;
}
