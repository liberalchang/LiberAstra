/** 图像输入编辑器：画笔涂抹 + 裁剪。双层 canvas（底图 + 涂抹层）,
 * 导出合成新图上传建档,节点改引用新资产。纯前端实现,不涉及 inpaint 蒙版语义。
 */
import { Crop, Eraser, Paintbrush, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api, fetchAssetBlob } from "@/api/client";
import { Button } from "@/components/ui/button";
import { NumberStepper } from "@/components/ui/number-stepper";
import { Segmented } from "@/components/ui/segmented";
import { useTx } from "@/i18n/tx";

type Mode = "brush" | "crop";

interface CropRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function ImagePaintEditor({
  assetId,
  onApply,
  onClose,
}: {
  assetId: number;
  /** 导出新图并上传建档后回调（新 assetId） */
  onApply: (assetId: number, name: string) => void;
  onClose: () => void;
}) {
  const tx = useTx();
  const baseRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<Mode>("brush");
  const [brushSize, setBrushSize] = useState(24);
  const [crop, setCrop] = useState<CropRect | null>(null);
  const [saving, setSaving] = useState(false);
  const drawing = useRef<{ x: number; y: number } | null>(null);
  const cropStart = useRef<{ x: number; y: number } | null>(null);
  /** 进入裁剪模式时暂存的画笔笔迹,切回画笔模式恢复 */
  const savedStrokes = useRef<ImageData | null>(null);

  // 加载底图
  useEffect(() => {
    let alive = true;
    void fetchAssetBlob(assetId).then((blob) => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        if (!alive) return;
        imageRef.current = img;
        const base = baseRef.current;
        const overlay = overlayRef.current;
        if (!base || !overlay) return;
        base.width = overlay.width = img.naturalWidth;
        base.height = overlay.height = img.naturalHeight;
        base.getContext("2d")?.drawImage(img, 0, 0);
        setReady(true);
      };
      img.src = url;
    });
    return () => {
      alive = false;
    };
  }, [assetId]);

  // 裁剪模式：暂存笔迹 → 清空叠加层 → 画暗化遮罩与选框；画笔模式：恢复笔迹
  useEffect(() => {
    if (!ready) return;
    const overlay = overlayRef.current;
    const ctx = overlay?.getContext("2d");
    if (!overlay || !ctx) return;
    if (mode === "crop") {
      if (!savedStrokes.current) {
        savedStrokes.current = ctx.getImageData(0, 0, overlay.width, overlay.height);
      }
      ctx.clearRect(0, 0, overlay.width, overlay.height);
      if (crop) {
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.fillRect(0, 0, overlay.width, overlay.height);
        ctx.clearRect(crop.x, crop.y, crop.w, crop.h);
        ctx.strokeStyle = "#6d28d9";
        ctx.lineWidth = Math.max(2, overlay.width / 400);
        ctx.strokeRect(crop.x, crop.y, crop.w, crop.h);
      }
    } else if (savedStrokes.current) {
      ctx.putImageData(savedStrokes.current, 0, 0);
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

  const onPointerDown = (e: React.PointerEvent) => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    overlay.setPointerCapture(e.pointerId);
    const p = toCanvasPoint(e, overlay);
    if (mode === "brush") {
      drawing.current = p;
      const ctx = overlay.getContext("2d");
      if (!ctx) return;
      ctx.fillStyle = "rgba(225,29,72,0.55)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, brushSize / 2, 0, Math.PI * 2);
      ctx.fill();
    } else {
      cropStart.current = p;
      setCrop(null);
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    const p = toCanvasPoint(e, overlay);
    if (mode === "brush" && drawing.current) {
      const ctx = overlay.getContext("2d");
      const last = drawing.current;
      if (!ctx) return;
      ctx.strokeStyle = "rgba(225,29,72,0.55)";
      ctx.lineWidth = brushSize;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      drawing.current = p;
    } else if (mode === "crop" && cropStart.current) {
      const s = cropStart.current;
      setCrop({
        x: Math.min(s.x, p.x),
        y: Math.min(s.y, p.y),
        w: Math.abs(p.x - s.x),
        h: Math.abs(p.y - s.y),
      });
    }
  };

  const onPointerUp = () => {
    drawing.current = null;
    cropStart.current = null;
  };

  const clearBrush = () => {
    const overlay = overlayRef.current;
    overlay?.getContext("2d")?.clearRect(0, 0, overlay.width, overlay.height);
  };

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
      // 涂抹导出：把笔迹烘进新图；裁剪导出：只取底图区域（不带裁剪遮罩）
      if (!cropOnly) ctx.drawImage(overlay, sx, sy, out.width, out.height, 0, 0, out.width, out.height);
      const blob = await new Promise<Blob | null>((resolve) => out.toBlob(resolve, "image/png"));
      if (!blob) return;
      const file = new File([blob], `canvas-edit-${Date.now()}.png`, { type: "image/png" });
      const uploaded = await api.uploadFileAsAsset(file, "image");
      onApply(uploaded.asset_id, file.name);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-2xl border border-border bg-card shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
          <h3 className="mr-auto text-sm font-medium">{tx("编辑图片输入")}</h3>
          <Segmented
            ariaLabel={tx("编辑模式")}
            value={mode}
            onChange={(v) => setMode(v as Mode)}
            options={[
              { value: "brush", label: tx("画笔涂抹") },
              { value: "crop", label: tx("裁剪") },
            ]}
          />
          {mode === "brush" && (
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
              <Button variant="ghost" size="icon" className="size-7" title={tx("清除涂抹")} onClick={clearBrush}>
                <Eraser className="size-4" />
              </Button>
            </>
          )}
          <Button variant="ghost" size="icon" className="size-7" onClick={onClose} aria-label={tx("关闭")}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="relative flex-1 overflow-auto p-4">
          {!ready && <p className="text-sm text-muted-foreground">{tx("加载图片…")}</p>}
          <div className="relative mx-auto w-fit">
            <canvas ref={baseRef} className="max-h-[55vh] max-w-full rounded-lg" />
            <canvas
              ref={overlayRef}
              className="absolute inset-0 h-full w-full touch-none rounded-lg"
              style={{ cursor: mode === "brush" ? "crosshair" : "cell" }}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
            />
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
          {mode === "brush" ? (
            <Button size="sm" disabled={!ready || saving} onClick={() => void exportImage(false)}>
              <Paintbrush className="size-4" />
              {tx("导出涂抹后的新图")}
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={!ready || saving || !crop || crop.w < 8 || crop.h < 8}
              onClick={() => void exportImage(true)}
            >
              <Crop className="size-4" />
              {tx("导出裁剪区域")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
