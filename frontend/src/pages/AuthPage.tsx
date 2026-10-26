import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Clapperboard, Image as ImageIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Starfield } from "@/components/ui/starfield";
import { useAuthStore } from "@/stores/auth";

export function AuthPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const signIn = useAuthStore((s) => s.signIn);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: status } = useQuery({ queryKey: ["auth-status"], queryFn: api.authStatus });
  const isSetup = status != null && !status.initialized;

  const submit = useMutation({
    mutationFn: async () => {
      if (isSetup) await api.setup(username, password);
      const { access_token } = await api.login(username, password);
      return access_token;
    },
    onSuccess: (token) => {
      signIn(token, null);
      queryClient.invalidateQueries({ queryKey: ["auth-status"] });
      navigate("/dashboard");
    },
    onError: (err) => setError(err.message),
  });

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-10">
      {/* 聚星画布:星星聚拢成星座 = 聚合编排 */}
      <div className="absolute inset-0">
        <Starfield />
      </div>

      <div className="result-in relative w-full max-w-[26rem] rounded-[28px] border border-border/60 bg-card/75 px-8 py-10 shadow-2xl shadow-primary/10 backdrop-blur-xl">
        {/* 品牌光斑:签名元素,落在磨砂卡上 */}
        <div aria-hidden className="pointer-events-none absolute -top-10 right-6 size-28 rounded-full bg-primary/20 blur-3xl sm:-top-14 sm:size-40" />
        <div className="relative mb-8 flex items-center gap-3.5">
          <span className="grid size-11 place-items-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">
            L
          </span>
          <div>
            <h1 className="text-2xl font-semibold leading-tight tracking-tight">LiberAstra</h1>
            <p className="text-sm text-muted-foreground">
              {isSetup ? t("auth.subtitleSetup") : t("auth.subtitleLogin")}
            </p>
          </div>
        </div>
        <form
          className="relative flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            submit.mutate();
          }}
        >
          <Field label={t("auth.username")} hint={t("auth.usernameHint")}>
            <Input
              placeholder={t("auth.username")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </Field>
          <Field
            label={t("auth.password")}
            hint={isSetup ? t("auth.passwordSetupHint") : t("auth.passwordHint")}
          >
            <Input
              type="password"
              placeholder={isSetup ? t("auth.passwordSetup") : t("auth.password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSetup ? "new-password" : "current-password"}
              minLength={isSetup ? 8 : 1}
              required
            />
          </Field>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <Button type="submit" disabled={submit.isPending} className="mt-1 h-12 text-[15px]">
            {submit.isPending ? t("auth.waiting") : isSetup ? t("auth.submitSetup") : t("auth.submitLogin")}
          </Button>
        </form>
      </div>

      {/* 能力注脚:图像 · 视频 · 语音,真实功能,非营销词 */}
      <div className="relative mt-6 flex items-center gap-5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <ImageIcon className="size-3.5" /> {t("group.image")}
        </span>
        <span className="flex items-center gap-1.5">
          <Clapperboard className="size-3.5" /> {t("group.video")}
        </span>
        <span className="flex items-center gap-1.5">
          <AudioLines className="size-3.5" /> {t("group.speech")}
        </span>
      </div>
    </div>
  );
}
