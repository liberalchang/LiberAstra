/** 画布右上工具坞：命名、保存、执行。 */
import { Loader2, Play, Save } from "lucide-react";
import { Panel } from "@xyflow/react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTx } from "@/i18n/tx";
import { useCanvasStore } from "@/stores/canvas";

export function CanvasDock({
  saving,
  running,
  onSave,
  onRun,
}: {
  saving: boolean;
  running: boolean;
  onSave: () => void;
  onRun: () => void;
}) {
  const tx = useTx();
  const name = useCanvasStore((s) => s.name);
  const setName = useCanvasStore((s) => s.setName);
  const dirty = useCanvasStore((s) => s.dirty);
  const selectedCount = useCanvasStore((s) => s.nodes.filter((n) => n.selected).length);

  return (
    <Panel position="top-right" className="flex items-center gap-2">
      <Input
        className="h-8 w-44 bg-card/95 text-sm"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={tx("画布名称")}
      />
      <Button
        variant="outline"
        size="sm"
        className="bg-card/95"
        onClick={onSave}
        disabled={saving}
        title={tx("保存画布（Ctrl+S）")}
      >
        {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
        {dirty ? tx("保存 *") : tx("保存")}
      </Button>
      <Button
        size="sm"
        onClick={onRun}
        disabled={running}
        title={
          selectedCount > 0
            ? tx("重跑选中节点（上游能复用则复用）")
            : tx("强制重跑整张画布（全部节点忽略缓存，需确认）")
        }
      >
        {running ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
        {selectedCount > 0 ? tx("执行选中") : tx("执行")}
      </Button>
    </Panel>
  );
}
