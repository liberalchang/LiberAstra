import { Workflow } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileUp, Pencil, Trash2, WandSparkles, X } from "lucide-react";
import { useRef, useState } from "react";

import { api, type WorkflowPackBundle, type WorkflowPackOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useTx } from "@/i18n/tx";

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

/** 粗判是否为 ComfyUI 画布格式（含 nodes 数组）。 */
function looksLikeCanvas(data: unknown): boolean {
  if (!data || typeof data !== "object") return false;
  const obj = data as Record<string, unknown>;
  if (obj.workflow && typeof obj.workflow === "object") return false;
  return Array.isArray(obj.nodes) && obj.nodes.length > 0;
}

export function WorkflowsPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const { data: packs } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [capability, setCapability] = useState("t2i");
  const [description, setDescription] = useState("");
  const [llmNote, setLlmNote] = useState("");
  const [workflowJson, setWorkflowJson] = useState("");
  const [inputsJson, setInputsJson] = useState("");
  const [outputsJson, setOutputsJson] = useState(DEFAULT_OUTPUTS);
  const [fps, setFps] = useState<number | "">("");
  const [accelJson, setAccelJson] = useState("");
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
    setLlmNote("");
    setWorkflowJson("");
    setInputsJson("");
    setOutputsJson(DEFAULT_OUTPUTS);
    setFps("");
    setAccelJson("");
  };

  /** 把转换结果填进表单。 */
  const applyConvertResult = (
    result: Awaited<ReturnType<typeof api.convertWorkflow>>,
    opts?: { packName?: string; fileName?: string },
  ) => {
    setEditing(null);
    if (opts?.packName) setName(opts.packName);
    else if (opts?.fileName && !name) setName(nameFromFile(opts.fileName));
    setCapability(result.capability || "t2i");
    setDescription(result.description || "");
    setWorkflowJson(JSON.stringify(result.workflow, null, 2));
    setInputsJson(JSON.stringify(result.inputs ?? {}, null, 2));
    setOutputsJson(JSON.stringify(result.outputs ?? {}, null, 2));
    setFps(result.fps ?? "");
    setAccelJson(
      result.accel && Object.keys(result.accel).length > 0
        ? JSON.stringify(result.accel, null, 2)
        : "",
    );
    const tips = [
      ...(result.warnings ?? []),
      tx("节点 {n} 个", { n: result.node_count }),
      result.node_types?.length
        ? tx("类型：{list}", {
            list: `${result.node_types.slice(0, 8).join("、")}${result.node_types.length > 8 ? "…" : ""}`,
          })
        : "",
    ].filter(Boolean);
    setNotice(tips.join(" · "));
    setError(null);
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const convertMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.convertWorkflow(data),
    onSuccess: (result) => applyConvertResult(result),
    onError: (err) => {
      setError(err.message);
      setNotice(null);
    },
  });

  const savePack = useMutation({
    mutationFn: () => {
      let workflow: unknown, inputs: unknown, outputs: unknown, accel: unknown;
      try {
        workflow = JSON.parse(workflowJson);
        inputs = inputsJson ? JSON.parse(inputsJson) : {};
        outputs = outputsJson ? JSON.parse(outputsJson) : {};
        accel = accelJson.trim() ? JSON.parse(accelJson) : undefined;
      } catch (e) {
        throw new Error(tx("JSON 解析失败: {err}", { err: (e as Error).message }));
      }
      const body: Record<string, unknown> = {
        name,
        capability,
        description,
        llm_note: llmNote,
        workflow,
        inputs,
        outputs,
      };
      if (fps !== "" && Number.isFinite(Number(fps))) body.fps = Number(fps);
      if (accel !== undefined) body.accel = accel;
      return editing ? api.updateWorkflow(editing, body) : api.importWorkflow(body);
    },
    onSuccess: (pack) => {
      setNotice(editing ? tx("已保存 {name}", { name: pack.name }) : tx("已导入 {name}", { name: pack.name }));
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
      setNotice(tx("已删除"));
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
    onSuccess: () => setNotice(tx("已导出")),
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
      setLlmNote(typeof bundle.llm_note === "string" ? bundle.llm_note : "");
      setWorkflowJson(JSON.stringify(bundle.workflow, null, 2));
      setInputsJson(JSON.stringify(bundle.inputs, null, 2));
      setOutputsJson(JSON.stringify(bundle.outputs, null, 2));
      setFps(bundle.fps ?? "");
      setAccelJson(
        bundle.accel && Object.keys(bundle.accel).length > 0
          ? JSON.stringify(bundle.accel, null, 2)
          : "",
      );
      setError(null);
      setNotice(null);
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    onError: (err) => setError(err.message),
  });

  /** 导入 JSON：完整包直接填表；画布/API 走后端转换。 */
  const handleFile = async (file: File) => {
    try {
      const data = JSON.parse(await file.text()) as Record<string, unknown>;
      if (data && typeof data === "object" && data.workflow && typeof data.workflow === "object") {
        setEditing(null);
        setName(typeof data.name === "string" ? data.name : nameFromFile(file.name));
        setCapability(typeof data.capability === "string" ? data.capability : "t2i");
        setDescription(typeof data.description === "string" ? data.description : "");
        setWorkflowJson(JSON.stringify(data.workflow, null, 2));
        setInputsJson(JSON.stringify(data.inputs ?? {}, null, 2));
        setOutputsJson(JSON.stringify(data.outputs ?? {}, null, 2));
        setFps(typeof data.fps === "number" ? data.fps : "");
        setAccelJson(
          data.accel && typeof data.accel === "object" && Object.keys(data.accel as object).length > 0
            ? JSON.stringify(data.accel, null, 2)
            : "",
        );
        setNotice(tx("已从 {file} 读取完整工作流包，确认后点击导入", { file: file.name }));
        setError(null);
        return;
      }
      // 画布或 API Format → 后端转换 + 启发式 manifest
      setNotice(tx("正在转换 {file}…", { file: file.name }));
      const result = await api.convertWorkflow(data);
      applyConvertResult(result, {
        packName: nameFromFile(file.name) || undefined,
        fileName: file.name,
      });
    } catch (e) {
      setError(tx("文件处理失败: {err}", { err: (e as Error).message }));
      setNotice(null);
    }
  };

  /** 把文本框里的 JSON（画布或 API）提交转换。 */
  const convertFromTextarea = async () => {
    try {
      const data = JSON.parse(workflowJson) as Record<string, unknown>;
      setNotice(tx("正在转换…"));
      await convertMut.mutateAsync(data); // onSuccess 填表
    } catch {
      // onError 已处理
    }
  };

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <PageHeader
        kind="workflow"
        icon={Workflow}
        title={tx("工作流包")}
        description={tx("支持 LiberAstra 包、ComfyUI API Format，以及画布 JSON（自动转换）。")}
      />

      <div className="flex flex-col gap-3">
        {packs?.map((p) => (
          <Card key={`${p.source}-${p.name}`}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{p.name}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{p.capability}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {p.source === "builtin" ? tx("内置") : tx("用户")}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground">{p.description}</div>
                <div className="text-xs text-muted-foreground">
                  参数：{Object.keys(p.inputs).join("、") || tx("无")}
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => exportPack.mutate(p)}
                disabled={exportPack.isPending}
                title={tx("导出为 JSON 文件")}
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
                    title={tx("编辑")}
                  >
                    <Pencil />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      if (window.confirm(tx("确定删除工作流包 {name}？", { name: p.name }))) remove.mutate(p.name);
                    }}
                    title={tx("删除")}
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
                <CardTitle>{editing ? `编辑工作流包：${editing}` : tx("导入工作流包")}</CardTitle>
                <CardDescription>
                  {editing
                    ? tx("修改后点击保存。包名不可更改；如需改名请导出后重新导入。")
                    : tx("可导入 LiberAstra 包、ComfyUI「Save (API Format)」，或画布工作流 JSON（含 nodes/links，会自动转成 API Format 并生成参数草稿）。")}
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
                    {tx('导入 JSON 文件')}
                  </Button>
                </>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={tx("包名")} hint={editing ? tx("编辑时包名不可更改。") : tx("只用字母、数字、横线和下划线。")}>
                <Input value={name} onChange={(e) => setName(e.target.value)} disabled={!!editing} />
              </Field>
              <Field label={tx("能力")} hint={tx("决定这个包会出现在哪个功能页（转换时会猜测，可改）。")}>
                <select
                  className={selectClass}
                  value={capability}
                  onChange={(e) => setCapability(e.target.value)}
                >
                  <option value="t2i">{tx("t2i 文生图")}</option>
                  <option value="i2i">{tx("i2i 图生图")}</option>
                  <option value="upscale">{tx("upscale 修复放大")}</option>
                  <option value="t2v">{tx("t2v 文生视频")}</option>
                  <option value="i2v">{tx("i2v 图生视频")}</option>
                  <option value="avatar">{tx("avatar 数字人")}</option>
                  <option value="motion">{tx("motion 动作迁移")}</option>
                  <option value="tts">{tx("tts 语音")}</option>
                  <option value="analysis">{tx("analysis 素材分析")}</option>
                </select>
              </Field>
            </div>
            <Field label={tx("描述")} hint={tx("一句话说明这个包做什么，会显示在包列表与提示里。")}>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
            <Field
              label={tx("优化器说明")}
              hint={tx("给提示词优化器读的技术细节（模型约束、时长上限、指代规则等）；用户提示只显示上面的描述。留空则优化器读描述。")}
            >
              <textarea
                className={`${areaClass} min-h-20`}
                value={llmNote}
                onChange={(e) => setLlmNote(e.target.value)}
                placeholder={tx("例:输出带同步音效,提示词需包含环境音/对白描写;单段最长约 5 秒。")}
              />
            </Field>
            <Field
              label="workflow.json"
              hint={tx("粘贴画布或 API Format 后，可点「转换画布/API」；或直接用右上角导入文件（画布会自动转换）。")}
            >
              <textarea
                className={`${areaClass} min-h-40 font-mono text-xs`}
                value={workflowJson}
                onChange={(e) => setWorkflowJson(e.target.value)}
              />
            </Field>
            {!editing && workflowJson.trim() && (
              <Button
                type="button"
                variant="outline"
                className="w-fit gap-1.5"
                disabled={convertMut.isPending}
                onClick={() => void convertFromTextarea()}
              >
                <WandSparkles className="size-4" />
                {convertMut.isPending
                  ? tx("转换中…")
                  : looksLikeCanvas(safeParse(workflowJson))
                    ? tx("转换画布 JSON")
                    : tx("从当前 JSON 生成参数草稿")}
              </Button>
            )}
            <Field label={tx("参数映射")} hint={tx("声明页面参数对应哪个节点。画布转换会预填草稿，请核对 node / field。")}>
              <textarea
                className={`${areaClass} min-h-32 font-mono text-xs`}
                placeholder={INPUTS_PLACEHOLDER}
                value={inputsJson}
                onChange={(e) => setInputsJson(e.target.value)}
              />
            </Field>
            <Field label={tx("输出节点")} hint={tx("例如 node 与 key；可含 texts 列表。")}>
              <Input value={outputsJson} onChange={(e) => setOutputsJson(e.target.value)} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={tx("帧率 fps")} hint={tx("视频包可选；有值时前端可按秒设时长。留空表示无。")}>
                <Input
                  type="number"
                  min={1}
                  max={60}
                  value={fps}
                  onChange={(e) => setFps(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder={tx("例如 24")}
                />
              </Field>
            </div>
            <Field
              label={tx("加速 accel（可选）")}
              hint={tx("Turbo LoRA 声明。空=无加速。示例含 node / bypass_input / lora / preset。")}
            >
              <textarea
                className={`${areaClass} min-h-24 font-mono text-xs`}
                placeholder={`{\n  "node": "105:200",\n  "bypass_input": "model",\n  "lora": { "field": "inputs.lora_name", "match": "minimax_h3" }\n}`}
                value={accelJson}
                onChange={(e) => setAccelJson(e.target.value)}
              />
            </Field>
            {error && <p className="text-sm text-danger">{error}</p>}
            {notice && <p className="text-sm text-success">{notice}</p>}
            <div className="flex items-center gap-2">
              <Button
                className="w-fit"
                onClick={() => savePack.mutate()}
                disabled={!name || !workflowJson || savePack.isPending}
              >
                {editing ? tx("保存修改") : tx("导入")}
              </Button>
              {editing && (
                <Button variant="ghost" className="w-fit gap-1.5" onClick={resetForm}>
                  <X className="size-4" />
                  {tx('取消编辑')}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
