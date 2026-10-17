import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Settings, Timer, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/api/client";
import { PageHeader } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NumberStepper } from "@/components/ui/number-stepper";
import { useAuthStore } from "@/stores/auth";

/** 系统设置：账户安全（改密码）+ 运行参数（各类等待超时）。 */
export function SystemSettingsPage() {
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
      setPwdError("新密码至少 8 位");
      return;
    }
    if (newPwd !== confirmPwd) {
      setPwdError("两次输入的新密码不一致");
      return;
    }
    setPwdError(null);
    changePwd.mutate();
  };

  // ---- 运行参数（超时） ----
  const { data: prefs } = useQuery({ queryKey: ["system-preferences"], queryFn: api.getPreferences });
  const [comfyTimeout, setComfyTimeout] = useState(600);
  const [apiTimeout, setApiTimeout] = useState(300);
  const [llmTimeout, setLlmTimeout] = useState(300);
  const [serialSameHost, setSerialSameHost] = useState(false);
  const [prefSaved, setPrefSaved] = useState(false);

  useEffect(() => {
    if (prefs) {
      setComfyTimeout(prefs.comfy_wait_timeout_seconds);
      setApiTimeout(prefs.api_wait_timeout_seconds);
      setLlmTimeout(prefs.llm_request_timeout_seconds);
      setSerialSameHost(prefs.serial_same_host === 1);
    }
  }, [prefs]);

  const savePrefs = useMutation({
    mutationFn: () =>
      api.updatePreferences({
        comfy_wait_timeout_seconds: comfyTimeout,
        api_wait_timeout_seconds: apiTimeout,
        llm_request_timeout_seconds: llmTimeout,
        serial_same_host: serialSameHost ? 1 : 0,
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
        title="系统设置"
        description="账户安全与运行参数。Provider 的密钥在「服务提供方」里管理，这里只管登录账户。"
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserRound className="size-4" /> 账户与安全
          </CardTitle>
          <CardDescription>当前登录账户与密码。密码只存哈希，修改后下次登录生效。</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label="当前账户" hint="这台 LiberAstra 的登录用户名。">
            <Input value={username} readOnly disabled />
          </Field>
          <form
            className="grid gap-3 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              submitPassword();
            }}
          >
            <Field label="当前密码" hint="验证身份用。">
              <Input
                type="password"
                value={currentPwd}
                required
                autoComplete="current-password"
                onChange={(e) => setCurrentPwd(e.target.value)}
              />
            </Field>
            <Field label="新密码" hint="至少 8 位。">
              <Input
                type="password"
                value={newPwd}
                required
                autoComplete="new-password"
                onChange={(e) => setNewPwd(e.target.value)}
              />
            </Field>
            <Field label="确认新密码" hint="再输一遍，防止打错。">
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
                <KeyRound /> {changePwd.isPending ? "修改中…" : "修改密码"}
              </Button>
              {pwdDone && <span className="text-sm text-green-600">密码已更新，下次登录请用新密码。</span>}
              {pwdError && <span className="text-sm text-red-500">{pwdError}</span>}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Timer className="size-4" /> 运行参数
          </CardTitle>
          <CardDescription>保存后对下一个任务生效，进行中的任务不受影响。</CardDescription>
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
              label="ComfyUI 等待超时（秒）"
              hint="图生图/视频在 ComfyUI 侧排队或步数较多时容易超过默认 600 秒，超时后任务以「等待 ComfyUI 结果超时」失败。60 到 14400。"
            >
              <NumberStepper
                ariaLabel="ComfyUI 等待超时"
                min={60}
                max={14400}
                step={60}
                value={comfyTimeout}
                onChange={setComfyTimeout}
              />
            </Field>
            <Field
              label="接口同步等待超时（秒）"
              hint="只影响带 wait=true 的同步 API 调用；页面里的异步任务不受影响。30 到 3600。"
            >
              <NumberStepper
                ariaLabel="接口同步等待超时"
                min={30}
                max={3600}
                step={30}
                value={apiTimeout}
                onChange={setApiTimeout}
              />
            </Field>
            <Field
              label="LLM 请求超时（秒）"
              hint="Ollama / OpenAI 兼容接口单次对话的读超时。大模型（如 32B）冷启动容易超过 60 秒；默认 300，范围 30 到 3600。"
            >
              <NumberStepper
                ariaLabel="LLM 请求超时"
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
                同主机服务串行执行
              </label>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                默认并行。开启后：同一台主机上的多个服务（如本机或同一台显卡主机上的
                Ollama、ComfyUI、语音服务）同时只跑一个任务，避免抢显存；不同主机之间照常并行。
              </p>
            </div>
            <div className="flex items-center gap-3 sm:col-span-2">
              <Button type="submit" disabled={savePrefs.isPending}>
                {savePrefs.isPending ? "保存中…" : "保存"}
              </Button>
              {prefSaved && !savePrefs.isPending && (
                <span className="text-sm text-green-600">已保存，下一个任务起生效。</span>
              )}
              {savePrefs.isError && <span className="text-sm text-red-500">{savePrefs.error.message}</span>}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
