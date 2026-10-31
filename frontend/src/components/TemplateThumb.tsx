import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { fetchTemplatePreview } from "@/api/client";
import { useInView } from "@/components/MediaLightbox";
import { useTx } from "@/i18n/tx";
import { cn } from "@/lib/utils";

async function blobToDataUri(blob: Blob): Promise<string> {
  // data URI 不受 revokeObjectURL/组件卸载影响（StrictMode 双挂载下 blob: 会被提前吊销）
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** 模板预览缩略图：进入视口后拉取后端缓存的 WebP，转 data URI 展示。 */
export function TemplateThumb({
  aspect,
  name,
  className,
}: {
  aspect: string;
  name: string;
  className?: string;
}) {
  const tx = useTx();
  const { ref, visible } = useInView();
  const { data, isError } = useQuery({
    queryKey: ["template-preview", aspect, name],
    queryFn: () => fetchTemplatePreview(aspect, name),
    enabled: visible,
    staleTime: 300_000,
    retry: false,
  });
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    if (data) {
      blobToDataUri(data).then((uri) => {
        if (alive) setSrc(uri);
      });
    }
    return () => {
      alive = false;
    };
  }, [data]);

  if (!src) {
    return (
      <div
        ref={ref}
        className={cn(
          "grid place-items-center bg-muted text-xs text-muted-foreground",
          className,
        )}
      >
        {visible ? (isError ? tx("预览不可用") : tx("渲染中…")) : null}
      </div>
    );
  }
  return <img ref={ref} src={src} alt={name} className={cn("object-cover", className)} />;
}
