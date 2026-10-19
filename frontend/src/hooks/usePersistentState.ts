import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

import {
  coercePromptValue,
  emptyPromptValue,
  type PromptFieldValue,
} from "@/lib/promptValue";

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

function resolveInitial<T>(initial: T | (() => T)): T {
  return typeof initial === "function" ? (initial as () => T)() : initial;
}

/**
 * 与 useState 相同签名，但把值持久化到 localStorage（键：liberastra-form:<key>）。
 * 刷新页面、切换功能页后再回来，表单保持上次的配置。
 * key 变化时（如换工作流包）会重新读取对应键；无存档则用当前 initial。
 * 注意：File / FileList 等不可序列化的值不要用它。
 */
export function usePersistentState<T>(
  key: string,
  initial: T | (() => T),
): [T, Dispatch<SetStateAction<T>>] {
  const initialRef = useRef(initial);
  initialRef.current = initial;

  const [value, setValue] = useState<T>(() => {
    const stored = readStored<T>(key);
    if (stored.found) return stored.value as T;
    return resolveInitial(initial);
  });

  // 换 key（换包）时同步切到该键存档；无存档则用最新 initial。layout 阶段执行，避免先闪旧包模型名
  useLayoutEffect(() => {
    const stored = readStored<T>(key);
    setValue(stored.found ? (stored.value as T) : resolveInitial(initialRef.current));
  }, [key]);

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

/**
 * 持久化完整 PromptFieldValue（raw + optimized + 开关）。
 * 兼容旧版仅存 string 的键：首次读取时自动升级为对象结构。
 */
export function usePersistentPromptValue(
  key: string,
  initialRaw = "",
): [PromptFieldValue, Dispatch<SetStateAction<PromptFieldValue>>] {
  const [stored, setStored] = usePersistentState<PromptFieldValue | string>(
    key,
    () => emptyPromptValue(initialRaw),
  );
  const value = coercePromptValue(stored);

  const set = useCallback<Dispatch<SetStateAction<PromptFieldValue>>>(
    (next) => {
      setStored((prev) => {
        const base = coercePromptValue(prev);
        return typeof next === "function" ? next(base) : next;
      });
    },
    [setStored],
  );

  return [value, set];
}
