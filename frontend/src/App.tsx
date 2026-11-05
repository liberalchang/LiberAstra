import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api } from "@/api/client";
import { Layout } from "@/components/Layout";
import { AuthPage } from "@/pages/AuthPage";
import { useTx } from "@/i18n/tx";
import { useAuthStore } from "@/stores/auth";

// 路由级代码分割：各页面（含 GuidePage 内联的 markdown 文档）按需加载
const AsrPage = lazy(() => import("@/pages/AsrPage").then((m) => ({ default: m.AsrPage })));
const VcPage = lazy(() => import("@/pages/VcPage").then((m) => ({ default: m.VcPage })));
const AssetsPage = lazy(() => import("@/pages/AssetsPage").then((m) => ({ default: m.AssetsPage })));
const AssetJobPage = lazy(() => import("@/pages/AssetJobPage").then((m) => ({ default: m.AssetJobPage })));
const DashboardPage = lazy(() => import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const CanvasListPage = lazy(() =>
  import("@/pages/CanvasListPage").then((m) => ({ default: m.CanvasEntryPage })),
);
const CanvasPage = lazy(() => import("@/pages/CanvasPage").then((m) => ({ default: m.CanvasPage })));
const CharactersPage = lazy(() => import("@/pages/CharactersPage").then((m) => ({ default: m.CharactersPage })));
const GuidePage = lazy(() => import("@/pages/GuidePage").then((m) => ({ default: m.GuidePage })));
const ImageEditPage = lazy(() => import("@/pages/ImageEditPage").then((m) => ({ default: m.ImageEditPage })));
const ImageDepthPage = lazy(() => import("@/pages/ImageDepthPage").then((m) => ({ default: m.ImageDepthPage })));
const ImageGenPage = lazy(() => import("@/pages/ImageGenPage").then((m) => ({ default: m.ImageGenPage })));
const JobsPage = lazy(() => import("@/pages/JobsPage").then((m) => ({ default: m.JobsPage })));
const MediaConcatPage = lazy(() =>
  import("@/pages/MediaConcatPage").then((m) => ({ default: m.MediaConcatPage })),
);
const VideoEnhancePage = lazy(() =>
  import("@/pages/VideoEnhancePage").then((m) => ({ default: m.VideoEnhancePage })),
);
const PluginsPage = lazy(() => import("@/pages/PluginsPage").then((m) => ({ default: m.PluginsPage })));
const MusicPage = lazy(() => import("@/pages/MusicPage").then((m) => ({ default: m.MusicPage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const PromptsPage = lazy(() => import("@/pages/PromptsPage").then((m) => ({ default: m.PromptsPage })));
const SystemSettingsPage = lazy(() =>
  import("@/pages/SystemSettingsPage").then((m) => ({ default: m.SystemSettingsPage })),
);
const TemplatesPage = lazy(() => import("@/pages/TemplatesPage").then((m) => ({ default: m.TemplatesPage })));
const TtsPage = lazy(() => import("@/pages/TtsPage").then((m) => ({ default: m.TtsPage })));
const VideoAssetsPage = lazy(() => import("@/pages/VideoAssetsPage").then((m) => ({ default: m.VideoAssetsPage })));
const VideoPackPage = lazy(() => import("@/pages/VideoPackPage").then((m) => ({ default: m.VideoPackPage })));
const VideoQuickPage = lazy(() => import("@/pages/VideoQuickPage").then((m) => ({ default: m.VideoQuickPage })));
const VoicesPage = lazy(() => import("@/pages/VoicesPage").then((m) => ({ default: m.VoicesPage })));
const WorkflowsPage = lazy(() => import("@/pages/WorkflowsPage").then((m) => ({ default: m.WorkflowsPage })));

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
    <Suspense fallback={null}>
      <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/canvas" element={<CanvasListPage />} />
        <Route path="/canvas/:id" element={<CanvasPage />} />
        <Route path="/guide/*" element={<GuidePage />} />
        <Route path="/speech/tts" element={<TtsPage />} />
        <Route path="/speech/asr" element={<AsrPage />} />
        <Route path="/speech/vc" element={<VcPage />} />
        <Route path="/resources/voices" element={<VoicesPage />} />
        <Route path="/resources/music" element={<MusicPage />} />
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
        <Route path="/image/upscale" element={<Navigate to="/tools/image-enhance" replace />} />
        <Route path="/image/depth" element={<ImageDepthPage />} />
        <Route path="/tools" element={<Navigate to="/tools/image-concat" replace />} />
        <Route path="/tools/image-concat" element={<MediaConcatPage kind="image" />} />
        <Route path="/tools/video-concat" element={<MediaConcatPage kind="video" />} />
        <Route path="/tools/audio-concat" element={<MediaConcatPage kind="audio" />} />
        <Route
          path="/tools/image-enhance"
          element={
            <ImageEditPage
              capability="upscale"
              title={tx("图片增强")}
              description={tx("保真放大用 RealESRGAN；AI 修复用 SeedVR2。按需选择工作流。")}
            />
          }
        />
        <Route path="/tools/video-enhance" element={<VideoEnhancePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/settings/prompts" element={<PromptsPage />} />
        <Route path="/settings/system" element={<SystemSettingsPage />} />
        <Route path="/settings/workflows" element={<WorkflowsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/assets" element={<AssetsPage />} />
        <Route path="/assets/jobs/:jobId" element={<AssetJobPage />} />
        <Route path="/settings/plugins" element={<PluginsPage />} />
        <Route path="/video/quick" element={<VideoQuickPage />} />
        <Route path="/settings/storyboard-templates" element={<TemplatesPage />} />
        <Route path="/video/assets" element={<VideoAssetsPage />} />
        <Route path="/video/avatar" element={<VideoPackPage kind="avatar" />} />
        <Route path="/video/i2v" element={<VideoPackPage kind="i2v" />} />
        <Route path="/video/motion" element={<VideoPackPage kind="motion" />} />
        <Route path="/resources/characters" element={<CharactersPage />} />
      </Route>
        <Route path="*" element={<HomeRedirect />} />
      </Routes>
    </Suspense>
  );
}
