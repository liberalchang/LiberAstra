export {
  T2I_NODE_BINDINGS,
  EDIT_NODE_BINDINGS,
  DEFAULT_COMFY_PLUS_CONFIG,
} from "../config/defaults.js";

/** Edit 动态 LoadImage 节点 id：image_1 → 101 */
export function loadImageNodeId(slotIndex1Based: number): string {
  if (slotIndex1Based < 1 || slotIndex1Based > 16) {
    throw new Error(`LoadImage 槽位越界: ${slotIndex1Based}`);
  }
  return String(100 + slotIndex1Based);
}
