import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">LiberAstra</CardTitle>
          <CardDescription>
            {isSetup ? t("auth.subtitleSetup") : t("auth.subtitleLogin")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              setError(null);
              submit.mutate();
            }}
          >
            <Input
              placeholder={t("auth.username")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
            <Input
              type="password"
              placeholder={isSetup ? t("auth.passwordSetup") : t("auth.password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSetup ? "new-password" : "current-password"}
              minLength={isSetup ? 8 : 1}
              required
            />
            {error && <p className="text-sm text-red-500">{error}</p>}
            <Button type="submit" disabled={submit.isPending}>
              {submit.isPending
                ? t("auth.waiting")
                : isSetup
                  ? t("auth.submitSetup")
                  : t("auth.submitLogin")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
