import type { ComfyPlusConfig, OperationKind } from "../types.js";
import { MAX_INPUT_IMAGES } from "../config/defaults.js";
import { createComfyError } from "../comfy/errors.js";

export type RouteDecision = {
  operation: OperationKind;
  workflowKey: "t2i" | "edit" | "colorGrade" | "pose";
  imageCount: number;
};

function normalizeOperation(raw: unknown): OperationKind | undefined {
  if (typeof raw !== "string") return undefined;
  const v = raw.trim().toLowerCase();
  if (!v) return undefined;
  if (v === "t2i" || v === "text-to-image" || v === "txt2img") return "t2i";
  if (v === "edit" || v === "image-edit" || v === "i2i") return "edit";
  if (v === "color-grade" || v === "colorgrade" || v === "color_grade") return "color-grade";
  if (v === "pose-transfer" || v === "pose" || v === "pose_transfer") return "pose-transfer";
  return undefined;
}

function hasExplicitOperation(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (typeof value === "string" && value.trim() === "") return false;
  return true;
}

/**
 * 路由：0 图 → t2i；1..16 → edit；color-grade / pose 强门禁。
 * 显式传入未知/非法 operation 时直接 VALIDATION_FAILED，禁止静默回退。
 */
export function routeOperation(params: {
  config: ComfyPlusConfig;
  imageCount: number;
  requestedOperation?: unknown;
}): RouteDecision {
  const imageCount = params.imageCount;
  if (imageCount > MAX_INPUT_IMAGES) {
    throw createComfyError(
      "VALIDATION_FAILED",
      `参考图数量 ${imageCount} 超过上限 ${MAX_INPUT_IMAGES}，本地拒绝且不发起网络请求`,
    );
  }
  if (imageCount < 0) {
    throw createComfyError("VALIDATION_FAILED", "imageCount 非法");
  }

  if (hasExplicitOperation(params.requestedOperation)) {
    if (typeof params.requestedOperation !== "string") {
      throw createComfyError(
        "VALIDATION_FAILED",
        `未识别的 operation: ${String(params.requestedOperation)}`,
      );
    }
    const requested = normalizeOperation(params.requestedOperation);
    if (!requested) {
      throw createComfyError(
        "VALIDATION_FAILED",
        `未识别的 operation: ${params.requestedOperation}`,
      );
    }

    if (requested === "color-grade") {
      if (!params.config.operations.colorGrade.enabled) {
        throw createComfyError("VALIDATION_FAILED", "调色工作流未验证");
      }
      if (imageCount < 2) {
        throw createComfyError("VALIDATION_FAILED", "调色至少需要原图 + 色彩参考图共 2 张");
      }
      return { operation: "color-grade", workflowKey: "colorGrade", imageCount };
    }

    if (requested === "pose-transfer") {
      if (!params.config.operations.pose.enabled) {
        throw createComfyError("VALIDATION_FAILED", "换姿工作流未验证");
      }
      if (imageCount < 2) {
        throw createComfyError("VALIDATION_FAILED", "换姿至少需要人物原图 + 姿态参考图共 2 张");
      }
      return { operation: "pose-transfer", workflowKey: "pose", imageCount };
    }

    if (requested === "t2i") {
      if (imageCount > 0) {
        throw createComfyError("VALIDATION_FAILED", "operation=t2i 时不得附带参考图");
      }
      return { operation: "t2i", workflowKey: "t2i", imageCount: 0 };
    }

    if (requested === "edit") {
      if (imageCount < 1) {
        throw createComfyError("VALIDATION_FAILED", "operation=edit 至少需要 1 张参考图");
      }
      return { operation: "edit", workflowKey: "edit", imageCount };
    }
  }

  // 未显式指定 operation 时按图片数量自动路由
  if (imageCount === 0) {
    return { operation: "t2i", workflowKey: "t2i", imageCount: 0 };
  }
  return { operation: "edit", workflowKey: "edit", imageCount };
}
