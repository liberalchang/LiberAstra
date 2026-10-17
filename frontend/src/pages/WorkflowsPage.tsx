import { Workflow } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileUp, Pencil, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";

import { api, type WorkflowPackBundle, type WorkflowPackOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const INPUTS_PLACEHOLDER = `{
  "prompt": { "node": "6", "field": "inputs.text", "type": "str", "required": true },
  "seed": { "node": "3", "field": "inputs.seed", "type": "int", "default": -1 }
}`;

const DEFAULT_OUTPUTS = '{ "node": "9", "key": "images" }';

/** 从文件名推导合法包名（字母、数字、横线、下划线）。 */
function nameFromFile(fileName: string): string {
  const base = fileName
    .replace(/\.workflow\.json$/i, "")
    .replace(/\.json$/i, "")
    .replace(/[^A-Za-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return base;
}

export function WorkflowsPage() {
  const queryClient = useQueryClient();
  const { data: packs } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [capability, setCapability] = useState("t2i");
  const [description, setDescription] = useState("");
  const [workflowJson, setWorkflowJson] = useState("");
  const [inputsJson, setInputsJson] = useState("");
  const [outputsJson, setOutputsJson] = useState(DEFAULT_OUTPUTS);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLDivElement>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workflows"] });

  const resetForm = () => {
    setEditing(null);
    setName("");
    setCapability("t2i");
    setDescription("");
    setWorkflowJson("");
    setInputsJson("");
    setOutputsJson(DEFAULT_OUTPUTS);
  };

  const savePack = useMutation({
    mutationFn: () => {
      let workflow: unknown, inputs: unknown, outputs: unknown;
      try {
        workflow = JSON.parse(workflowJson);
        inputs = inputsJson ? JSON.parse(inputsJson) : {};
        outputs = outputsJson ? JSON.parse(outputsJson) : {};
      } catch (e) {
        throw new Error(`JSON 解析失败: ${(e as Error).message}`);
      }
      const body = { name, capability, description, workflow, inputs, outputs };
      return editing ? api.updateWorkflow(editing, body) : api.importWorkflow(body);
    },
    onSuccess: (pack) => {
      setNotice(editing ? `已保存 ${pack.name}` : `已导入 ${pack.name}`);
      setError(null);
      resetForm();
      invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
    },
  });

  const remove = useMutation({
    mutationFn: (n: string) => api.deleteWorkflow(n),
    onSuccess: () => {
      setNotice("已删除");
      invalidate();
    },
    onError: (err) => setError(err.message),
  });

  const exportPack = useMutation({
    mutationFn: async (p: WorkflowPackOut) => {
      const bundle = await api.exportWorkflow(p.name);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${p.name}.workflow.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
    onSuccess: () => setNotice("已导出"),
    onError: (err) => setError(err.message),
  });

  /** 编辑：拉取完整包（含 workflow JSON）载入表单。 */
  const startEdit = useMutation({
    mutationFn: (n: string) => api.exportWorkflow(n),
    onSuccess: (bundle: WorkflowPackBundle) => {
      setEditing(bundle.name);
      setName(bundle.name);
      setCapability(bundle.capability);
      setDescription(bundle.description);
      setWorkflowJson(JSON.stringify(bundle.workflow, null, 2));
      setInputsJson(JSON.stringify(bundle.inputs, null, 2));
      setOutputsJson(JSON.stringify(bundle.outputs, null, 2));
      setError(null);
      setNotice(null);
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    onError: (err) => setError(err.message),
  });

  /** 导入 JSON 文件：完整包（含 workflow 字段）自动填充全部表单；否则按 ComfyUI API JSON 处理。 */
  const handleFile = async (file: File) => {
    try {
      const data = JSON.parse(await file.text());
      if (data && typeof data === "object" && data.workflow && typeof data.workflow === "object") {
        setEditing(null);
        setName(typeof data.name === "string" ? data.name : nameFromFile(file.name));
        setCapability(typeof data.capability === "string" ? data.capability : "t2i");
        setDescription(typeof data.description === "string" ? data.description : "");
        setWorkflowJson(JSON.stringify(data.workflow, null, 2));
        setInputsJson(JSON.stringify(data.inputs ?? {}, null, 2));
        setOutputsJson(JSON.stringify(data.outputs ?? {}, null, 2));
        setNotice(`已从 ${file.name} 读取完整工作流包，确认后点击导入`);
      } else {
        setWorkflowJson(JSON.stringify(data, null, 2));
        if (!name) setName(nameFromFile(file.name));
        setNotice(`已从 ${file.name} 读取 workflow.json，请补充参数映射后导入`);
      }
      setError(null);
    } catch (e) {
      setError(`文件解析失败: ${(e as Error).message}`);
      setNotice(null);
    }
  };

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <PageHeader kind="workflow" icon={Workflow} title="工作流包" description="导入 ComfyUI API JSON，勾选参数后试运行。" />

      <div className="flex flex-col gap-3">
        {packs?.map((p) => (
          <Card key={`${p.source}-${p.name}`}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{p.name}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{p.capability}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {p.source === "builtin" ? "内置" : "用户"}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground">{p.description}</div>
                <div className="text-xs text-muted-foreground">
                  参数：{Object.keys(p.inputs).join("、") || "无"}
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => exportPack.mutate(p)}
                disabled={exportPack.isPending}
                title="导出为 JSON 文件"
              >
                <Download />
              </Button>
              {p.source === "user" && (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => startEdit.mutate(p.name)}
                    disabled={startEdit.isPending}
                    title="编辑"
                  >
                    <Pencil />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      if (window.confirm(`确定删除工作流包 ${p.name}？`)) remove.mutate(p.name);
                    }}
                    title="删除"
                  >
                    <Trash2 />
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div ref={formRef} className="scroll-mt-4">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1.5">
              <CardTitle>{editing ? `编辑工作流包：${editing}` : "导入工作流包"}</CardTitle>
              <CardDescription>
                {editing
                  ? "修改后点击保存。包名不可更改；如需改名请导出后重新导入。"
                  : "选择 JSON 文件或粘贴 ComfyUI 的 API Format JSON，并用 manifest 声明参数到节点的映射（JSON 是合法 YAML）。"}
              </CardDescription>
            </div>
            {!editing && (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".json,application/json"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void handleFile(file);
                    e.target.value = "";
                  }}
                />
                <Button variant="outline" className="shrink-0 gap-1.5" onClick={() => fileRef.current?.click()}>
                  <FileUp className="size-4" />
                  导入 JSON 文件
                </Button>
              </>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="包名" hint={editing ? "编辑时包名不可更改。" : "只用字母、数字、横线和下划线。"}>
              <Input value={name} onChange={(e) => setName(e.target.value)} disabled={!!editing} />
            </Field>
            <Field label="能力" hint="决定这个包会出现在哪个功能页。">
              <select
                className={selectClass}
                value={capability}
                onChange={(e) => setCapability(e.target.value)}
              >
                <option value="t2i">t2i 文生图</option>
                <option value="i2i">i2i 图生图</option>
                <option value="upscale">upscale 修复放大</option>
                <option value="t2v">t2v 文生视频</option>
                <option value="i2v">i2v 图生视频</option>
                <option value="avatar">avatar 数字人</option>
                <option value="motion">motion 动作迁移</option>
                <option value="tts">tts 语音</option>
              </select>
            </Field>
          </div>
          <Field label="描述" hint="一句话说明这个包做什么，会显示在包列表里。">
            <Input value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label="workflow.json" hint="在 ComfyUI 里用 Save (API Format) 导出后粘贴到这里，或点右上角导入文件。">
            <textarea
              className={`${areaClass} min-h-40 font-mono text-xs`}
              value={workflowJson}
              onChange={(e) => setWorkflowJson(e.target.value)}
            />
          </Field>
          <Field label="参数映射" hint="声明页面上的参数对应工作流里的哪个节点。JSON 也可以写成 YAML。">
            <textarea
              className={`${areaClass} min-h-32 font-mono text-xs`}
              placeholder={INPUTS_PLACEHOLDER}
              value={inputsJson}
              onChange={(e) => setInputsJson(e.target.value)}
            />
          </Field>
          <Field label="输出节点" hint='例如 { "node": "9", "key": "images" }，告诉系统从哪取出结果。'>
            <Input
              value={outputsJson}
              onChange={(e) => setOutputsJson(e.target.value)}
            />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
          {notice && <p className="text-sm text-green-600">{notice}</p>}
          <div className="flex items-center gap-2">
            <Button
              className="w-fit"
              onClick={() => savePack.mutate()}
              disabled={!name || !workflowJson || savePack.isPending}
            >
              {editing ? "保存修改" : "导入"}
            </Button>
            {editing && (
              <Button variant="ghost" className="w-fit gap-1.5" onClick={resetForm}>
                <X className="size-4" />
                取消编辑
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
      </div>
    </div>
  );
}
