/** 执行前预检:在发起执行前静态校验节点配置,问题节点红框提示并阻断执行。
 *
 * 只覆盖「前端可判定」的语义问题(未选包/缺必填输入/空文本等);
 * 环、变量重名等结构问题由保存时的后端 _validate_graph 负责。
 */
import type { Edge } from "@xyflow/react";

import type { WorkflowPackOut } from "@/api/client";
import {
  nodeOutputKind,
  type CanvasFlowNode,
  type FunctionNodeData,
  type InputNodeData,
  type SpeechNodeData,
} from "@/canvas/types";

export interface PreflightIssue {
  nodeId: string;
  message: string;
}

const MEDIA_LABEL: Record<string, string> = { image: "图片", video: "视频", audio: "音频" };

/** 目标集合 + 祖先链;目标为空 = 所有末端节点(无出边的节点)。 */
export function scopeOf(
  nodes: CanvasFlowNode[],
  edges: Edge[],
  targetIds: string[],
): Set<string> {
  let targets = targetIds.filter((id) => nodes.some((n) => n.id === id));
  if (targets.length === 0) {
    const hasOutgoing = new Set(edges.map((e) => e.source));
    targets = nodes.filter((n) => !hasOutgoing.has(n.id)).map((n) => n.id);
  }
  const scope = new Set<string>();
  const queue = [...targets];
  while (queue.length) {
    const id = queue.pop()!;
    if (scope.has(id)) continue;
    scope.add(id);
    for (const e of edges) if (e.target === id) queue.push(e.source);
  }
  return scope;
}

/** 校验 scope 内(缺省全图)节点的执行前置条件,返回问题清单。 */
export function validateCanvas(
  nodes: CanvasFlowNode[],
  edges: Edge[],
  packs: WorkflowPackOut[] | undefined,
  scope?: Set<string>,
): PreflightIssue[] {
  const issues: PreflightIssue[] = [];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const packByName = new Map((packs ?? []).map((p) => [p.name, p]));
  const inScope = (id: string) => !scope || scope.has(id);
  const incoming = (id: string) =>
    edges.filter((e) => e.target === id).map((e) => byId.get(e.source)).filter(Boolean) as CanvasFlowNode[];
  const hasOutgoing = (id: string) => edges.some((e) => e.source === id);

  for (const node of nodes) {
    if (!inScope(node.id)) continue;
    const d = node.data;

    if (d.kind === "function") {
      const f = d as FunctionNodeData;
      if (!f.group) {
        issues.push({ nodeId: node.id, message: "未选择所属分组" });
        continue;
      }
      if (!f.pack) {
        issues.push({ nodeId: node.id, message: "未选择工作流包" });
        continue;
      }
      const pack = packByName.get(f.pack);
      if (!pack) continue; // 包清单未加载时不误判
      for (const [key, spec] of Object.entries(pack.inputs)) {
        if (!["image", "video", "audio"].includes(spec.type) || !spec.required) continue;
        const bound = Boolean(f.bindings?.[key]);
        // 蒙版键:名字是 mask 或说明含「蒙版」——要看上游图片输入节点是否挂了蒙版资产
        const isMask =
          spec.type === "image" &&
          (key === "mask" || /蒙版/.test(String(spec.label ?? "") + String(spec.description ?? "")));
        if (isMask) {
          const fedMask = incoming(node.id).some(
            (s) => s.data.kind === "input" && Boolean((s.data as InputNodeData).maskAssetId),
          );
          if (!bound && !fedMask) {
            issues.push({
              nodeId: node.id,
              message: "缺少蒙版（在图片输入节点上点「编辑图片」→ 蒙版模式涂抹导出）",
            });
          }
          continue;
        }
        const fed = incoming(node.id).some((s) => nodeOutputKind(s) === spec.type);
        if (!bound && !fed) {
          issues.push({
            nodeId: node.id,
            message: `缺少必需的${MEDIA_LABEL[spec.type] ?? spec.type}输入「${spec.label ?? key}」`,
          });
        }
      }
      // 只拦 manifest 标了 required 的提示词。调色等包留空会用 default（LoRA 触发词），
      // 与后端 apply_inputs 一致：空串不写入，节点保留包内默认句。
      const promptSpec = pack.inputs["prompt"];
      const effectiveEmpty =
        !f.prompt.trim() && !(f.promptUseOptimized && (f.promptOptimized ?? "").trim());
      const promptFilledByRunner = pack.capability === "avatar" || pack.capability === "motion";
      if (promptSpec?.required && effectiveEmpty && !promptFilledByRunner) {
        issues.push({ nodeId: node.id, message: "提示词为空" });
      }
      continue;
    }

    if (d.kind === "input") {
      const i = d as InputNodeData;
      if (!hasOutgoing(node.id)) continue; // 未连接的输入节点是摆设,不阻断
      if (i.mediaKind === "text") {
        if (!(i.text ?? "").trim()) issues.push({ nodeId: node.id, message: "文本输入为空" });
      } else if (i.mediaKind === "character") {
        if (i.characterId == null) issues.push({ nodeId: node.id, message: "未选择角色" });
      } else if (i.assetId == null) {
        issues.push({ nodeId: node.id, message: `未选择${MEDIA_LABEL[i.mediaKind]}文件` });
      }
      continue;
    }

    if (d.kind === "speech") {
      const s = d as SpeechNodeData;
      if (s.mode === "tts") {
        if (!(s.text ?? "").trim()) issues.push({ nodeId: node.id, message: "待合成文本为空" });
        if (!s.voiceRecordId) issues.push({ nodeId: node.id, message: "未选择音色" });
      } else if (
        !incoming(node.id).some((n) => {
          const kind = nodeOutputKind(n);
          return kind === "audio" || kind === "video";
        })
      ) {
        issues.push({ nodeId: node.id, message: "缺少音频或视频输入" });
      }
      continue;
    }

    if (d.kind === "concat") {
      if (incoming(node.id).length < 2) {
        issues.push({ nodeId: node.id, message: "合成至少需要两路输入" });
      }
    }
  }
  return issues;
}
