import { Upload } from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface FileDropProps {
  accept?: string;
  multiple?: boolean;
  /** 已选文件名（展示用） */
  names?: string[];
  title: string;
  subtitle?: string;
  onSelect: (files: FileList | null) => void;
  /** 选择后清空原生 input，允许再次选择同一文件（父组件需自行保存 File 快照） */
  clearAfterSelect?: boolean;
}

/** 上传拖放区：虚线框 + 图标，点击或拖拽选择文件，替代原生 file input。 */
export function FileDrop({ accept, multiple, names, title, subtitle, onSelect, clearAfterSelect }: FileDropProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          onSelect(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-field/50 px-4 py-6 text-center transition-colors hover:border-primary/50 hover:bg-field",
          dragOver && "border-primary bg-primary/5",
        )}
      >
        <span className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
          <Upload className="size-5" />
        </span>
        <span className="text-sm font-medium text-foreground">{title}</span>
        {subtitle && <span className="text-xs text-muted-foreground">{subtitle}</span>}
        {names && names.length > 0 && (
          <span className="mt-1 max-w-full truncate rounded-md bg-muted px-2 py-1 text-xs text-foreground">
            {names.join("、")}
          </span>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => {
          onSelect(e.target.files);
          // 清空 value 后才能再次选择同一文件并触发 onChange；
          // FileList 是活引用，父组件必须在 onSelect 里先取出 File 快照
          if (clearAfterSelect) e.target.value = "";
        }}
      />
    </div>
  );
}
