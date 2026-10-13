import { create } from "zustand";
import { persist } from "zustand/middleware";

import { setAuthToken } from "@/api/client";
import type { UserOut } from "@/api/client";

interface AuthState {
  token: string | null;
  user: UserOut | null;
  signIn: (token: string, user: UserOut | null) => void;
  signOut: () => void;
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
        setAuthToken(state?.token ?? null);
      },
    },
  ),
);
