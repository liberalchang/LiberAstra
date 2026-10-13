import { Workflow } from "lucide-react";
import { PageHeader } from "@/components/PageShell";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, areaClass, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const INPUTS_PLACEHOLDER = `{
  "prompt": { "node": "6", "field": "inputs.text", "type": "str", "required": true },
  "seed": { "node": "3", "field": "inputs.seed", "type": "int", "default": -1 }
}`;

export function WorkflowsPage() {
  const queryClient = useQueryClient();
  const { data: packs } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });

  const [name, setName] = useState("");
  const [capability, setCapability] = useState("t2i");
  const [workflowJson, setWorkflowJson] = useState("");
  const [inputsJson, setInputsJson] = useState("");
  const [outputsJson, setOutputsJson] = useState('{ "node": "9", "key": "images" }');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workflows"] });

  const importPack = useMutation({
    mutationFn: () => {
      let workflow: unknown, inputs: unknown, outputs: unknown;
      try {
        workflow = JSON.parse(workflowJson);
        inputs = inputsJson ? JSON.parse(inputsJson) : {};
        outputs = outputsJson ? JSON.parse(outputsJson) : {};
      } catch (e) {
        throw new Error(`JSON 解析失败: ${(e as Error).message}`);
      }
      return api.importWorkflow({
        name,
        capability,
        workflow,
        inputs,
        outputs,
      });
    },
    onSuccess: (pack) => {
      setNotice(`已导入 ${pack.name}`);
      setError(null);
      setName("");
      setWorkflowJson("");
      setInputsJson("");
      invalidate();
    },
    onError: (err) => {
      setError(err.message);
      setNotice(null);
    },
  });

  const remove = useMutation({
    mutationFn: (n: string) => api.deleteWorkflow(n),
    onSuccess: invalidate,
    onError: (err) => setError(err.message),
  });

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
              {p.source === "user" && (
                <Button variant="ghost" size="icon" onClick={() => remove.mutate(p.name)} title="删除">
                  <Trash2 />
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>导入工作流包</CardTitle>
          <CardDescription>
            粘贴 ComfyUI 的 API Format JSON，并用 manifest 声明参数到节点的映射（JSON 是合法 YAML）。
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="包名" hint="只用字母、数字、横线和下划线。">
              <Input value={name} onChange={(e) => setName(e.target.value)} />
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
                <option value="tts">tts 语音</option>
              </select>
            </Field>
          </div>
          <Field label="workflow.json" hint="在 ComfyUI 里用 Save (API Format) 导出后粘贴到这里。">
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
          <Button
            className="w-fit"
            onClick={() => importPack.mutate()}
            disabled={!name || !workflowJson || importPack.isPending}
          >
            导入
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
