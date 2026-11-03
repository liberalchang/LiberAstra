/** 本地图片预览条：缩略图 + 角标 + 悬停删除，和图片编辑页保持一致。 */
import { X } from "lucide-react";
import { useEffect, useMemo } from "react";

import { useTx } from "@/i18n/tx";

export function ImagePreviewStrip({
  files,
  onRemove,
  labelFor,
  className,
}: {
  files: File[];
  onRemove: (index: number) => void;
  labelFor?: (file: File, index: number) => string | undefined;
  className?: string;
}) {
  const tx = useTx();
  const previews = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  if (files.length === 0) return null;

  return (
    <div className={`mt-2 flex gap-2 overflow-x-auto pb-1 ${className ?? ""}`}>
      {files.map((file, index) => {
        const label = labelFor?.(file, index);
        return (
          <div
            key={`${file.name}:${file.size}:${file.lastModified}`}
            className="group relative size-20 shrink-0 overflow-hidden rounded-lg border border-border bg-muted"
          >
            <img src={previews[index]} alt={file.name} className="size-full object-cover" />
            {label && (
              <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[10px] leading-none text-white">
                {label}
              </span>
            )}
            <button
              type="button"
              onClick={() => onRemove(index)}
              title={tx("移除 {name}", { name: file.name })}
              className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-black/60 text-white opacity-0 transition-opacity hover:bg-danger group-hover:opacity-100"
            >
              <X className="size-3" />
            </button>
            <span className="absolute inset-x-0 bottom-0 truncate bg-black/50 px-1 py-0.5 text-[10px] leading-none text-white">
              {file.name}
            </span>
          </div>
        );
      })}
    </div>
  );
}
