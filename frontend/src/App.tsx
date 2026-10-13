import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import { api } from "@/api/client";
import { Layout } from "@/components/Layout";
import { AuthPage } from "@/pages/AuthPage";
import { AsrPage } from "@/pages/AsrPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ImageEditPage } from "@/pages/ImageEditPage";
import { ImageGenPage } from "@/pages/ImageGenPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { TtsPage } from "@/pages/TtsPage";
import { VoicesPage } from "@/pages/VoicesPage";
import { WorkflowsPage } from "@/pages/WorkflowsPage";
import { useAuthStore } from "@/stores/auth";

function HomeRedirect() {
  const token = useAuthStore((s) => s.token);
  const { data: status, isLoading } = useQuery({
    queryKey: ["auth-status"],
    queryFn: api.authStatus,
  });

  if (isLoading) return null;
  if (!status?.initialized) return <Navigate to="/auth" replace />;
  return token ? <Navigate to="/dashboard" replace /> : <Navigate to="/auth" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/speech/tts" element={<TtsPage />} />
        <Route path="/speech/asr" element={<AsrPage />} />
        <Route path="/speech/voices" element={<VoicesPage />} />
        <Route path="/image/generate" element={<ImageGenPage />} />
        <Route
          path="/image/edit"
          element={
            <ImageEditPage
              capability="i2i"
              title="图生图与编辑"
              description="上传参考图，配合提示词进行编辑或风格迁移。"
            />
          }
        />
        <Route
          path="/image/upscale"
          element={
            <ImageEditPage
              capability="upscale"
              title="修复与放大"
              description="上传图片，用修复/放大工作流（如 SUPIR）提升画质。"
            />
          }
        />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/settings/workflows" element={<WorkflowsPage />} />
      </Route>
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}
