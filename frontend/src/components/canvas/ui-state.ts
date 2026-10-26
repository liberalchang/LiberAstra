/** 画布页内 UI 状态：当前预览的资产（MediaLightbox 由 CanvasPage 统一挂载）
 * + 节点 + 钮的「向后建点」请求（CanvasPage 监听后在节点右侧弹快速建点菜单）。
 */
import { create } from "zustand";

export interface CanvasPreviewTarget {
  id: number;
  kind: string;
}

interface CanvasUiState {
  preview: CanvasPreviewTarget | null;
  setPreview: (target: CanvasPreviewTarget | null) => void;
  /** 节点 + 钮点击:待接的源节点 id(CanvasPage 消费后清零) */
  addAfter: string | null;
  requestAddAfter: (nodeId: string | null) => void;
  /** 失败节点卡上的「重试」请求(CanvasPage 消费后清零,保存并重跑该节点) */
  retryNode: string | null;
  requestRetry: (nodeId: string | null) => void;
}

export const useCanvasUiStore = create<CanvasUiState>()((set) => ({
  preview: null,
  setPreview: (preview) => set({ preview }),
  addAfter: null,
  requestAddAfter: (addAfter) => set({ addAfter }),
  retryNode: null,
  requestRetry: (retryNode) => set({ retryNode }),
}));
