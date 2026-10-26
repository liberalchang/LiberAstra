/** 自定义边：贝塞尔曲线 + 28px 宽隐形热区,点击删除（open-canvas CanvasConnectionEdge 移植）。 */
import {
  BaseEdge,
  getBezierPath,
  useReactFlow,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";

import { useTx } from "@/i18n/tx";

export function CanvasEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
}: EdgeProps<Edge>) {
  const [path] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const { deleteElements } = useReactFlow();
  const tx = useTx();

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        className={
          selected ? "!stroke-primary" : "!stroke-muted-foreground/50 hover:!stroke-primary/70"
        }
        style={{ strokeWidth: selected ? 2.5 : 1.5 }}
      />
      {/* 宽热区：点击删除这条连线 */}
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={28}
        className="nodrag cursor-pointer"
        onClick={() => void deleteElements({ edges: [{ id }] })}
      >
        <title>{tx("点击删除连线")}</title>
      </path>
    </>
  );
}

export const canvasEdgeTypes = { canvas: CanvasEdge };
