import { Upload } from "lucide-react";
import { useRef, useState } from "react";

import { filterAcceptedFiles } from "@/lib/fileAccept";
import { cn } from "@/lib/utils";

interface FileDropProps {
  accept?: string;
  multiple?: boolean;
  /** 已选文件名（展示用） */
  names?: string[];
  title: string;
  subtitle?: string;
  disabled?: boolean;
  /** 始终传稳定的 File[] 快照，避免 FileList 被清空后变空 */
  onSelect: (files: File[] | null) => void;
  /** 选择后清空原生 input，允许再次选择同一文件 */
  clearAfterSelect?: boolean;
}

/** 上传拖放区：虚线框 + 图标，点击或拖拽选择文件，替代原生 file input。 */
export function FileDrop({ accept, multiple, names, title, subtitle, disabled = false, onSelect, clearAfterSelect }: FileDropProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);

  const select = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length === 0) return;
    const result = filterAcceptedFiles(files, accept);
    setRejected(result.rejected.map((file) => file.name));
    if (result.accepted.length > 0) onSelect(result.accepted);
  };

  return (
    <div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (!disabled) select(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-field/50 px-4 py-6 text-center transition-colors hover:border-primary/50 hover:bg-field",
          dragOver && "border-primary bg-primary/5",
          disabled && "cursor-not-allowed opacity-50 hover:border-border hover:bg-field/50",
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
      {rejected.length > 0 && (
        <p role="alert" className="mt-1 text-xs text-danger">
          不支持的文件类型：{rejected.join("、")}
        </p>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        className="hidden"
        onChange={(e) => {
          select(e.target.files);
          if (clearAfterSelect) e.target.value = "";
        }}
      />
    </div>
  );
}
