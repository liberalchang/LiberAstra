import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth";

export function DashboardPage() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const { data: health } = useQuery({ queryKey: ["healthz"], queryFn: api.healthz });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">{t("group.workbench")}</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>
              {t("dashboard.welcome")}
              {user ? `，${user.username}` : ""}
            </CardTitle>
            <CardDescription>{t("dashboard.ready")}</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {t("dashboard.readyHint")}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("dashboard.status")}</CardTitle>
            <CardDescription>{t("dashboard.statusHint")}</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {health ? `${t("dashboard.runningAt")} · v${health.version}` : t("dashboard.connecting")}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
