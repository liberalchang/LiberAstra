import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

const FORM_KEY_PREFIX = "liberastra-form:";

function readStored<T>(key: string): { found: boolean; value?: T } {
  try {
    const raw = localStorage.getItem(FORM_KEY_PREFIX + key);
    if (raw == null) return { found: false };
    return { found: true, value: JSON.parse(raw) as T };
  } catch {
    return { found: false }; // 隐私模式禁用 localStorage 或数据损坏时静默回落默认值
  }
}

/**
 * 与 useState 相同签名，但把值持久化到 localStorage（键：liberastra-form:<key>）。
 * 刷新页面、切换功能页后再回来，表单保持上次的配置。
 * 注意：File / FileList 等不可序列化的值不要用它。
 */
export function usePersistentState<T>(
  key: string,
  initial: T | (() => T),
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    const stored = readStored<T>(key);
    if (stored.found) return stored.value as T;
    return typeof initial === "function" ? (initial as () => T)() : initial;
  });

  const set = useCallback<Dispatch<SetStateAction<T>>>(
    (next) => {
      setValue((prev) => {
        const v = typeof next === "function" ? (next as (p: T) => T)(prev) : next;
        try {
          localStorage.setItem(FORM_KEY_PREFIX + key, JSON.stringify(v));
        } catch {
          /* 写入失败时仅保留内存状态 */
        }
        return v;
      });
    },
    [key],
  );

  return [value, set];
}
