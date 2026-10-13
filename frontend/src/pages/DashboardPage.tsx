import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth";

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const { data: health } = useQuery({ queryKey: ["healthz"], queryFn: api.healthz });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">工作台</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>欢迎{user ? `，${user.username}` : ""}</CardTitle>
            <CardDescription>LiberAstra 已就绪</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            语音、图像、视频能力将在后续里程碑开放，先到「设置」添加服务提供方。
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>服务状态</CardTitle>
            <CardDescription>后端健康检查</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {health ? `运行中 · v${health.version}` : "连接中…"}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
