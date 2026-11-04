/** 画布功能绑定规则：功能创建时固定，只有空节点允许首次绑定。 */

export type BindingNode = {
  kind: string;
  presetId?: string;
  presetTitle?: string;
  pack?: string;
  targetType?: string;
  targetId?: string;
  providerId?: number | null;
  subCapability?: string;
  mode?: string;
};

export type BindingCheck = { ok: boolean; reason?: string };

export function canApplyMenu(
  node: BindingNode,
  menuId: string,
  menuSubCapability = "",
): BindingCheck {
  if (node.kind !== "function" && node.kind !== "speech") {
    return { ok: false, reason: "只有功能节点或语音节点可以套用功能菜单" };
  }
  if (!menuId) {
    return { ok: false, reason: "功能菜单项不能为空" };
  }
  if (node.kind === "speech" && node.mode && menuSubCapability && node.mode !== menuSubCapability) {
    return { ok: false, reason: "语音模式在创建时确定，请新建节点" };
  }
  if (node.presetId) {
    return { ok: false, reason: "功能在创建时确定，请新建节点" };
  }
  if (node.pack || node.targetType || node.targetId) {
    return { ok: false, reason: "节点已绑定执行目标，请新建节点" };
  }
  return { ok: true };
}

export function canApplyPack(
  node: BindingNode,
  packName: string,
  allowedPackNames: string[],
): BindingCheck {
  if (node.kind !== "function") {
    return { ok: false, reason: "只有功能节点可以绑定工作流包" };
  }
  if (!packName) {
    return { ok: false, reason: "工作流包不能为空" };
  }
  if (node.presetId && !allowedPackNames.includes(packName)) {
    return { ok: false, reason: "该工作流不属于当前功能" };
  }
  return { ok: true };
}

export function canEditSpeechField(field: string): boolean {
  return field !== "mode";
}

export function functionNodeTitle(
  data: Pick<BindingNode, "presetTitle" | "pack" | "targetId">,
  fallback = "通用节点",
): string {
  return data.presetTitle || data.pack || data.targetId || fallback;
}
