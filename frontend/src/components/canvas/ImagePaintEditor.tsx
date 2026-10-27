/** 图像输入编辑器：标记涂抹(十色) + 蒙版(inpaint 白区) + 比例裁剪。
 * 三层 canvas:底图 + 标记层 + 蒙版层。标记导出把笔迹烘进新图;
 * 蒙版导出白区黑底 PNG(供 inpaint 包);裁剪导出只取底图区域。
 */
import { Crop, Eraser, Paintbrush, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { LightboxShell } from "@/components/ui/lightbox";
import { NumberStepper } from "@/components/ui/number-stepper";
import { Segmented } from "@/components/ui/segmented";
import { selectClass } from "@/components/ui/field";
import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";

type Mode = "brush" | "mask" | "crop";

interface CropRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** 标记色板:七色 + 黑白灰。 */
const BRUSH_COLORS = [
  "#e11d48",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#000000",
  "#ffffff",
  "#6b7280",
];

/** 预设比例:w/h。null = 自由。 */
const RATIO_PRESETS: { id: string; label: string; value: number | null }[] = [
  { id: "free", label: "自由", value: null },
  { id: "1:1", label: "1:1", value: 1 },
  { id: "4:3", label: "4:3", value: 4 / 3 },
  { id: "3:2", label: "3:2", value: 3 / 2 },
  { id: "16:9", label: "16:9", value: 16 / 9 },
  { id: "9:16", label: "9:16", value: 9 / 16 },
  { id: "custom", label: "自定义", value: null },
];

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b);
}

/** 近似简化比例(两位以内),如 1.78 → 16:9。 */
function simpleRatio(w: number, h: number): string {
  if (w < 1 || h < 1) return "";
  const g = gcd(Math.round(w), Math.round(h));
  const rw = Math.round(w) / g;
  const rh = Math.round(h) / g;
  if (rw <= 99 && rh <= 99) return `${rw}:${rh}`;
  return (w / h).toFixed(2) + ":1";
}

