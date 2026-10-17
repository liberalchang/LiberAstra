import { create } from "zustand";
import { persist } from "zustand/middleware";

import { setAuthToken, setUnauthorizedHandler } from "@/api/client";
import type { UserOut } from "@/api/client";

interface AuthState {
  token: string | null;
  user: UserOut | null;
  signIn: (token: string, user: UserOut | null) => void;
  signOut: () => void;
}

/** JWT 是否已过期（解析失败按过期处理）。 */
function isExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload.exp === "number" && payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      signIn: (token, user) => {
        setAuthToken(token);
        set({ token, user });
      },
      signOut: () => {
        setAuthToken(null);
        set({ token: null, user: null });
      },
    }),
    {
      name: "liberastra-auth",
      onRehydrateStorage: () => (state) => {
        const token = state?.token ?? null;
        // 恢复登录态时检查 JWT 是否已过期，过期直接视为未登录
        if (token && isExpired(token)) {
          state?.signOut();
          return;
        }
        setAuthToken(token);
      },
    },
  ),
);

// 任何接口返回 401（且当前持有 token）= 登录态失效，自动登出回登录页
setUnauthorizedHandler(() => useAuthStore.getState().signOut());
