import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import { api } from "@/api/client";
import { Layout } from "@/components/Layout";
import { AuthPage } from "@/pages/AuthPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { SettingsPage } from "@/pages/SettingsPage";
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
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}
