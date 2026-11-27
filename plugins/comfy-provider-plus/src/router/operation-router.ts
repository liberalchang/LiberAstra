import type { ComfyPlusConfig, OperationKind } from "../types.js";
import { MAX_INPUT_IMAGES } from "../config/defaults.js";

export type RouteDecision = {
  operation: OperationKind;
  workflowKey: "t2i" | "edit" | "colorGrade" | "pose";
  imageCount: number;
};

function normalizeOperation(raw: unknown): OperationKind | undefined {
  if (typeof raw !== "string") return undefined;
  const v = raw.trim().toLowerCase();
  if (v === "t2i" || v === "text-to-image" || v === "txt2img") return "t2i";
  if (v === "edit" || v === "image-edit" || v === "i2i") return "edit";
  if (v === "color-grade" || v === "colorgrade" || v === "color_grade") return "color-grade";
  if (v === "pose-transfer" || v === "pose" || v === "pose_transfer") return "pose-transfer";
  return undefined;
}

/**
 * 路由：0 图 → t2i；1..16 → edit；color-grade / pose 强门禁。
 * 未识别操作或开关关闭时直接报错，不退回通用编辑/文生图。
 */
export function routeOperation(params: {
  config: ComfyPlusConfig;
  imageCount: number;
  requestedOperation?: unknown;
}): RouteDecision {
  const imageCount = params.imageCount;
  if (imageCount > MAX_INPUT_IMAGES) {
    throw Object.assign(
      new Error(`参考图数量 ${imageCount} 超过上限 ${MAX_INPUT_IMAGES}，本地拒绝且不发起网络请求`),
      { code: "VALIDATION_FAILED" as const },
    );
  }
  if (imageCount < 0) {
    throw Object.assign(new Error("imageCount 非法"), { code: "VALIDATION_FAILED" as const });
  }

  const requested = normalizeOperation(params.requestedOperation);

  if (requested === "color-grade") {
    if (!params.config.operations.colorGrade.enabled) {
      throw Object.assign(new Error("调色工作流未验证"), { code: "VALIDATION_FAILED" as const });
    }
    if (imageCount < 2) {
      throw Object.assign(new Error("调色至少需要原图 + 色彩参考图共 2 张"), {
        code: "VALIDATION_FAILED" as const,
      });
    }
    return { operation: "color-grade", workflowKey: "colorGrade", imageCount };
  }

  if (requested === "pose-transfer") {
    if (!params.config.operations.pose.enabled) {
      throw Object.assign(new Error("换姿工作流未验证"), { code: "VALIDATION_FAILED" as const });
    }
    if (imageCount < 2) {
      throw Object.assign(new Error("换姿至少需要人物原图 + 姿态参考图共 2 张"), {
        code: "VALIDATION_FAILED" as const,
      });
    }
    return { operation: "pose-transfer", workflowKey: "pose", imageCount };
  }

  if (requested && requested !== "t2i" && requested !== "edit") {
    throw Object.assign(new Error(`未识别的 operation: ${String(params.requestedOperation)}`), {
      code: "VALIDATION_FAILED" as const,
    });
  }

  if (requested === "t2i") {
    if (imageCount > 0) {
      throw Object.assign(new Error("operation=t2i 时不得附带参考图"), {
        code: "VALIDATION_FAILED" as const,
      });
    }
    return { operation: "t2i", workflowKey: "t2i", imageCount: 0 };
  }

  if (requested === "edit") {
    if (imageCount < 1) {
      throw Object.assign(new Error("operation=edit 至少需要 1 张参考图"), {
        code: "VALIDATION_FAILED" as const,
      });
    }
    return { operation: "edit", workflowKey: "edit", imageCount };
  }

  // 自动路由
  if (imageCount === 0) {
    return { operation: "t2i", workflowKey: "t2i", imageCount: 0 };
  }
  return { operation: "edit", workflowKey: "edit", imageCount };
}
