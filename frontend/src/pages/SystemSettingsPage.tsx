import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Bot, ImageIcon, KeyRound, RefreshCw, Settings, Timer, UserRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, ApiError, type SpeechCatalogModel } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, selectClass } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { useAuthStore } from "@/stores/auth";
import {
  SPEECH_MODEL_GROUPS,
  asrModelHint,
  speechModelHint,
} from "@/components/SpeechLanguageSelect";
import { useTx } from "@/i18n/tx";

/** 系统设置：账户安全（改密码）+ 运行参数（各类等待超时）。 */
export function SystemSettingsPage() {
  const tx = useTx();
  const queryClient = useQueryClient();
  const storedUser = useAuthStore((s) => s.user);
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me });
  const username = me?.username ?? storedUser?.username ?? "";

  // ---- 修改密码 ----
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdDone, setPwdDone] = useState(false);

  const changePwd = useMutation({
    mutationFn: () => api.changePassword(currentPwd, newPwd),
    onSuccess: () => {
      setPwdError(null);
      setPwdDone(true);
      setCurrentPwd("");
      setNewPwd("");
      setConfirmPwd("");
    },
    onError: (err) => {
      setPwdDone(false);
      setPwdError(err.message);
    },
  });

  const submitPassword = () => {
    setPwdDone(false);
    if (newPwd.length < 8) {
      setPwdError(tx("新密码至少 8 位"));
      return;
    }
    if (newPwd !== confirmPwd) {
      setPwdError(tx("两次输入的新密码不一致"));
      return;
    }
    setPwdError(null);
    changePwd.mutate();
  };

  // ---- 运行参数（超时） ----
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  const speechCatalog = useQuery({
    queryKey: ["speech-catalog"],
    queryFn: api.getSpeechCatalog,
    retry: false,
  });
  const [comfyTimeout, setComfyTimeout] = useState(600);
  const [apiTimeout, setApiTimeout] = useState(300);
  const [llmTimeout, setLlmTimeout] = useState(300);
  const [serialSameHost, setSerialSameHost] = useState(false);
  const [llmProviderId, setLlmProviderId] = useState(0);
  const [llmModel, setLlmModel] = useState("");
  const [characterProviderId, setCharacterProviderId] = useState(0);
  const [characterWorkflow, setCharacterWorkflow] = useState("qwen_image_21");
  const [characterI2i, setCharacterI2i] = useState("qwen_image_21_edit");
  const [characterI2iMulti, setCharacterI2iMulti] = useState("qwen_image_21_edit_multi");
  const [speechModel, setSpeechModel] = useState("multilingual_v3");
  const [speechAsrModel, setSpeechAsrModel] = useState("");
  const [prefSaved, setPrefSaved] = useState(false);
  const ttsGroups = useMemo(
    () => groupSpeechModels(speechCatalog.data?.tts_models ?? [], speechModel),
    [speechCatalog.data, speechModel],
  );
  const asrOptions = useMemo(() => {
    const options: SpeechCatalogModel[] = [
      { id: "", label: "跟随语音服务配置 (.env)" },
      ...(speechCatalog.data?.asr_models ?? []),
    ];
    if (speechAsrModel && !options.some((item) => item.id === speechAsrModel)) {
      options.push({ id: speechAsrModel, label: speechAsrModel });
    }
    return options;
  }, [speechCatalog.data, speechAsrModel]);
  const catalogError =
    speechCatalog.error instanceof ApiError
      ? speechCatalog.error.message
      : speechCatalog.error
        ? "无法读取 Liber Speech 的模型列表"
        : "";

  const { data: providers } = useQuery({ queryKey: ["providers"], queryFn: api.listProviders });
  const llmProviders = useMemo(
    () => (providers ?? []).filter((p) => p.enabled && p.capabilities.includes("llm")),
    [providers],
  );
  const imageProviders = useMemo(
    () => (providers ?? []).filter((p) => p.enabled && p.capabilities.includes("image")),
    [providers],
  );
  const { data: workflows } = useQuery({ queryKey: ["workflows"], queryFn: () => api.listWorkflows() });
  const t2iPacks = useMemo(
    () => (workflows ?? []).filter((pack) => pack.capability === "t2i"),
    [workflows],
  );
  const i2iPacks = useMemo(
    () => (workflows ?? []).filter((pack) => pack.capability === "i2i"),
    [workflows],
  );
  const selectedLlm = llmProviders.find((p) => p.id === llmProviderId) ?? null;
  const fetchModels = useMutation({
    mutationFn: (id: number) => api.fetchProviderModels(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });

  useEffect(() => {
    if (prefs) {
      setComfyTimeout(prefs.comfy_wait_timeout_seconds);
      setApiTimeout(prefs.api_wait_timeout_seconds);
      setLlmTimeout(prefs.llm_request_timeout_seconds);
      setSerialSameHost(prefs.serial_same_host === 1);
      setLlmProviderId(prefs.default_llm_provider_id ?? 0);
      setLlmModel(prefs.default_llm_model ?? "");
      setCharacterProviderId(prefs.default_character_provider_id ?? 0);
      setCharacterWorkflow(prefs.default_character_workflow || "qwen_image_21");
      setCharacterI2i(prefs.default_character_i2i_workflow || "qwen_image_21_edit");
      setCharacterI2iMulti(prefs.default_character_i2i_multi_workflow || "qwen_image_21_edit_multi");
      setSpeechModel(prefs.default_speech_model || "multilingual_v3");
      setSpeechAsrModel(prefs.default_asr_model || "");
    }
  }, [prefs]);

  const savePrefs = useMutation({
    mutationFn: () =>
      api.updatePreferences({
        comfy_wait_timeout_seconds: comfyTimeout,
        api_wait_timeout_seconds: apiTimeout,
        llm_request_timeout_seconds: llmTimeout,
        serial_same_host: serialSameHost ? 1 : 0,
        default_llm_provider_id: llmProviderId,
        default_llm_model: llmModel,
        default_character_provider_id: characterProviderId,
        default_character_workflow: characterWorkflow,
        default_character_i2i_workflow: characterI2i,
        default_character_i2i_multi_workflow: characterI2iMulti,
        default_speech_model: speechModel,
        default_asr_model: speechAsrModel,
      }),
    onSuccess: (next) => {
      setPrefSaved(true);
      queryClient.setQueryData(["system-preferences"], next);
    },
  });

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <PageHeader
        kind="settings"
        icon={Settings}
        title={tx("系统设置")}
        description={tx("账户安全与运行参数。Provider 的密钥在「服务提供方」里管理，这里只管登录账户。")}
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserRound className="size-4" /> {tx('账户与安全')}
          </CardTitle>
          <CardDescription>{tx("当前登录账户与密码。密码只存哈希，修改后下次登录生效。")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label={tx("当前账户")} hint={tx("这台 LiberAstra 的登录用户名。")}>
            <Input value={username} readOnly disabled />
          </Field>
          <form
            className="grid gap-3 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              submitPassword();
            }}
          >
            <Field label={tx("当前密码")} hint={tx("验证身份用。")}>
              <Input
                type="password"
                value={currentPwd}
                required
                autoComplete="current-password"
                onChange={(e) => setCurrentPwd(e.target.value)}
              />
            </Field>
            <Field label={tx("新密码")} hint={tx("至少 8 位。")}>
              <Input
                type="password"
                value={newPwd}
                required
                autoComplete="new-password"
                onChange={(e) => setNewPwd(e.target.value)}
              />
            </Field>
            <Field label={tx("确认新密码")} hint={tx("再输一遍，防止打错。")}>
              <Input
                type="password"
                value={confirmPwd}
                required
                autoComplete="new-password"
                onChange={(e) => setConfirmPwd(e.target.value)}
              />
            </Field>
            <div className="flex items-center gap-3 sm:col-span-3">
              <Button type="submit" disabled={changePwd.isPending}>
                <KeyRound /> {changePwd.isPending ? tx("修改中…") : tx("修改密码")}
              </Button>
              {pwdDone && <span className="text-sm text-green-600">{tx("密码已更新，下次登录请用新密码。")}</span>}
              {pwdError && <span className="text-sm text-red-500">{pwdError}</span>}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="size-4" /> {tx('默认 LLM（脚本与提示词优化）')}
          </CardTitle>
          <CardDescription>
            {tx('快速创作、自定义素材、提示词 ✨ 优化统一使用此处配置，无需在各功能页重复选择。')}
            {tx('未选服务商时自动取第一个启用的 LLM Provider。')}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Field label={tx("LLM 服务商")} hint={tx("在「服务提供方」中添加 Ollama / OpenAI 兼容等。")}>
            <div className="flex gap-2">
              <select
                className={selectClass}
                value={llmProviderId}
                onChange={(e) => {
                  setLlmProviderId(Number(e.target.value));
                  setLlmModel("");
                }}
              >
                <option value={0}>{tx("自动（第一个启用的 LLM）")}</option>
                {llmProviders.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="outline"
                size="icon"
                title={tx("刷新模型列表")}
                disabled={!selectedLlm || fetchModels.isPending}
                onClick={() => selectedLlm && fetchModels.mutate(selectedLlm.id)}
              >
                <RefreshCw className={fetchModels.isPending ? "animate-spin" : undefined} />
              </Button>
            </div>
          </Field>
          <Field label={tx("默认模型")} hint={tx("可从已拉取列表选择，或手填模型名。")}>
            {selectedLlm?.models?.length ? (
              <select
                className={selectClass}
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
              >
                <option value="">{tx("自动（Provider 默认 / 列表首项）")}</option>
                {selectedLlm.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                value={llmModel}
                placeholder={tx("留空则自动；或手填模型名")}
                onChange={(e) => setLlmModel(e.target.value)}
              />
            )}
          </Field>
          {llmProviders.length === 0 && (
            <p className="text-sm text-amber-700 dark:text-amber-400 sm:col-span-2">
              {tx('尚未配置启用的 LLM 服务商。请先到「服务提供方」添加。')}
            </p>
          )}
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button
              type="button"
              disabled={savePrefs.isPending}
              onClick={() => {
                setPrefSaved(false);
                savePrefs.mutate();
              }}
            >
              {savePrefs.isPending ? tx("保存中…") : tx("保存")}
            </Button>
            {prefSaved && !savePrefs.isPending && (
              <span className="text-sm text-green-600">{tx("已保存。")}</span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AudioLines className="size-4" /> {tx("语音文字合成（Liber Speech）")}
          </CardTitle>
          <CardDescription>
            {tx("两个下拉框的选项来自已启用的 Liber Speech。功能页不单独选模型时使用这里保存的值。")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {speechCatalog.isPending && (
            <p className="text-sm text-muted-foreground">{tx("正在读取 Liber Speech 的模型列表…")}</p>
          )}
          {catalogError && <p className="text-sm text-red-500">{catalogError}</p>}
          <Field label={tx("文字转语音模型")} hint={tx(speechModelHint(speechModel))}>
            <select
              className={selectClass}
              value={speechModel}
              disabled={!speechCatalog.data}
              onChange={(e) => setSpeechModel(e.target.value)}
            >
              {ttsGroups.map((group) =>
                group.id ? (
                  <optgroup key={group.id} label={tx(speechGroupLabel(group.id))}>
                    {group.items.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </optgroup>
                ) : (
                  group.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))
                ),
              )}
            </select>
          </Field>
          <Field label={tx("语音转文字模型")} hint={tx(asrModelHint(speechAsrModel))}>
            <select
              className={selectClass}
              value={speechAsrModel}
              disabled={!speechCatalog.data}
              onChange={(e) => setSpeechAsrModel(e.target.value)}
            >
              {asrOptions.map((item) => (
                <option key={item.id || "env"} value={item.id}>
                  {item.id ? item.label : tx(item.label)}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="outline"
              disabled={speechCatalog.isFetching}
              onClick={() => {
                void speechCatalog.refetch();
              }}
            >
              <RefreshCw className={speechCatalog.isFetching ? "animate-spin" : undefined} />
              {tx("重新读取")}
            </Button>
            <Button
              type="button"
              disabled={savePrefs.isPending}
              onClick={() => {
                setPrefSaved(false);
                savePrefs.mutate();
              }}
            >
              {savePrefs.isPending ? tx("保存中…") : tx("保存")}
            </Button>
            {prefSaved && !savePrefs.isPending && (
              <span className="text-sm text-green-600">{tx("已保存。")}</span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ImageIcon className="size-4" /> {tx("默认角色生图")}
          </CardTitle>
          <CardDescription>
            {tx("没有参考图时用文生图。上传 1 张参考图用图生图，2 到 3 张用多图编辑。")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Field label={tx("图像服务商")} hint={tx("在「服务提供方」中添加 ComfyUI 等图像服务。")}>
            <select
              className={selectClass}
              value={characterProviderId}
              onChange={(e) => setCharacterProviderId(Number(e.target.value))}
            >
              <option value={0}>{tx("自动（第一个启用的图像服务）")}</option>
              {imageProviders.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={tx("定妆照工作流包")} hint={tx("只列出文生图工作流包。默认 Qwen-Image 2.1。")}>
            <select
              className={selectClass}
              value={characterWorkflow}
              onChange={(e) => setCharacterWorkflow(e.target.value)}
            >
              {t2iPacks.length === 0 && <option value={characterWorkflow}>{characterWorkflow}</option>}
              {t2iPacks.map((pack) => (
                <option key={pack.name} value={pack.name}>
                  {pack.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={tx("单张参考图工作流")} hint={tx("上传 1 张参考图时使用的图生图包。")}>
            <select className={selectClass} value={characterI2i} onChange={(e) => setCharacterI2i(e.target.value)}>
              {i2iPacks.length === 0 && <option value={characterI2i}>{characterI2i}</option>}
              {i2iPacks.map((pack) => (
                <option key={pack.name} value={pack.name}>{pack.name}</option>
              ))}
            </select>
          </Field>
          <Field label={tx("多张参考图工作流")} hint={tx("上传 2 到 3 张参考图时使用的多图编辑包。")}>
            <select className={selectClass} value={characterI2iMulti} onChange={(e) => setCharacterI2iMulti(e.target.value)}>
              {i2iPacks.length === 0 && <option value={characterI2iMulti}>{characterI2iMulti}</option>}
              {i2iPacks.map((pack) => (
                <option key={pack.name} value={pack.name}>{pack.name}</option>
              ))}
            </select>
          </Field>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button
              type="button"
              disabled={savePrefs.isPending}
              onClick={() => {
                setPrefSaved(false);
                savePrefs.mutate();
              }}
            >
              {savePrefs.isPending ? tx("保存中…") : tx("保存")}
            </Button>
            {prefSaved && !savePrefs.isPending && <span className="text-sm text-green-600">{tx("已保存。")}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Timer className="size-4" /> {tx('运行参数')}
          </CardTitle>
          <CardDescription>{tx("保存后对下一个任务生效，进行中的任务不受影响。")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              setPrefSaved(false);
              savePrefs.mutate();
            }}
          >
            <Field
              label={tx("ComfyUI 等待超时（秒）")}
              hint={tx("图生图/视频在 ComfyUI 侧排队或步数较多时容易超过默认 600 秒，超时后任务以「等待 ComfyUI 结果超时」失败。60 到 14400。")}
            >
              <NumberStepper
                ariaLabel={tx("ComfyUI 等待超时")}
                min={60}
                max={14400}
                step={60}
                value={comfyTimeout}
                onChange={setComfyTimeout}
              />
            </Field>
            <Field
              label={tx("接口同步等待超时（秒）")}
              hint={tx("只影响带 wait=true 的同步 API 调用；页面里的异步任务不受影响。30 到 3600。")}
            >
              <NumberStepper
                ariaLabel={tx("接口同步等待超时")}
                min={30}
                max={3600}
                step={30}
                value={apiTimeout}
                onChange={setApiTimeout}
              />
            </Field>
            <Field
              label={tx("LLM 请求超时（秒）")}
              hint={tx("Ollama / OpenAI 兼容接口单次对话的读超时。大模型（如 32B）冷启动容易超过 60 秒；默认 300，范围 30 到 3600。")}
            >
              <NumberStepper
                ariaLabel={tx("LLM 请求超时")}
                min={30}
                max={3600}
                step={30}
                value={llmTimeout}
                onChange={setLlmTimeout}
              />
            </Field>
            <div className="sm:col-span-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={serialSameHost}
                  onChange={(e) => setSerialSameHost(e.target.checked)}
                />
                {tx('同主机服务串行执行')}
              </label>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {tx('默认并行。开启后：同一台主机上的多个服务（如本机或同一台显卡主机上的')}
                {tx('Ollama、ComfyUI、语音服务）同时只跑一个任务，避免抢显存；不同主机之间照常并行。')}
              </p>
            </div>
            <div className="flex items-center gap-3 sm:col-span-2">
              <Button type="submit" disabled={savePrefs.isPending}>
                {savePrefs.isPending ? tx("保存中…") : tx("保存")}
              </Button>
              {prefSaved && !savePrefs.isPending && (
                <span className="text-sm text-green-600">{tx("已保存，下一个任务起生效。")}</span>
              )}
              {savePrefs.isError && <span className="text-sm text-red-500">{savePrefs.error.message}</span>}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function speechGroupLabel(group: string): string {
  return SPEECH_MODEL_GROUPS.find((item) => item.id === group)?.label || group;
}

function groupSpeechModels(models: SpeechCatalogModel[], selected: string) {
  const source = [...models];
  if (selected && !source.some((item) => item.id === selected)) {
    source.push({ id: selected, label: selected });
  }
  const order: string[] = [];
  const grouped = new Map<string, SpeechCatalogModel[]>();
  for (const item of source) {
    const group = item.group || "";
    if (!grouped.has(group)) {
      order.push(group);
      grouped.set(group, []);
    }
    grouped.get(group)?.push(item);
  }
  return order.map((id) => ({ id, items: grouped.get(id) ?? [] }));
}
