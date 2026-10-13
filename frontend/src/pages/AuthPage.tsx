import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
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
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-[28px] border border-border bg-card px-8 py-10">
        <div className="mb-6 flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-primary text-base font-bold text-primary-foreground">
            L
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">LiberAstra</h1>
            <p className="text-sm text-muted-foreground">
              {isSetup ? t("auth.subtitleSetup") : t("auth.subtitleLogin")}
            </p>
          </div>
        </div>
        <form
          className="flex flex-col gap-3"
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
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button type="submit" disabled={submit.isPending} className="mt-2">
            {submit.isPending ? t("auth.waiting") : isSetup ? t("auth.submitSetup") : t("auth.submitLogin")}
          </Button>
        </form>
      </div>
    </div>
  );
}