export function ImagePaintEditor({
  assetId,
  maskAssetId,
  onApply,
  onApplyMask,
  onClose,
}: {
  assetId: number;
  /** 已有蒙版(节点上挂着的),用于提示而非载入编辑 */
  maskAssetId?: number | null;
  /** 导出新图并上传建档后回调（新 assetId;op= 标记 | 裁剪,供版本命名） */
  onApply: (assetId: number, name: string, op: "markup" | "crop") => void;
  /** 导出蒙版建档后回调;无此 prop 时隐藏蒙版模式 */
  onApplyMask?: (assetId: number, name: string) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  const baseRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null); // 标记层
  const maskRef = useRef<HTMLCanvasElement>(null); // 蒙版层
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<Mode>("brush");
  const [brushSize, setBrushSize] = useState(24);
  const [brushColor, setBrushColor] = useState(BRUSH_COLORS[0]);
  const [crop, setCrop] = useState<CropRect | null>(null);
  const [saving, setSaving] = useState(false);
  const [ratioId, setRatioId] = useState("free");
  const [hasMaskStroke, setHasMaskStroke] = useState(false);
  const [customW, setCustomW] = useState("3");
  const [customH, setCustomH] = useState("2");
  const drawing = useRef<{ x: number; y: number } | null>(null);
  const cropStart = useRef<{ x: number; y: number } | null>(null);
  /** 进入裁剪模式时暂存的笔迹,切回时恢复 */
  const savedStrokes = useRef<{ brush: ImageData; mask: ImageData } | null>(null);

  const lockedRatio: number | null = (() => {
    if (ratioId === "free") return null;
    if (ratioId === "custom") {
      const w = Number(customW);
      const h = Number(customH);
      return w > 0 && h > 0 ? w / h : null;
    }
    return RATIO_PRESETS.find((r) => r.id === ratioId)?.value ?? null;
  })();

  // 加载底图
  useEffect(() => {
    let alive = true;
    void fetchAssetBlob(assetId).then((blob) => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        if (!alive) return;
        imageRef.current = img;
        for (const ref of [baseRef, overlayRef, maskRef]) {
          const c = ref.current;
          if (!c) continue;
          c.width = img.naturalWidth;
          c.height = img.naturalHeight;
        }
        baseRef.current?.getContext("2d")?.drawImage(img, 0, 0);
        setReady(true);
      };
      img.src = url;
    });
    return () => {
      alive = false;
    };
  }, [assetId]);

  // 裁剪模式:暂存两层笔迹 → 清空 → 画暗化遮罩与选框;切回时恢复
  useEffect(() => {
    if (!ready) return;
    const overlay = overlayRef.current;
    const mask = maskRef.current;
    const ctx = overlay?.getContext("2d");
    if (!overlay || !ctx || !mask) return;
    if (mode === "crop") {
      if (!savedStrokes.current) {
        savedStrokes.current = {
          brush: ctx.getImageData(0, 0, overlay.width, overlay.height),
          mask: mask.getContext("2d")!.getImageData(0, 0, mask.width, mask.height),
        };
      }
      ctx.clearRect(0, 0, overlay.width, overlay.height);
      mask.getContext("2d")!.clearRect(0, 0, mask.width, mask.height);
      if (crop) {
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.fillRect(0, 0, overlay.width, overlay.height);
        ctx.clearRect(crop.x, crop.y, crop.w, crop.h);
        ctx.strokeStyle = getComputedStyle(document.documentElement)
          .getPropertyValue("--primary")
          .trim() || "#7c3aed";
        ctx.lineWidth = Math.max(2, overlay.width / 400);
        ctx.strokeRect(crop.x, crop.y, crop.w, crop.h);
      }
    } else if (savedStrokes.current) {
      ctx.putImageData(savedStrokes.current.brush, 0, 0);
      mask.getContext("2d")!.putImageData(savedStrokes.current.mask, 0, 0);
      savedStrokes.current = null;
    }
  }, [mode, crop, ready]);

  // 坐标换算：canvas 实际像素 ← CSS 显示坐标
  const toCanvasPoint = (e: React.PointerEvent, canvas: HTMLCanvasElement) => {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * canvas.width,
      y: ((e.clientY - rect.top) / rect.height) * canvas.height,
    };
  };

  const activePaintCanvas = () =>
    mode === "mask" ? maskRef.current : overlayRef.current;

  const paintColor = () =>
    mode === "mask" ? "rgba(225,29,72,0.55)" : brushColor + "8c"; // 8c ≈ 55% alpha

  const onPointerDown = (e: React.PointerEvent) => {
    const target = mode === "crop" ? overlayRef.current : activePaintCanvas();
    if (!target) return;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    const p = toCanvasPoint(e, target);
    if (mode === "brush" || mode === "mask") {
      drawing.current = p;
      if (mode === "mask") setHasMaskStroke(true);
      const ctx = target.getContext("2d");
      if (!ctx) return;
      ctx.fillStyle = paintColor();
      ctx.beginPath();
      ctx.arc(p.x, p.y, brushSize / 2, 0, Math.PI * 2);
      ctx.fill();
    } else {
      cropStart.current = p;
      setCrop(null);
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (mode === "brush" || mode === "mask") {
      const canvas = activePaintCanvas();
      if (!canvas || !drawing.current) return;
      const p = toCanvasPoint(e, canvas);
      const ctx = canvas.getContext("2d");
      const last = drawing.current;
      if (!ctx) return;
      ctx.strokeStyle = paintColor();
      ctx.lineWidth = brushSize;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      drawing.current = p;
      return;
    }
    if (mode === "crop" && cropStart.current && overlayRef.current) {
      const p = toCanvasPoint(e, overlayRef.current);
      const s = cropStart.current;
      let w = Math.abs(p.x - s.x);
      let h = Math.abs(p.y - s.y);
      // 锁定比例:按主导轴推导另一轴(PS 同款手感)
      if (lockedRatio && w > 0 && h > 0) {
        if (w / lockedRatio > h) h = w / lockedRatio;
        else w = h * lockedRatio;
      }
      setCrop({
        x: p.x < s.x ? s.x - w : s.x,
        y: p.y < s.y ? s.y - h : s.y,
        w,
        h,
      });
    }
  };

  const onPointerUp = () => {
    drawing.current = null;
    cropStart.current = null;
  };

  const clearPaint = () => {
    const canvas = activePaintCanvas();
    canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    if (mode === "mask") setHasMaskStroke(false);
  };

  const upload = async (canvas: HTMLCanvasElement, name: string, hidden = false) => {
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) return null;
    const file = new File([blob], name, { type: "image/png" });
    const uploaded = await api.uploadFileAsAsset(file, "image", hidden);
    return { id: uploaded.asset_id, name: file.name };
  };

  /** 导出涂抹/裁剪后的新图(复用原逻辑:笔迹烘进新图;裁剪只取底图)。 */
  const exportImage = async (cropOnly: boolean) => {
    const base = baseRef.current;
    const overlay = overlayRef.current;
    if (!base || !overlay) return;
    setSaving(true);
    try {
      const out = document.createElement("canvas");
      const rect = cropOnly && crop && crop.w > 4 && crop.h > 4 ? crop : null;
      out.width = rect ? Math.round(rect.w) : base.width;
      out.height = rect ? Math.round(rect.h) : base.height;
      const ctx = out.getContext("2d")!;
      const sx = rect?.x ?? 0;
      const sy = rect?.y ?? 0;
      ctx.drawImage(base, sx, sy, out.width, out.height, 0, 0, out.width, out.height);
      if (!cropOnly) ctx.drawImage(overlay, sx, sy, out.width, out.height, 0, 0, out.width, out.height);
      const uploaded = await upload(out, `canvas-edit-${Date.now()}.png`);
      if (!uploaded) return;
      onApply(uploaded.id, uploaded.name, cropOnly ? "crop" : "markup");
      onClose();
    } finally {
      setSaving(false);
    }
  };

  /** 导出蒙版:蒙版层笔迹 → 白区黑底 PNG(inpaint 语义:白色重画,黑色保留)。 */
  const exportMask = async () => {
    const mask = maskRef.current;
    if (!mask || !onApplyMask) return;
    setSaving(true);
    try {
      const out = document.createElement("canvas");
      out.width = mask.width;
      out.height = mask.height;
      const ctx = out.getContext("2d")!;
      ctx.fillStyle = "#000000";
      ctx.fillRect(0, 0, out.width, out.height);
      // 笔迹任意色 → source-in 涂白
      const tint = document.createElement("canvas");
      tint.width = mask.width;
      tint.height = mask.height;
      const tctx = tint.getContext("2d")!;
      tctx.drawImage(mask, 0, 0);
      tctx.globalCompositeOperation = "source-in";
      tctx.fillStyle = "#ffffff";
      tctx.fillRect(0, 0, tint.width, tint.height);
      ctx.drawImage(tint, 0, 0);
      // 蒙版是中间产物:建档即隐藏,不进资源库视野
      const uploaded = await upload(out, `canvas-mask-${Date.now()}.png`, true);
      if (!uploaded) return;
      onApplyMask(uploaded.id, uploaded.name);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <LightboxShell onClose={onClose} ariaLabel={tx("编辑图片输入")} className="max-w-3xl">
      <div className="flex max-h-[85vh] flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
          <h3 className="mr-auto text-sm font-medium">{tx("编辑图片输入")}</h3>
          <Segmented
            ariaLabel={tx("编辑模式")}
            value={mode}
            onChange={(v) => setMode(v as Mode)}
            options={[
              { value: "brush", label: tx("标记涂抹") },
              ...(onApplyMask ? [{ value: "mask" as const, label: tx("蒙版") }] : []),
              { value: "crop", label: tx("裁剪") },
            ]}
          />
          {(mode === "brush" || mode === "mask") && (
            <>
              <div className="w-28">
                <NumberStepper
                  ariaLabel={tx("笔刷大小")}
                  min={4}
                  max={120}
                  value={brushSize}
                  onChange={setBrushSize}
                />
              </div>
              <Button variant="ghost" size="icon" className="size-8" title={tx("清除")} aria-label={tx("清除")} onClick={clearPaint}>
                <Eraser className="size-4" />
              </Button>
            </>
          )}
          <Button variant="ghost" size="icon" onClick={onClose} aria-label={tx("关闭")}>
            <X />
          </Button>
        </div>

        {/* 画笔色板:仅标记模式(蒙版语义固定白色重绘区) */}
        {mode === "brush" && (
          <div className="flex items-center gap-1.5 border-b border-border px-4 py-2">
            <span className="text-xs text-muted-foreground">{tx("颜色")}</span>
            {BRUSH_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={c}
                aria-pressed={brushColor === c}
                onClick={() => setBrushColor(c)}
                className={cn(
                  "size-6 rounded-full border border-border transition-transform",
                  brushColor === c && "scale-110 ring-2 ring-primary",
                )}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        )}
        {mode === "mask" && (
          <p className="border-b border-border px-4 py-2 text-xs text-muted-foreground">
            {tx("涂抹要重绘的区域(玫红显示,导出为白区黑底蒙版)")}
            {maskAssetId ? tx("；节点上已挂一张蒙版,导出会替换它") : ""}
          </p>
        )}
        {mode === "crop" && (
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2 text-xs">
            <span className="text-muted-foreground">{tx("比例")}</span>
            <select
              className={selectClass}
              style={{ height: "2rem" }}
              value={ratioId}
              onChange={(e) => setRatioId(e.target.value)}
              aria-label={tx("裁剪比例")}
            >
              {RATIO_PRESETS.map((r) => (
                <option key={r.id} value={r.id}>
                  {tx(r.label)}
                </option>
              ))}
            </select>
            {ratioId === "custom" && (
              <span className="flex items-center gap-1 text-muted-foreground">
                <input
                  className="w-12 rounded-md border border-border bg-field px-1.5 py-1 text-xs"
                  value={customW}
                  onChange={(e) => setCustomW(e.target.value.replace(/[^0-9]/g, ""))}
                  aria-label={tx("比例宽")}
                />
                :
                <input
                  className="w-12 rounded-md border border-border bg-field px-1.5 py-1 text-xs"
                  value={customH}
                  onChange={(e) => setCustomH(e.target.value.replace(/[^0-9]/g, ""))}
                  aria-label={tx("比例高")}
                />
              </span>
            )}
            {crop && crop.w > 4 && (
              <span className="ml-auto tabular-nums text-muted-foreground">
                {Math.round(crop.w)}×{Math.round(crop.h)} px · {simpleRatio(crop.w, crop.h)}
              </span>
            )}
          </div>
        )}

        <div className="relative flex-1 overflow-auto p-4">
          {!ready && <p className="text-sm text-muted-foreground">{tx("加载图片…")}</p>}
          <div
            className="relative mx-auto w-fit touch-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            style={{ cursor: mode === "crop" ? "cell" : "crosshair" }}
          >
            <canvas ref={baseRef} className="max-h-[55vh] max-w-full rounded-lg" />
            <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full rounded-lg" />
            <canvas ref={maskRef} className="pointer-events-none absolute inset-0 h-full w-full rounded-lg" />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
          {mode === "crop" ? (
            <Button
              size="sm"
              disabled={!ready || saving || !crop || crop.w < 8 || crop.h < 8}
              onClick={() => void exportImage(true)}
            >
              <Crop className="size-4" />
              {tx("导出裁剪区域")}
            </Button>
          ) : mode === "mask" ? (
            <Button size="sm" disabled={!ready || saving || !hasMaskStroke} onClick={() => void exportMask()}>
              <Paintbrush className="size-4" />
              {tx("导出蒙版")}
            </Button>
          ) : (
            <Button size="sm" disabled={!ready || saving} onClick={() => void exportImage(false)}>
              <Paintbrush className="size-4" />
              {tx("导出涂抹后的新图")}
            </Button>
          )}
        </div>
      </div>
    </LightboxShell>
  );
}
