/** 自定义边：贝塞尔曲线，被节点挡住时改走上方或下方空隙。点击宽热区删除。 */
import { useMemo } from "react";
import {
  BaseEdge,
  getBezierPath,
  useNodes,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
} from "@xyflow/react";

import { useTx } from "@/i18n/tx";

const SAMPLES = 16;
const CHANNEL_MARGIN = 24;

type Rect = { x: number; y: number; w: number; h: number };

function nodeRect(node: Node): Rect {
  const w = node.measured?.width ?? node.width ?? 260;
  const h = node.measured?.height ?? node.height ?? 100;
  return { x: node.position.x, y: node.position.y, w, h };
}

function cubicPoint(t: number, p0: number, p1: number, p2: number, p3: number): number {
  const u = 1 - t;
  return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
}

function parseCubic(path: string): number[] | null {
  const match =
    /M\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s*C\s*([-\d.eE]+)[,\s]+([-\d.eE]+)\s+([-\d.eE]+)[,\s]+([-\d.eE]+)\s+([-\d.eE]+)[,\s]+([-\d.eE]+)/.exec(
      path,
    );
  if (!match) return null;
  return match.slice(1, 9).map(Number);
}

function hitsRect(x: number, y: number, rect: Rect): boolean {
  return x > rect.x && x < rect.x + rect.w && y > rect.y && y < rect.y + rect.h;
}

/** 起点水平离开，沿通道走到终点再水平进入。 */
function detourPath(sx: number, sy: number, tx: number, ty: number, channelY: number): string {
  const span = tx - sx;
  const dir = span >= 0 ? 1 : -1;
  const bend = Math.max(24, Math.min(80, Math.abs(span) * 0.35));
  const leaveX = sx + dir * bend;
  const approachX = tx - dir * bend;
  const midX = (sx + tx) / 2;
  return `M${sx},${sy} C${leaveX},${sy} ${leaveX},${channelY} ${midX},${channelY} C${approachX},${channelY} ${approachX},${ty} ${tx},${ty}`;
}

function routedPath(
  bezier: string,
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  blockers: Rect[],
): string {
  if (!blockers.length) return bezier;
  const cubic = parseCubic(bezier);
  if (!cubic) return bezier;
  const [x0, y0, cx1, cy1, cx2, cy2, x3, y3] = cubic;
  const hit: Rect[] = [];
  for (let i = 1; i < SAMPLES; i++) {
    const t = i / SAMPLES;
    const x = cubicPoint(t, x0, cx1, cx2, x3);
    const y = cubicPoint(t, y0, cy1, cy2, y3);
    for (const rect of blockers) {
      if (hit.includes(rect)) continue;
      if (hitsRect(x, y, rect)) hit.push(rect);
    }
  }
  if (!hit.length) return bezier;
  const top = Math.min(...hit.map((rect) => rect.y));
  const bottom = Math.max(...hit.map((rect) => rect.y + rect.h));
  const above = top - CHANNEL_MARGIN;
  const below = bottom + CHANNEL_MARGIN;
  const midY = (sy + ty) / 2;
  const channelY = Math.abs(above - midY) <= Math.abs(below - midY) ? above : below;
  return detourPath(sx, sy, tx, ty, channelY);
}

export function CanvasEdge({
  id,
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
}: EdgeProps<Edge>) {
  const nodes = useNodes();
  const { deleteElements } = useReactFlow();
  const tx = useTx();

  const path = useMemo(() => {
    const [bezier] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
    const minX = Math.min(sourceX, targetX);
    const maxX = Math.max(sourceX, targetX);
    const blockers = nodes
      .filter((node) => node.id !== source && node.id !== target)
      .map(nodeRect)
      .filter((rect) => rect.x + rect.w > minX && rect.x < maxX);
    return routedPath(bezier, sourceX, sourceY, targetX, targetY, blockers);
  }, [nodes, source, target, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition]);

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
