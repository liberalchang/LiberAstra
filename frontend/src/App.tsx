import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import { api } from "@/api/client";
import { Layout } from "@/components/Layout";
import { AuthPage } from "@/pages/AuthPage";
import { AsrPage } from "@/pages/AsrPage";
import { AssetsPage } from "@/pages/AssetsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { CliPage } from "@/pages/CliPage";
import { GuidePage } from "@/pages/GuidePage";
import { ImageEditPage } from "@/pages/ImageEditPage";
import { ImageGenPage } from "@/pages/ImageGenPage";
import { JobsPage } from "@/pages/JobsPage";
import { MusicPage } from "@/pages/MusicPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SystemSettingsPage } from "@/pages/SystemSettingsPage";
import { TemplatesPage } from "@/pages/TemplatesPage";
import { TtsPage } from "@/pages/TtsPage";
import { VideoAssetsPage } from "@/pages/VideoAssetsPage";
import { VideoPackPage } from "@/pages/VideoPackPage";
import { VideoQuickPage } from "@/pages/VideoQuickPage";
import { VoicesPage } from "@/pages/VoicesPage";
import { WorkflowsPage } from "@/pages/WorkflowsPage";
import { useTx } from "@/i18n/tx";
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
  const tx = useTx();
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/guide" element={<GuidePage />} />
        <Route path="/dev/cli" element={<CliPage />} />
        <Route path="/speech/tts" element={<TtsPage />} />
        <Route path="/speech/asr" element={<AsrPage />} />
        <Route path="/speech/voices" element={<VoicesPage />} />
        <Route path="/speech/music" element={<MusicPage />} />
        <Route path="/image/generate" element={<ImageGenPage />} />
        <Route
          path="/image/edit"
          element={
            <ImageEditPage
              capability="i2i"
              title={tx("图生图与编辑")}
              description={tx("上传参考图，配合提示词进行编辑或风格迁移。")}
            />
          }
        />
        <Route
          path="/image/upscale"
          element={
            <ImageEditPage
              capability="upscale"
              title={tx("修复与放大")}
              description={tx("上传图片，用 RealESRGAN 放大 4 倍。模型文件需放在 ComfyUI 的 upscale_models 目录。")}
            />
          }
        />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/settings/system" element={<SystemSettingsPage />} />
        <Route path="/settings/workflows" element={<WorkflowsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/assets" element={<AssetsPage />} />
        <Route path="/video/quick" element={<VideoQuickPage />} />
        <Route path="/video/templates" element={<TemplatesPage />} />
        <Route path="/video/assets" element={<VideoAssetsPage />} />
        <Route path="/video/avatar" element={<VideoPackPage kind="avatar" />} />
        <Route path="/video/i2v" element={<VideoPackPage kind="i2v" />} />
        <Route path="/video/motion" element={<VideoPackPage kind="motion" />} />
      </Route>
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}
